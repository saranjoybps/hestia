from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Literal, Dict, Any, Set
from datetime import datetime
from app.dependencies import get_current_user, require_role
from app.dependencies import db
from app.models import ShiftCreate, ShiftUpdate, ShiftResponse
from app.services.audit_log import log_audit_event
from google.cloud.firestore_v1 import FieldFilter

router = APIRouter(tags=["shifts"])


ALLOWED_TARGET_ROLES = {
    "lead": {"employee"},
    "manager": {"lead", "employee"},
    "director": {"manager", "lead", "employee"},
    "hr": {"manager", "lead", "employee"},
}

APPROVAL_CREATOR_ROLES = {
    "manager": {"manager", "lead"},
    "director": {"director", "manager", "lead"},
    "super_admin": {"director", "manager", "lead"},
}


def _get_direct_reportee_ids(manager_uid: str) -> Set[str]:
    """Return direct reportee ids for a user using manager_id as primary and legacy fallback fields."""
    ids: Set[str] = set()
    queries = [
        db.collection("users").where(filter=FieldFilter("manager_id", "==", manager_uid)),
        db.collection("users").where(filter=FieldFilter("managerId", "==", manager_uid)),
        # Legacy fallback for old datasets
        db.collection("users").where(filter=FieldFilter("lead_id", "==", manager_uid)),
        db.collection("users").where(filter=FieldFilter("leadId", "==", manager_uid)),
    ]
    for query in queries:
        for doc in query.stream():
            ids.add(doc.id)
    return ids


def _is_descendant(manager_uid: str, target_uid: str, max_depth: int = 8) -> bool:
    """Check whether target user exists anywhere under manager in the reporting tree."""
    if not manager_uid or not target_uid or manager_uid == target_uid:
        return False

    visited: Set[str] = {manager_uid}
    frontier: Set[str] = {manager_uid}
    depth = 0

    while frontier and depth < max_depth:
        next_frontier: Set[str] = set()
        for uid in frontier:
            reportee_ids = _get_direct_reportee_ids(uid)
            if target_uid in reportee_ids:
                return True
            for rid in reportee_ids:
                if rid not in visited:
                    visited.add(rid)
                    next_frontier.add(rid)
        frontier = next_frontier
        depth += 1

    return False


def _ensure_shift_hierarchy_access(current_user: Dict[str, Any], target_user: Dict[str, Any], action: str) -> None:
    """Validate role + hierarchy rules for shift create/update actions."""
    actor_role = current_user.get("role")
    actor_uid = current_user.get("uid")
    target_uid = target_user.get("uid")
    target_role = target_user.get("role")

    allowed_roles = ALLOWED_TARGET_ROLES.get(actor_role, set())
    if not allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if target_role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=(
                f"As {actor_role}, you can only {action} shifts for: "
                f"{', '.join(sorted(allowed_roles))}"
            )
        )

    if not _is_descendant(actor_uid, target_uid):
        raise HTTPException(
            status_code=403,
            detail=f"You can only {action} shifts for employees in your reporting hierarchy"
        )


def _get_user_role(uid: Optional[str], role_cache: Dict[str, Optional[str]]) -> Optional[str]:
    if not uid:
        return None
    if uid in role_cache:
        return role_cache[uid]
    doc = db.collection("users").document(uid).get()
    role_cache[uid] = doc.to_dict().get("role") if doc.exists else None
    return role_cache[uid]


def _can_current_user_approve_shift(current_user: Dict[str, Any], shift_data: Dict[str, Any], role_cache: Dict[str, Optional[str]]) -> bool:
    approver_role = current_user.get("role")
    allowed_creator_roles = APPROVAL_CREATOR_ROLES.get(approver_role, set())
    if not allowed_creator_roles:
        return False

    creator_role = _get_user_role(shift_data.get("created_by"), role_cache)
    if creator_role not in allowed_creator_roles:
        return False

    # Managers can only approve/reject shifts for employees under their hierarchy.
    if approver_role == "manager":
        return _is_descendant(current_user.get("uid"), shift_data.get("employee_id"))

    return True


@router.post("/shifts", response_model=ShiftResponse)
async def create_shift(
    shift: ShiftCreate,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))
):
    """
    Create a new shift allocation.
    Hierarchy rules:
    - Director/HR: managers, leads, employees under their hierarchy
    - Manager: leads, employees under their hierarchy
    - Lead: employees under their hierarchy
    """
    try:
        # Verify the employee exists
        employee_ref = db.collection("users").document(shift.employee_id)
        employee_doc = employee_ref.get()
        
        if not employee_doc.exists:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        employee_data = employee_doc.to_dict()
        
        employee_data["uid"] = shift.employee_id
        _ensure_shift_hierarchy_access(current_user, employee_data, "create")
        
        # Check for duplicate shift on same date
        existing_shifts = (
            db.collection("shifts")
            .where(filter=FieldFilter("employee_id", "==", shift.employee_id))
            .where(filter=FieldFilter("shift_date", "==", shift.shift_date))
            .where(filter=FieldFilter("status", "in", ["pending", "approved"]))
            .stream()
        )
        
        if any(existing_shifts):
            raise HTTPException(
                status_code=400,
                detail="A shift already exists for this employee on this date"
            )
        
        # Create shift document
        shift_data = {
            "employee_id": shift.employee_id,
            "employee_name": employee_data.get("name"),
            "employee_email": employee_data.get("email"),
            "shift_type": shift.shift_type,
            "shift_date": shift.shift_date,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
            "notes": shift.notes,
            "status": "pending",
            "created_by": current_user["uid"],
            "created_by_name": current_user.get("name"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        shift_ref = db.collection("shifts").document()
        shift_ref.set(shift_data)

        # Audit log - shift created
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_created",
            description=(
                f"{current_user.get('name', 'Someone')} created a {shift_data['shift_type']} shift for "
                f"{shift_data.get('employee_name', shift_data['employee_id'])} on {shift_data['shift_date']} "
                f"({shift_data['start_time']} - {shift_data['end_time']})."
            ),
            result="success",
            target_type="shift",
            target_id=shift_ref.id,
            metadata={
                "employee_id": shift_data["employee_id"],
                "employee_name": shift_data.get("employee_name"),
                "shift_type": shift_data["shift_type"],
                "shift_date": shift_data["shift_date"],
                "start_time": shift_data["start_time"],
                "end_time": shift_data["end_time"],
                "status": shift_data["status"]
            }
        )
        
        return ShiftResponse(
            id=shift_ref.id,
            **shift_data,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create shift: {str(e)}")


@router.get("/shifts", response_model=dict)
async def get_shifts(
    status: Optional[Literal["pending", "approved", "rejected"]] = None,
    employee_id: Optional[str] = None,
    shift_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get shifts based on filters and user role.
    Visibility rules:
    - Employee: only own shifts
    - Lead: shifts for their reportees (manager_id match) + shifts they created
    - Manager: shifts for their reportees (manager_id match) + shifts they created
    - HR/Director/Super Admin: all shifts
    """
    try:
        user_role = current_user.get("role")
        user_uid = current_user.get("uid")

        query = db.collection("shifts")

        # Apply basic filters at query level where possible
        if status:
            query = query.where(filter=FieldFilter("status", "==", status))
        if employee_id:
            query = query.where(filter=FieldFilter("employee_id", "==", employee_id))
        if shift_date:
            query = query.where(filter=FieldFilter("shift_date", "==", shift_date))

        user_cache = {}

        def get_user(uid: str):
            if uid in user_cache:
                return user_cache[uid]
            doc = db.collection("users").document(uid).get()
            user_cache[uid] = doc.to_dict() if doc.exists else None
            return user_cache[uid]

        def can_view(shift_data: dict) -> bool:
            if user_role in ["director", "super_admin", "hr"]:
                return True
            if user_role == "employee":
                return shift_data.get("employee_id") == user_uid
            if user_role == "manager":
                if shift_data.get("employee_id") == user_uid:
                    return True
                if shift_data.get("created_by") == user_uid:
                    return True
                emp = get_user(shift_data.get("employee_id", ""))
                if not emp:
                    return False
                manager_id = emp.get("manager_id") or emp.get("managerId")
                legacy_lead_id = emp.get("lead_id") or emp.get("leadId")
                return manager_id == user_uid or legacy_lead_id == user_uid
            if user_role == "lead":
                if shift_data.get("employee_id") == user_uid:
                    return True
                if shift_data.get("created_by") == user_uid:
                    return True
                emp = get_user(shift_data.get("employee_id", ""))
                if not emp:
                    return False
                manager_id = emp.get("manager_id") or emp.get("managerId")
                legacy_lead_id = emp.get("lead_id") or emp.get("leadId")
                return manager_id == user_uid or legacy_lead_id == user_uid
            return False

        shifts = []
        for doc in query.stream():
            shift_data = doc.to_dict()
            shift_data["id"] = doc.id

            # Date range filter in memory
            if start_date and shift_data.get("shift_date", "") < start_date:
                continue
            if end_date and shift_data.get("shift_date", "") > end_date:
                continue

            if not can_view(shift_data):
                continue

            shifts.append(ShiftResponse(
                id=shift_data["id"],
                employee_id=shift_data["employee_id"],
                employee_name=shift_data.get("employee_name"),
                employee_email=shift_data.get("employee_email"),
                shift_type=shift_data["shift_type"],
                shift_date=shift_data["shift_date"],
                start_time=shift_data["start_time"],
                end_time=shift_data["end_time"],
                notes=shift_data.get("notes"),
                status=shift_data["status"],
                created_by=shift_data["created_by"],
                created_by_name=shift_data.get("created_by_name"),
                approved_by=shift_data.get("approved_by"),
                approved_by_name=shift_data.get("approved_by_name"),
                rejection_reason=shift_data.get("rejection_reason"),
                created_at=datetime.fromisoformat(shift_data["created_at"]),
                updated_at=datetime.fromisoformat(shift_data["updated_at"]) if shift_data.get("updated_at") else None
            ))

        return {"shifts": shifts, "total": len(shifts)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shifts: {str(e)}")


@router.get("/shifts/pending-approvals", response_model=dict)
async def get_pending_approvals(
    current_user: dict = Depends(require_role("manager", "director", "super_admin"))
):
    """
    Get shifts pending approval.
    Approval rules:
    - director/super_admin: shifts created by director/manager/lead
    - manager: shifts created by manager/lead and employee under manager hierarchy
    """
    try:
        query = db.collection("shifts").where(filter=FieldFilter("status", "==", "pending"))
        role_cache: Dict[str, Optional[str]] = {}
        
        shifts = []
        for doc in query.stream():
            shift_data = doc.to_dict()
            shift_data["id"] = doc.id

            if not _can_current_user_approve_shift(current_user, shift_data, role_cache):
                continue
            
            shifts.append(ShiftResponse(
                id=shift_data["id"],
                employee_id=shift_data["employee_id"],
                employee_name=shift_data.get("employee_name"),
                employee_email=shift_data.get("employee_email"),
                shift_type=shift_data["shift_type"],
                shift_date=shift_data["shift_date"],
                start_time=shift_data["start_time"],
                end_time=shift_data["end_time"],
                notes=shift_data.get("notes"),
                status=shift_data["status"],
                created_by=shift_data["created_by"],
                created_by_name=shift_data.get("created_by_name"),
                approved_by=shift_data.get("approved_by"),
                approved_by_name=shift_data.get("approved_by_name"),
                rejection_reason=shift_data.get("rejection_reason"),
                created_at=datetime.fromisoformat(shift_data["created_at"]),
                updated_at=datetime.fromisoformat(shift_data["updated_at"]) if shift_data.get("updated_at") else None
            ))
        
        return {"shifts": shifts, "total": len(shifts)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending approvals: {str(e)}")


@router.patch("/shifts/{shift_id}/approve", response_model=ShiftResponse)
async def approve_shift(
    shift_id: str,
    current_user: dict = Depends(require_role("manager", "director", "super_admin"))
):
    """
    Approve a shift allocation.
    Approval rules:
    - director/super_admin: shifts created by director/manager/lead
    - manager: shifts created by manager/lead and employee under manager hierarchy
    """
    try:
        shift_ref = db.collection("shifts").document(shift_id)
        shift_doc = shift_ref.get()
        
        if not shift_doc.exists:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        shift_data = shift_doc.to_dict()
        
        if shift_data["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve shift with status: {shift_data['status']}"
            )
        
        if not _can_current_user_approve_shift(current_user, shift_data, {}):
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to approve this shift"
            )
        
        # Update shift status
        update_data = {
            "status": "approved",
            "approved_by": current_user["uid"],
            "approved_by_name": current_user.get("name"),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        shift_ref.update(update_data)
        
        # Get updated data
        updated_doc = shift_ref.get()
        updated_data = updated_doc.to_dict()

        # Audit log - shift approved
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_approved",
            description=(
                f"{current_user.get('name', 'Someone')} approved the shift for "
                f"{updated_data.get('employee_name', updated_data.get('employee_id'))} on "
                f"{updated_data.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": updated_data.get("employee_id"),
                "employee_name": updated_data.get("employee_name"),
                "shift_type": updated_data.get("shift_type"),
                "shift_date": updated_data.get("shift_date"),
                "status": updated_data.get("status")
            }
        )
        
        return ShiftResponse(
            id=shift_id,
            employee_id=updated_data["employee_id"],
            employee_name=updated_data.get("employee_name"),
            employee_email=updated_data.get("employee_email"),
            shift_type=updated_data["shift_type"],
            shift_date=updated_data["shift_date"],
            start_time=updated_data["start_time"],
            end_time=updated_data["end_time"],
            notes=updated_data.get("notes"),
            status=updated_data["status"],
            created_by=updated_data["created_by"],
            created_by_name=updated_data.get("created_by_name"),
            approved_by=updated_data.get("approved_by"),
            approved_by_name=updated_data.get("approved_by_name"),
            rejection_reason=updated_data.get("rejection_reason"),
            created_at=datetime.fromisoformat(updated_data["created_at"]),
            updated_at=datetime.fromisoformat(updated_data["updated_at"]) if updated_data.get("updated_at") else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve shift: {str(e)}")


@router.patch("/shifts/{shift_id}/reject", response_model=ShiftResponse)
async def reject_shift(
    shift_id: str,
    rejection_data: dict,
    current_user: dict = Depends(require_role("manager", "director", "super_admin"))
):
    """
    Reject a shift allocation with a reason.
    Rejection rules are the same as approval rules.
    """
    try:
        rejection_reason = rejection_data.get("rejection_reason")
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        shift_ref = db.collection("shifts").document(shift_id)
        shift_doc = shift_ref.get()
        
        if not shift_doc.exists:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        shift_data = shift_doc.to_dict()
        
        if shift_data["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject shift with status: {shift_data['status']}"
            )
        
        if not _can_current_user_approve_shift(current_user, shift_data, {}):
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to reject this shift"
            )
        
        # Update shift status
        update_data = {
            "status": "rejected",
            "approved_by": current_user["uid"],
            "approved_by_name": current_user.get("name"),
            "rejection_reason": rejection_reason,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        shift_ref.update(update_data)
        
        # Get updated data
        updated_doc = shift_ref.get()
        updated_data = updated_doc.to_dict()

        # Audit log - shift rejected
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_rejected",
            description=(
                f"{current_user.get('name', 'Someone')} rejected the shift for "
                f"{updated_data.get('employee_name', updated_data.get('employee_id'))} on "
                f"{updated_data.get('shift_date')}. Reason: {updated_data.get('rejection_reason')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": updated_data.get("employee_id"),
                "employee_name": updated_data.get("employee_name"),
                "shift_type": updated_data.get("shift_type"),
                "shift_date": updated_data.get("shift_date"),
                "status": updated_data.get("status"),
                "rejection_reason": updated_data.get("rejection_reason")
            }
        )
        
        return ShiftResponse(
            id=shift_id,
            employee_id=updated_data["employee_id"],
            employee_name=updated_data.get("employee_name"),
            employee_email=updated_data.get("employee_email"),
            shift_type=updated_data["shift_type"],
            shift_date=updated_data["shift_date"],
            start_time=updated_data["start_time"],
            end_time=updated_data["end_time"],
            notes=updated_data.get("notes"),
            status=updated_data["status"],
            created_by=updated_data["created_by"],
            created_by_name=updated_data.get("created_by_name"),
            approved_by=updated_data.get("approved_by"),
            approved_by_name=updated_data.get("approved_by_name"),
            rejection_reason=updated_data.get("rejection_reason"),
            created_at=datetime.fromisoformat(updated_data["created_at"]),
            updated_at=datetime.fromisoformat(updated_data["updated_at"]) if updated_data.get("updated_at") else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject shift: {str(e)}")


@router.patch("/shifts/bulk-approve", response_model=dict)
async def bulk_approve_shifts(
    payload: dict,
    current_user: dict = Depends(require_role("manager", "director", "super_admin"))
):
    """
    Bulk approve pending shifts.
    Approval rules are the same as single approval.
    """
    try:
        shift_ids = payload.get("shift_ids") or []
        if not isinstance(shift_ids, list) or len(shift_ids) == 0:
            raise HTTPException(status_code=400, detail="shift_ids is required")

        role_cache: Dict[str, Optional[str]] = {}
        approved: list[str] = []
        failed: list[dict] = []

        for shift_id in shift_ids:
            try:
                shift_ref = db.collection("shifts").document(shift_id)
                shift_doc = shift_ref.get()
                if not shift_doc.exists:
                    failed.append({"id": shift_id, "reason": "Shift not found"})
                    continue

                shift_data = shift_doc.to_dict()
                if shift_data.get("status") != "pending":
                    failed.append({"id": shift_id, "reason": f"Cannot approve shift with status: {shift_data.get('status')}"})
                    continue

                if not _can_current_user_approve_shift(current_user, shift_data, role_cache):
                    failed.append({"id": shift_id, "reason": "You are not allowed to approve this shift"})
                    continue

                update_data = {
                    "status": "approved",
                    "approved_by": current_user["uid"],
                    "approved_by_name": current_user.get("name"),
                    "updated_at": datetime.utcnow().isoformat()
                }
                shift_ref.update(update_data)

                # Audit log - shift approved
                log_audit_event(
                    actor_id=current_user.get("uid"),
                    actor_name=current_user.get("name"),
                    actor_email=current_user.get("email"),
                    module="shift_management",
                    action="shift_approved",
                    description=(
                        f"{current_user.get('name', 'Someone')} approved the shift for "
                        f"{shift_data.get('employee_name', shift_data.get('employee_id'))} on "
                        f"{shift_data.get('shift_date')}."
                    ),
                    result="success",
                    target_type="shift",
                    target_id=shift_id,
                    metadata={
                        "employee_id": shift_data.get("employee_id"),
                        "employee_name": shift_data.get("employee_name"),
                        "shift_type": shift_data.get("shift_type"),
                        "shift_date": shift_data.get("shift_date"),
                        "status": "approved"
                    }
                )

                approved.append(shift_id)
            except Exception as inner:
                failed.append({"id": shift_id, "reason": str(inner)})

        return {
            "approved": approved,
            "failed": failed,
            "successCount": len(approved),
            "failCount": len(failed)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk approve shifts: {str(e)}")


@router.patch("/shifts/bulk-reject", response_model=dict)
async def bulk_reject_shifts(
    payload: dict,
    current_user: dict = Depends(require_role("manager", "director", "super_admin"))
):
    """
    Bulk reject pending shifts with a reason.
    Rejection rules are the same as single rejection.
    """
    try:
        shift_ids = payload.get("shift_ids") or []
        rejection_reason = payload.get("rejection_reason")
        if not isinstance(shift_ids, list) or len(shift_ids) == 0:
            raise HTTPException(status_code=400, detail="shift_ids is required")
        if not rejection_reason or not str(rejection_reason).strip():
            raise HTTPException(status_code=400, detail="rejection_reason is required")

        role_cache: Dict[str, Optional[str]] = {}
        rejected: list[str] = []
        failed: list[dict] = []

        for shift_id in shift_ids:
            try:
                shift_ref = db.collection("shifts").document(shift_id)
                shift_doc = shift_ref.get()
                if not shift_doc.exists:
                    failed.append({"id": shift_id, "reason": "Shift not found"})
                    continue

                shift_data = shift_doc.to_dict()
                if shift_data.get("status") != "pending":
                    failed.append({"id": shift_id, "reason": f"Cannot reject shift with status: {shift_data.get('status')}"})
                    continue

                if not _can_current_user_approve_shift(current_user, shift_data, role_cache):
                    failed.append({"id": shift_id, "reason": "You are not allowed to reject this shift"})
                    continue

                update_data = {
                    "status": "rejected",
                    "approved_by": current_user["uid"],
                    "approved_by_name": current_user.get("name"),
                    "rejection_reason": rejection_reason,
                    "updated_at": datetime.utcnow().isoformat()
                }
                shift_ref.update(update_data)

                # Audit log - shift rejected
                log_audit_event(
                    actor_id=current_user.get("uid"),
                    actor_name=current_user.get("name"),
                    actor_email=current_user.get("email"),
                    module="shift_management",
                    action="shift_rejected",
                    description=(
                        f"{current_user.get('name', 'Someone')} rejected the shift for "
                        f"{shift_data.get('employee_name', shift_data.get('employee_id'))} on "
                        f"{shift_data.get('shift_date')}. Reason: {rejection_reason}."
                    ),
                    result="success",
                    target_type="shift",
                    target_id=shift_id,
                    metadata={
                        "employee_id": shift_data.get("employee_id"),
                        "employee_name": shift_data.get("employee_name"),
                        "shift_type": shift_data.get("shift_type"),
                        "shift_date": shift_data.get("shift_date"),
                        "status": "rejected",
                        "rejection_reason": rejection_reason
                    }
                )

                rejected.append(shift_id)
            except Exception as inner:
                failed.append({"id": shift_id, "reason": str(inner)})

        return {
            "rejected": rejected,
            "failed": failed,
            "successCount": len(rejected),
            "failCount": len(failed)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk reject shifts: {str(e)}")


@router.delete("/shifts/{shift_id}")
async def delete_shift(
    shift_id: str,
    current_user: dict = Depends(require_role("lead", "manager", "director"))
):
    """
    Delete a shift allocation.
    Only the creator or managers/directors can delete shifts.
    Can only delete pending shifts.
    """
    try:
        shift_ref = db.collection("shifts").document(shift_id)
        shift_doc = shift_ref.get()
        
        if not shift_doc.exists:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        shift_data = shift_doc.to_dict()
        
        # Check permissions
        if current_user["role"] == "lead":
            if shift_data["created_by"] != current_user["uid"]:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete shifts you created"
                )
        
        # Can only delete pending shifts
        if shift_data["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete shift with status: {shift_data['status']}"
            )
        
        shift_ref.delete()

        # Audit log - shift deleted
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_deleted",
            description=(
                f"{current_user.get('name', 'Someone')} deleted the shift for "
                f"{shift_data.get('employee_name', shift_data.get('employee_id'))} on "
                f"{shift_data.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": shift_data.get("employee_id"),
                "employee_name": shift_data.get("employee_name"),
                "shift_type": shift_data.get("shift_type"),
                "shift_date": shift_data.get("shift_date"),
                "status": shift_data.get("status")
            }
        )
        
        return {"message": "Shift deleted successfully", "id": shift_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete shift: {str(e)}")


@router.patch("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: str,
    shift_update: ShiftUpdate,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))
):
    """
    Update a shift allocation.
    Hierarchy rules are the same as create-shift.
    Approved shifts can be edited, but will be reset to pending for re-approval.
    """
    try:
        shift_ref = db.collection("shifts").document(shift_id)
        shift_doc = shift_ref.get()
        
        if not shift_doc.exists:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        shift_data = shift_doc.to_dict()
        
        # Check hierarchy permissions against the shift employee
        employee_ref = db.collection("users").document(shift_data["employee_id"])
        employee_doc = employee_ref.get()
        if not employee_doc.exists:
            raise HTTPException(status_code=404, detail="Employee not found for this shift")
        employee_data = employee_doc.to_dict()
        employee_data["uid"] = shift_data["employee_id"]
        _ensure_shift_hierarchy_access(current_user, employee_data, "update")
        
        # Can only update pending or approved shifts
        if shift_data["status"] not in ["pending", "approved"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot update shift with status: {shift_data['status']}"
            )
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }

        # If an approved shift is edited, reset it to pending for re-approval
        if shift_data["status"] == "approved":
            update_data["status"] = "pending"
            update_data["approved_by"] = None
            update_data["approved_by_name"] = None
            update_data["rejection_reason"] = None
        
        if shift_update.shift_type is not None:
            update_data["shift_type"] = shift_update.shift_type
        if shift_update.shift_date is not None:
            update_data["shift_date"] = shift_update.shift_date
        if shift_update.start_time is not None:
            update_data["start_time"] = shift_update.start_time
        if shift_update.end_time is not None:
            update_data["end_time"] = shift_update.end_time
        if shift_update.notes is not None:
            update_data["notes"] = shift_update.notes
        
        shift_ref.update(update_data)
        
        # Get updated data
        updated_doc = shift_ref.get()
        updated_data = updated_doc.to_dict()

        # Audit log - shift updated
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated the shift for "
                f"{updated_data.get('employee_name', updated_data.get('employee_id'))} on "
                f"{updated_data.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "employee_id": updated_data.get("employee_id"),
                "employee_name": updated_data.get("employee_name"),
                "shift_type": updated_data.get("shift_type"),
                "shift_date": updated_data.get("shift_date"),
                "start_time": updated_data.get("start_time"),
                "end_time": updated_data.get("end_time"),
                "status": updated_data.get("status")
            }
        )
        
        return ShiftResponse(
            id=shift_id,
            employee_id=updated_data["employee_id"],
            employee_name=updated_data.get("employee_name"),
            employee_email=updated_data.get("employee_email"),
            shift_type=updated_data["shift_type"],
            shift_date=updated_data["shift_date"],
            start_time=updated_data["start_time"],
            end_time=updated_data["end_time"],
            notes=updated_data.get("notes"),
            status=updated_data["status"],
            created_by=updated_data["created_by"],
            created_by_name=updated_data.get("created_by_name"),
            approved_by=updated_data.get("approved_by"),
            approved_by_name=updated_data.get("approved_by_name"),
            rejection_reason=updated_data.get("rejection_reason"),
            created_at=datetime.fromisoformat(updated_data["created_at"]),
            updated_at=datetime.fromisoformat(updated_data["updated_at"]) if updated_data.get("updated_at") else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update shift: {str(e)}")
