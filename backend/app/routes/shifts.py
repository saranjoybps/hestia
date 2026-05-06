from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Body

from app.dependencies import get_current_user, require_role, supabase
from app.models import ShiftCreate, ShiftUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

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


def _get_descendants(manager_uid: str, user_map: Dict[str, Dict[str, Any]], max_depth: int = 8) -> Set[str]:
    def _identifiers(row: Dict[str, Any]) -> Set[str]:
        identifiers: Set[str] = set()
        if row.get("uid"):
            identifiers.add(str(row["uid"]))
        if row.get("id"):
            identifiers.add(str(row["id"]))
        return identifiers

    root_identifiers: Set[str] = {str(manager_uid)} if manager_uid else set()
    for row in user_map.values():
        row_identifiers = _identifiers(row)
        if str(manager_uid) in row_identifiers:
            root_identifiers.update(row_identifiers)
            break

    visited: Set[str] = set(root_identifiers)
    frontier: Set[str] = set(root_identifiers)
    depth = 0
    while frontier and depth < max_depth:
        next_frontier: Set[str] = set()
        for uid in frontier:
            for other_uid, data in user_map.items():
                if other_uid in visited or other_uid == manager_uid:
                    continue
                data_identifiers = _identifiers(data)
                manager_id = str(data.get("manager_id") or "")
                lead_id = str(data.get("lead_id") or "")
                if manager_id in frontier or lead_id in frontier:
                    visited.update(data_identifiers)
                    next_frontier.update(data_identifiers)
        frontier = next_frontier
        depth += 1
    return visited - root_identifiers


def _ensure_shift_hierarchy_access(current_user: Dict[str, Any], target_user: Dict[str, Any], action: str) -> None:
    actor_role = current_user.get("role")
    actor_uid = current_user.get("uid")
    target_uid = target_user.get("uid")
    target_role = target_user.get("role")

    allowed_roles = ALLOWED_TARGET_ROLES.get(actor_role, set())
    if not allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if target_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"As {actor_role}, you can only {action} shifts for: {', '.join(sorted(allowed_roles))}")

    user_map = getattr(_ensure_shift_hierarchy_access, "_user_map", {})
    if actor_uid not in _get_descendants(actor_uid, user_map) and actor_uid != target_uid and actor_role in {"lead", "manager"}:
        # fallback check is handled by caller when user_map is populated
        pass


async def _current_internal_user_id(firebase_uid: str) -> Optional[str]:
    return await SupabaseHelper.get_internal_user_id(firebase_uid)


async def _shift_to_public(row: Dict[str, Any]) -> Dict[str, Any]:
    employee = await SupabaseHelper.get_public_user_by_id(row.get("employee_id")) if row.get("employee_id") else None
    creator = await SupabaseHelper.get_public_user_by_id(row.get("created_by")) if row.get("created_by") else None
    approver = await SupabaseHelper.get_public_user_by_id(row.get("approved_by")) if row.get("approved_by") else None
    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "employee_id": employee.get("uid") if employee else None,
        "employee_name": row.get("employee_name") or (employee.get("name") if employee else None),
        "employee_email": row.get("employee_email") or (employee.get("email") if employee else None),
        "shift_type": row.get("shift_type"),
        "shift_date": row.get("shift_date"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "notes": row.get("notes"),
        "status": row.get("status"),
        "created_by": creator.get("uid") if creator else None,
        "created_by_name": row.get("created_by_name") or (creator.get("name") if creator else None),
        "approved_by": approver.get("uid") if approver else None,
        "approved_by_name": row.get("approved_by_name") or (approver.get("name") if approver else None),
        "rejection_reason": row.get("rejection_reason"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def _can_current_user_approve_shift(current_user: Dict[str, Any], shift_data: Dict[str, Any], role_cache: Dict[str, Optional[str]]) -> bool:
    approver_role = current_user.get("role")
    allowed_creator_roles = APPROVAL_CREATOR_ROLES.get(approver_role, set())
    if not allowed_creator_roles:
        return False

    creator = await SupabaseHelper.get_public_user_by_id(shift_data.get("created_by")) if shift_data.get("created_by") else None
    creator_role = creator.get("role") if creator else None
    if creator_role not in allowed_creator_roles:
        return False

    if approver_role == "manager":
        user_map = role_cache.get("_user_map") or await SupabaseHelper.get_public_user_map()
        return shift_data.get("employee_id") in _get_descendants(current_user.get("uid"), user_map)
    return True


def _normalize_shift_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return row


def _build_shift_name(employee_name: Optional[str], shift_type: str, shift_date: str) -> str:
    """Generate a stable display name for shift rows that require a non-null name."""
    person = (employee_name or "Employee").strip() or "Employee"
    shift_label = (shift_type or "shift").replace("_", " ").strip().title() or "Shift"
    date_label = (shift_date or "").strip()
    return f"{person} - {shift_label} - {date_label}".strip(" -")


@router.post("/shifts")
async def create_shift(
    shift: ShiftCreate,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr")),
):
    try:
        employee_row = await SupabaseHelper.get_user_row_by_firebase_uid(shift.employee_id)
        if not employee_row:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee_data = await SupabaseHelper.get_public_user_by_id(employee_row["id"])
        employee_data["uid"] = shift.employee_id

        user_map = await SupabaseHelper.get_public_user_map()
        if current_user.get("role") in {"lead", "manager", "director", "hr"}:
            allowed = ALLOWED_TARGET_ROLES.get(current_user.get("role"), set())
            if employee_data.get("role") not in allowed:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            if current_user.get("role") in {"lead", "manager"} and shift.employee_id not in _get_descendants(current_user.get("uid"), user_map):
                raise HTTPException(status_code=403, detail="You can only create shifts for employees in your reporting hierarchy")

        creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not creator_row:
            raise HTTPException(status_code=404, detail="Current user not found")

        existing = supabase.table("shifts").select("id").eq("employee_id", str(employee_row["id"])).eq("shift_date", shift.shift_date).execute()
        if any(row for row in (existing.data or []) if row):
            raise HTTPException(status_code=400, detail="A shift already exists for this employee on this date")

        shift_row = {
            "name": _build_shift_name(employee_data.get("name"), shift.shift_type, shift.shift_date),
            "employee_id": str(employee_row["id"]),
            "employee_name": employee_data.get("name"),
            "employee_email": employee_data.get("email"),
            "shift_type": shift.shift_type,
            "shift_date": shift.shift_date,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
            "notes": shift.notes,
            "status": "pending",
            "created_by": str(creator_row["id"]),
            "created_by_name": current_user.get("name"),
            "approved_by": None,
            "approved_by_name": None,
            "rejection_reason": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("shifts").insert(shift_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create shift")

        shift_public = await _shift_to_public(inserted)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_created",
            description=(
                f"{current_user.get('name', 'Someone')} created a {shift_public['shift_type']} shift for "
                f"{shift_public.get('employee_name', shift_public['employee_id'])} on {shift_public['shift_date']} "
                f"({shift_public['start_time']} - {shift_public['end_time']})."
            ),
            result="success",
            target_type="shift",
            target_id=shift_public["id"],
            metadata={
                "employee_id": shift_public["employee_id"],
                "employee_name": shift_public.get("employee_name"),
                "shift_type": shift_public["shift_type"],
                "shift_date": shift_public["shift_date"],
                "start_time": shift_public["start_time"],
                "end_time": shift_public["end_time"],
                "status": shift_public["status"],
            },
        )
        return shift_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create shift: {str(e)}")


@router.get("/shifts")
async def get_shifts(
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    shift_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        query = supabase.table("shifts").select("*").order("created_at", desc=True)

        if status:
            query = query.eq("status", status)
        if employee_id:
            employee_row = await SupabaseHelper.get_user_row_by_firebase_uid(employee_id)
            if employee_row:
                query = query.eq("employee_id", str(employee_row["id"]))
            else:
                return {"shifts": []}
        if shift_date:
            query = query.eq("shift_date", shift_date)

        resp = query.execute()
        rows = resp.data or []

        user_role = current_user.get("role")
        user_uid = current_user.get("uid")
        user_map = await SupabaseHelper.get_public_user_map()
        public_rows = []
        for row in rows:
            public_row = await _shift_to_public(row)
            if start_date and public_row.get("shift_date", "") < start_date:
                continue
            if end_date and public_row.get("shift_date", "") > end_date:
                continue

            if user_role in ["director", "super_admin", "hr"]:
                public_rows.append(public_row)
                continue
            if user_role == "employee":
                if public_row.get("employee_id") == user_uid:
                    public_rows.append(public_row)
                continue
            if user_role in {"manager", "lead"}:
                if public_row.get("employee_id") == user_uid or public_row.get("created_by") == user_uid:
                    public_rows.append(public_row)
                    continue
                if public_row.get("employee_id") in _get_descendants(user_uid, user_map):
                    public_rows.append(public_row)

        return {"shifts": public_rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shifts: {str(e)}")


@router.get("/shifts/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    try:
        resp = supabase.table("shifts").select("*").eq("status", "pending").order("created_at", desc=True).execute()
        rows = resp.data or []
        role_cache: Dict[str, Optional[str]] = {}
        role_cache["_user_map"] = await SupabaseHelper.get_public_user_map()
        approvals = []
        for row in rows:
            if await _can_current_user_approve_shift(current_user, row, role_cache):
                approvals.append(await _shift_to_public(row))
        return {"shifts": approvals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending approvals: {str(e)}")


@router.patch("/shifts/{shift_id}/approve")
async def approve_shift(shift_id: str, current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    try:
        resp = supabase.table("shifts").select("*").eq("id", shift_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Shift not found")
        shift_data = resp.data[0]
        if shift_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot approve shift with status: {shift_data.get('status')}")

        role_cache: Dict[str, Optional[str]] = {"_user_map": await SupabaseHelper.get_public_user_map()}
        if not await _can_current_user_approve_shift(current_user, shift_data, role_cache):
            raise HTTPException(status_code=403, detail="You are not allowed to approve this shift")

        approver_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        update_resp = supabase.table("shifts").update({
            "status": "approved",
            "approved_by": str(approver_row["id"]) if approver_row else None,
            "approved_by_name": current_user.get("name"),
            "rejection_reason": None,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", shift_id).execute()
        updated = update_resp.data[0] if update_resp.data else None
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to approve shift")

        shift_public = await _shift_to_public(updated)
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_approved",
            description=(
                f"{current_user.get('name', 'Someone')} approved the shift for "
                f"{shift_public.get('employee_name', shift_public.get('employee_id'))} on {shift_public.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": shift_public.get("employee_id"),
                "employee_name": shift_public.get("employee_name"),
                "shift_type": shift_public.get("shift_type"),
                "shift_date": shift_public.get("shift_date"),
                "status": "approved",
            },
        )
        return shift_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve shift: {str(e)}")


@router.patch("/shifts/{shift_id}/reject")
async def reject_shift(shift_id: str, rejection_reason: str = Body(..., embed=True), current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    try:
        resp = supabase.table("shifts").select("*").eq("id", shift_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Shift not found")
        shift_data = resp.data[0]
        if shift_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot reject shift with status: {shift_data.get('status')}")

        role_cache: Dict[str, Optional[str]] = {"_user_map": await SupabaseHelper.get_public_user_map()}
        if not await _can_current_user_approve_shift(current_user, shift_data, role_cache):
            raise HTTPException(status_code=403, detail="You are not allowed to reject this shift")

        approver_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        update_resp = supabase.table("shifts").update({
            "status": "rejected",
            "approved_by": str(approver_row["id"]) if approver_row else None,
            "approved_by_name": current_user.get("name"),
            "rejection_reason": rejection_reason,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", shift_id).execute()
        updated = update_resp.data[0] if update_resp.data else None
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to reject shift")

        shift_public = await _shift_to_public(updated)
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_rejected",
            description=(
                f"{current_user.get('name', 'Someone')} rejected the shift for "
                f"{shift_public.get('employee_name', shift_public.get('employee_id'))} on {shift_public.get('shift_date')}. Reason: {rejection_reason}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": shift_public.get("employee_id"),
                "employee_name": shift_public.get("employee_name"),
                "shift_type": shift_public.get("shift_type"),
                "shift_date": shift_public.get("shift_date"),
                "status": "rejected",
                "rejection_reason": rejection_reason,
            },
        )
        return shift_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject shift: {str(e)}")


@router.patch("/shifts/bulk-approve")
async def bulk_approve_shifts(payload: Dict[str, Any], current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    try:
        shift_ids = payload.get("shift_ids") or []
        if not isinstance(shift_ids, list) or not shift_ids:
            raise HTTPException(status_code=400, detail="shift_ids is required")

        approved: List[str] = []
        failed: List[Dict[str, str]] = []
        for shift_id in shift_ids:
            try:
                await approve_shift(shift_id, current_user=current_user)
                approved.append(shift_id)
            except Exception as inner:
                failed.append({"id": shift_id, "reason": str(inner)})
        return {"approved": approved, "failed": failed, "successCount": len(approved), "failCount": len(failed)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk approve shifts: {str(e)}")


@router.patch("/shifts/bulk-reject")
async def bulk_reject_shifts(payload: Dict[str, Any], current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    try:
        shift_ids = payload.get("shift_ids") or []
        rejection_reason = payload.get("rejection_reason")
        if not isinstance(shift_ids, list) or not shift_ids:
            raise HTTPException(status_code=400, detail="shift_ids is required")
        if not rejection_reason or not str(rejection_reason).strip():
            raise HTTPException(status_code=400, detail="rejection_reason is required")

        rejected: List[str] = []
        failed: List[Dict[str, str]] = []
        for shift_id in shift_ids:
            try:
                await reject_shift(shift_id, rejection_reason=rejection_reason, current_user=current_user)
                rejected.append(shift_id)
            except Exception as inner:
                failed.append({"id": shift_id, "reason": str(inner)})
        return {"rejected": rejected, "failed": failed, "successCount": len(rejected), "failCount": len(failed)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk reject shifts: {str(e)}")


@router.delete("/shifts/{shift_id}")
async def delete_shift(shift_id: str, current_user: dict = Depends(require_role("lead", "manager", "director"))):
    try:
        resp = supabase.table("shifts").select("*").eq("id", shift_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Shift not found")
        shift_data = resp.data[0]

        if current_user["role"] == "lead":
            creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
            if not creator_row or str(shift_data.get("created_by")) != str(creator_row["id"]):
                raise HTTPException(status_code=403, detail="You can only delete shifts you created")

        if shift_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot delete shift with status: {shift_data.get('status')}")

        shift_public = await _shift_to_public(shift_data)
        supabase.table("shifts").delete().eq("id", shift_id).execute()

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_deleted",
            description=(
                f"{current_user.get('name', 'Someone')} deleted the shift for "
                f"{shift_public.get('employee_name', shift_public.get('employee_id'))} on {shift_public.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "employee_id": shift_public.get("employee_id"),
                "employee_name": shift_public.get("employee_name"),
                "shift_type": shift_public.get("shift_type"),
                "shift_date": shift_public.get("shift_date"),
                "status": shift_public.get("status"),
            },
        )
        return {"message": "Shift deleted successfully", "id": shift_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete shift: {str(e)}")


@router.patch("/shifts/{shift_id}")
async def update_shift(
    shift_id: str,
    shift_update: ShiftUpdate,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr")),
):
    try:
        resp = supabase.table("shifts").select("*").eq("id", shift_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Shift not found")

        shift_data = resp.data[0]
        employee_row = await SupabaseHelper.get_public_user_by_id(shift_data.get("employee_id")) if shift_data.get("employee_id") else None
        if not employee_row:
            raise HTTPException(status_code=404, detail="Employee not found for this shift")

        user_map = await SupabaseHelper.get_public_user_map()
        if current_user.get("role") in {"lead", "manager"} and employee_row.get("uid") not in _get_descendants(current_user.get("uid"), user_map) and employee_row.get("uid") != current_user.get("uid"):
            raise HTTPException(status_code=403, detail="You can only update shifts for employees in your reporting hierarchy")

        if shift_data.get("status") not in ["pending", "approved"]:
            raise HTTPException(status_code=400, detail=f"Cannot update shift with status: {shift_data.get('status')}")

        update_data: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
        if shift_data.get("status") == "approved":
            update_data.update({"status": "pending", "approved_by": None, "approved_by_name": None, "rejection_reason": None})
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

        update_resp = supabase.table("shifts").update(update_data).eq("id", shift_id).execute()
        updated = update_resp.data[0] if update_resp.data else None
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update shift")

        shift_public = await _shift_to_public(updated)
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="shift_management",
            action="shift_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated the shift for "
                f"{shift_public.get('employee_name', shift_public.get('employee_id'))} on {shift_public.get('shift_date')}."
            ),
            result="success",
            target_type="shift",
            target_id=shift_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "employee_id": shift_public.get("employee_id"),
                "employee_name": shift_public.get("employee_name"),
                "shift_type": shift_public.get("shift_type"),
                "shift_date": shift_public.get("shift_date"),
                "start_time": shift_public.get("start_time"),
                "end_time": shift_public.get("end_time"),
                "status": shift_public.get("status"),
            },
        )
        return shift_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update shift: {str(e)}")
