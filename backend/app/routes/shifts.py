from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Body, Depends, HTTPException

from app.dependencies import get_current_user, require_role, supabase
from app.models import ShiftAllocationCreate, ShiftAllocationUpdate, ShiftTemplateCreate, ShiftTemplateUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(tags=["shifts"])

TEMPLATE_ROLES = {"hr", "director", "super_admin"}
ALLOCATION_ROLES = {"lead", "manager", "hr", "director", "super_admin"}
TARGET_ROLES = {
    "lead": {"employee"},
    "manager": {"employee", "lead"},
    "hr": {"employee", "lead", "manager"},
    "director": {"employee", "lead", "manager", "hr", "director"},
    "super_admin": {"employee", "lead", "manager", "hr", "director"},
}
APPROVAL_CREATOR_ROLES = {
    "manager": {"lead"},
    "director": {"hr", "manager", "lead"},
    "super_admin": {"hr", "manager", "lead", "director"},
}


def _get_descendants(manager_uid: str, user_map: Dict[str, Dict[str, Any]]) -> Set[str]:
    root = next((u for u in user_map.values() if u.get("uid") == manager_uid), None)
    if not root:
        return set()
    root_ids = {str(manager_uid), str(root.get("id"))}
    descendants: Set[str] = set()
    frontier = set(root_ids)
    while frontier:
        next_frontier: Set[str] = set()
        for row in user_map.values():
            uid = str(row.get("uid") or "")
            internal_id = str(row.get("id") or "")
            if uid in descendants or internal_id in descendants or uid == manager_uid:
                continue
            if str(row.get("manager_id") or "") in frontier or str(row.get("lead_id") or "") in frontier:
                descendants.update(value for value in (uid, internal_id) if value)
                next_frontier.update(value for value in (uid, internal_id) if value)
        frontier = next_frontier
    return descendants - root_ids


async def _get_template(template_id: str) -> Dict[str, Any]:
    response = supabase.table("shift_templates").select("*").eq("id", template_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Shift template not found")
    row = response.data[0]
    return row


async def _get_employee(employee_uid: str) -> Dict[str, Any]:
    row = await SupabaseHelper.get_user_row_by_firebase_uid(employee_uid)
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    public = SupabaseHelper._public_user(row) or {}
    public["id"] = str(row["id"])
    return public


async def _check_allocation_scope(actor: Dict[str, Any], employee: Dict[str, Any]) -> None:
    role = actor.get("role")
    if role not in ALLOCATION_ROLES:
        raise HTTPException(status_code=403, detail="You cannot allocate shifts")
    if employee.get("role") not in TARGET_ROLES.get(role, set()):
        raise HTTPException(status_code=403, detail="You cannot allocate shifts to this role")
    if role in {"lead", "manager"}:
        user_map = await SupabaseHelper.get_public_user_map()
        if employee.get("uid") not in _get_descendants(str(actor.get("uid")), user_map):
            raise HTTPException(status_code=403, detail="You can only allocate shifts within your reporting tree")


async def _get_allocation(shift_id: str) -> Dict[str, Any]:
    response = supabase.table("shifts").select("*").eq("id", shift_id).execute()
    if not response.data or not response.data[0].get("employee_id"):
        raise HTTPException(status_code=404, detail="Shift allocation not found")
    return response.data[0]


async def _shift_to_public(row: Dict[str, Any], user_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    user_map = user_map or await SupabaseHelper.get_public_user_map()
    employee = user_map.get(str(row.get("employee_id"))) if row.get("employee_id") else None
    creator = user_map.get(str(row.get("created_by"))) if row.get("created_by") else None
    approver = user_map.get(str(row.get("approved_by"))) if row.get("approved_by") else None
    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "employee_id": employee.get("uid") if employee else None,
        "employee_name": row.get("employee_name") or (employee.get("name") if employee else None),
        "employee_email": row.get("employee_email") or (employee.get("email") if employee else None),
        "shift_type": row.get("shift_type"),
        "shift_template_id": row.get("shift_template_id"),
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


async def _can_approve(actor: Dict[str, Any], allocation: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    role = actor.get("role")
    creator = user_map.get(str(allocation.get("created_by"))) if allocation.get("created_by") else None
    if not creator or creator.get("role") not in APPROVAL_CREATOR_ROLES.get(role, set()):
        return False
    if role == "manager":
        employee = user_map.get(str(allocation.get("employee_id"))) if allocation.get("employee_id") else None
        return bool(employee and employee.get("uid") in _get_descendants(str(actor.get("uid")), user_map))
    return True


def _audit(actor: Dict[str, Any], action: str, description: str, target_id: str, metadata: Dict[str, Any]) -> None:
    log_audit_event(
        actor_id=actor.get("uid"), actor_name=actor.get("name"), actor_email=actor.get("email"),
        module="shift_management", action=action, description=description, result="success",
        target_type="shift", target_id=target_id, metadata=metadata,
    )


@router.get("/shift-templates")
async def list_shift_templates(current_user: dict = Depends(require_role("lead", "manager", "hr", "director", "super_admin"))):
    response = supabase.table("shift_templates").select("*").order("created_at").execute()
    return {"templates": [
        {"id": str(row["id"]), "name": row["name"], "start_time": row["start_time"], "end_time": row["end_time"],
         "notes": row.get("notes"), "created_by": row.get("created_by"), "created_at": row.get("created_at")}
        for row in (response.data or [])
    ]}


@router.post("/shift-templates", status_code=201)
async def create_shift_template(template: ShiftTemplateCreate, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    name = template.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Shift name is required")
    existing = supabase.table("shift_templates").select("id,name").execute()
    if any(str(row.get("name", "")).casefold() == name.casefold() for row in (existing.data or [])):
        raise HTTPException(status_code=409, detail="A shift with this name already exists")
    creator = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    if not creator:
        raise HTTPException(status_code=404, detail="Current user not found")
    now = datetime.utcnow().isoformat()
    try:
        response = supabase.table("shift_templates").insert({
            "name": name,
            "start_time": template.start_time, "end_time": template.end_time, "notes": template.notes,
            "created_by": str(creator["id"]),
            "created_at": now, "updated_at": now,
        }).execute()
    except Exception as error:
        if "duplicate key" in str(error).lower() or "unique constraint" in str(error).lower():
            raise HTTPException(status_code=409, detail="A shift with this name already exists")
        raise
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create shift")
    row = response.data[0]
    _audit(current_user, "shift_template_created", f"Created shift template {name}.", str(row["id"]), {"name": name})
    return {"id": str(row["id"]), "name": name, "start_time": row["start_time"], "end_time": row["end_time"], "notes": row.get("notes")}


@router.patch("/shift-templates/{template_id}")
async def update_shift_template(template_id: str, update: ShiftTemplateUpdate, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    row = await _get_template(template_id)
    changes = update.model_dump(exclude_unset=True)
    if changes.get("start_time", row["start_time"]) == changes.get("end_time", row["end_time"]):
        raise HTTPException(status_code=422, detail="Start and end times must be different")
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Shift name is required")
        existing = supabase.table("shift_templates").select("id,name").execute()
        if any(r.get("id") != template_id and str(r.get("name", "")).casefold() == changes["name"].casefold() for r in (existing.data or [])):
            raise HTTPException(status_code=409, detail="A shift with this name already exists")
    if not changes:
        return {"id": template_id, "name": row["name"], "start_time": row["start_time"], "end_time": row["end_time"], "notes": row.get("notes")}
    changes["updated_at"] = datetime.utcnow().isoformat()
    try:
        updated = supabase.table("shift_templates").update(changes).eq("id", template_id).execute()
    except Exception as error:
        if "duplicate key" in str(error).lower() or "unique constraint" in str(error).lower():
            raise HTTPException(status_code=409, detail="A shift with this name already exists")
        raise
    if not updated.data:
        raise HTTPException(status_code=500, detail="Failed to update shift")
    row = updated.data[0]
    _audit(current_user, "shift_template_updated", f"Updated shift template {row['name']}.", template_id, {"fields": list(changes)})
    return {"id": template_id, "name": row["name"], "start_time": row["start_time"], "end_time": row["end_time"], "notes": row.get("notes")}


@router.delete("/shift-templates/{template_id}")
async def delete_shift_template(template_id: str, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    row = await _get_template(template_id)
    supabase.table("shift_templates").delete().eq("id", template_id).execute()
    _audit(current_user, "shift_template_deleted", f"Deleted shift template {row['name']}.", template_id, {"name": row["name"]})
    return {"id": template_id, "message": "Shift template deleted"}


@router.post("/shifts")
async def create_shift_allocation(allocation: ShiftAllocationCreate, current_user: dict = Depends(require_role("lead", "manager", "hr", "director", "super_admin"))):
    employee = await _get_employee(allocation.employee_id)
    await _check_allocation_scope(current_user, employee)
    template = await _get_template(allocation.shift_template_id)
    existing = supabase.table("shifts").select("id,shift_date,status").eq("employee_id", employee["id"]).in_("status", ["pending", "approved"]).execute()
    today = datetime.utcnow().date().isoformat()
    if any(not row.get("shift_date") or row.get("shift_date") >= today for row in (existing.data or [])):
        raise HTTPException(status_code=409, detail="This employee already has a pending or active shift allocation")
    creator = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    if not creator:
        raise HTTPException(status_code=404, detail="Current user not found")
    role = current_user.get("role")
    status = "approved" if role in {"director", "super_admin"} else "pending"
    approver = str(creator["id"]) if status == "approved" else None
    now = datetime.utcnow().isoformat()
    row = {
        "name": template["name"], "employee_id": employee["id"], "employee_name": employee.get("name"),
        "employee_email": employee.get("email"), "shift_type": template["name"], "shift_date": None,
        "shift_template_id": template["id"],
        "start_time": template["start_time"], "end_time": template["end_time"], "notes": allocation.notes,
        "status": status, "created_by": str(creator["id"]), "created_by_name": current_user.get("name"),
        "approved_by": approver, "approved_by_name": current_user.get("name") if approver else None,
        "rejection_reason": None, "created_at": now, "updated_at": now,
    }
    try:
        inserted = supabase.table("shifts").insert(row).execute()
    except Exception as error:
        if "duplicate key" in str(error).lower() or "unique constraint" in str(error).lower():
            raise HTTPException(status_code=409, detail="This employee already has a pending or active shift allocation")
        raise
    if not inserted.data:
        raise HTTPException(status_code=500, detail="Failed to allocate shift")
    result = await _shift_to_public(inserted.data[0])
    _audit(current_user, "shift_allocated", f"Allocated {template['name']} to {employee.get('name')} ({status}).", result["id"], {"employee_id": employee["uid"], "template": template["name"], "status": status})
    return result


@router.get("/shifts")
async def get_shifts(status: Optional[str] = None, employee_id: Optional[str] = None, shift_date: Optional[str] = None,
                     start_date: Optional[str] = None, end_date: Optional[str] = None,
                     current_user: dict = Depends(get_current_user)):
    query = supabase.table("shifts").select("*").not_.is_("employee_id", "null").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if employee_id:
        employee = await SupabaseHelper.get_user_row_by_firebase_uid(employee_id)
        if not employee:
            return {"shifts": []}
        query = query.eq("employee_id", str(employee["id"]))
    if shift_date:
        query = query.or_(f"shift_date.eq.{shift_date},shift_date.is.null")
    rows = query.execute().data or []
    role = current_user.get("role")
    user_uid = str(current_user.get("uid"))
    user_map = await SupabaseHelper.get_public_user_map()
    descendants = _get_descendants(user_uid, user_map) if role in {"manager", "lead"} else set()
    results = []
    for row in rows:
        public = await _shift_to_public(row, user_map)
        date = public.get("shift_date")
        if start_date and date and date < start_date:
            continue
        if end_date and date and date > end_date:
            continue
        target = public.get("employee_id")
        creator = public.get("created_by")
        if role in {"hr", "director", "super_admin"} or target == user_uid or creator == user_uid or target in descendants:
            results.append(public)
    return {"shifts": results}


@router.get("/shifts/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    pending = supabase.table("shifts").select("*").not_.is_("employee_id", "null").eq("status", "pending").order("created_at", desc=True).execute().data or []
    user_map = await SupabaseHelper.get_public_user_map()
    result = []
    for row in pending:
        if await _can_approve(current_user, row, user_map):
            result.append(await _shift_to_public(row, user_map))
    return {"shifts": result}


@router.patch("/shifts/{shift_id}/approve")
async def approve_shift(shift_id: str, current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    allocation = await _get_allocation(shift_id)
    if allocation.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending allocations can be approved")
    user_map = await SupabaseHelper.get_public_user_map()
    if not await _can_approve(current_user, allocation, user_map):
        raise HTTPException(status_code=403, detail="You cannot approve this allocation")
    approver = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    result = supabase.table("shifts").update({"status": "approved", "approved_by": str(approver["id"]) if approver else None,
        "approved_by_name": current_user.get("name"), "rejection_reason": None, "updated_at": datetime.utcnow().isoformat()}).eq("id", shift_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to approve allocation")
    public = await _shift_to_public(result.data[0], user_map)
    _audit(current_user, "shift_approved", f"Approved shift allocation for {public.get('employee_name')}.", shift_id, {"employee_id": public.get("employee_id")})
    return public


@router.patch("/shifts/{shift_id}/reject")
async def reject_shift(shift_id: str, rejection_reason: str = Body(..., embed=True), current_user: dict = Depends(require_role("manager", "director", "super_admin"))):
    reason = rejection_reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    allocation = await _get_allocation(shift_id)
    if allocation.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending allocations can be rejected")
    user_map = await SupabaseHelper.get_public_user_map()
    if not await _can_approve(current_user, allocation, user_map):
        raise HTTPException(status_code=403, detail="You cannot reject this allocation")
    approver = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    result = supabase.table("shifts").update({"status": "rejected", "approved_by": str(approver["id"]) if approver else None,
        "approved_by_name": current_user.get("name"), "rejection_reason": reason, "updated_at": datetime.utcnow().isoformat()}).eq("id", shift_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to reject allocation")
    public = await _shift_to_public(result.data[0], user_map)
    _audit(current_user, "shift_rejected", f"Rejected shift allocation for {public.get('employee_name')}.", shift_id, {"reason": reason})
    return public


@router.patch("/shifts/{shift_id}")
async def update_shift_allocation(shift_id: str, update: ShiftAllocationUpdate, current_user: dict = Depends(require_role("lead", "manager", "hr", "director", "super_admin"))):
    existing = await _get_allocation(shift_id)
    role = current_user.get("role")
    is_admin = role in {"hr", "director", "super_admin"}
    creator = await SupabaseHelper.get_public_user_by_id(existing.get("created_by")) if existing.get("created_by") else None
    if not is_admin and (not creator or creator.get("uid") != current_user.get("uid") or existing.get("status") != "pending"):
        raise HTTPException(status_code=403, detail="You can only edit your own pending allocations")
    employee_uid = update.employee_id or (await SupabaseHelper.get_public_user_by_id(existing["employee_id"])).get("uid")
    employee = await _get_employee(employee_uid)
    await _check_allocation_scope(current_user, employee)
    if str(employee["id"]) != str(existing["employee_id"]):
        duplicates = supabase.table("shifts").select("id,shift_date").eq("employee_id", employee["id"]).in_("status", ["pending", "approved"]).execute()
        today = datetime.utcnow().date().isoformat()
        if any(not row.get("shift_date") or row.get("shift_date") >= today for row in (duplicates.data or [])):
            raise HTTPException(status_code=409, detail="This employee already has a pending or active shift allocation")
    template_id = update.shift_template_id
    template = await _get_template(template_id) if template_id else None
    changes: Dict[str, Any] = {"employee_id": employee["id"], "employee_name": employee.get("name"),
        "employee_email": employee.get("email"), "updated_at": datetime.utcnow().isoformat()}
    if template:
        changes.update({"name": template["name"], "shift_type": template["name"], "shift_template_id": template["id"], "start_time": template["start_time"], "end_time": template["end_time"]})
    if update.notes is not None:
        changes["notes"] = update.notes
    changes.update({"status": "approved" if role in {"director", "super_admin"} else "pending",
        "approved_by": None, "approved_by_name": None, "rejection_reason": None})
    if role in {"director", "super_admin"}:
        approver = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        changes.update({"approved_by": str(approver["id"]) if approver else None, "approved_by_name": current_user.get("name")})
    try:
        result = supabase.table("shifts").update(changes).eq("id", shift_id).execute()
    except Exception as error:
        if "duplicate key" in str(error).lower() or "unique constraint" in str(error).lower():
            raise HTTPException(status_code=409, detail="This employee already has a pending or active shift allocation")
        raise
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update allocation")
    public = await _shift_to_public(result.data[0])
    _audit(current_user, "shift_allocation_updated", f"Updated shift allocation for {public.get('employee_name')}.", shift_id, {"fields": list(changes)})
    return public


@router.delete("/shifts/{shift_id}")
async def delete_shift_allocation(shift_id: str, current_user: dict = Depends(require_role("lead", "manager", "hr", "director", "super_admin"))):
    allocation = await _get_allocation(shift_id)
    role = current_user.get("role")
    if role not in {"hr", "director", "super_admin"}:
        creator = await SupabaseHelper.get_public_user_by_id(allocation.get("created_by")) if allocation.get("created_by") else None
        if not creator or creator.get("uid") != current_user.get("uid") or allocation.get("status") != "pending":
            raise HTTPException(status_code=403, detail="You can only delete your own pending allocations")
    public = await _shift_to_public(allocation)
    supabase.table("shifts").delete().eq("id", shift_id).execute()
    _audit(current_user, "shift_allocation_deleted", f"Deleted shift allocation for {public.get('employee_name')}.", shift_id, {"employee_id": public.get("employee_id")})
    return {"id": shift_id, "message": "Shift allocation deleted"}
