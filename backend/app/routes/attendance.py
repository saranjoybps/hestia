from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, require_role, supabase
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/attendance", tags=["Attendance"])
try:
    LOCAL_TZ = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    # Windows Python installations may not include an IANA timezone database.
    # Kolkata uses a fixed UTC+05:30 offset and does not observe daylight saving.
    LOCAL_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
READ_ALL_ROLES = {"hr", "director", "super_admin"}
MANUAL_ROLES = {"lead", "manager", "hr", "director", "super_admin"}
REVIEWER_CREATORS = {
    "lead": {"employee"},
    "manager": {"employee", "lead"},
    "director": {"employee", "lead", "manager", "hr"},
    "super_admin": {"director"},
}
ALLOWED_STATUSES = {"present", "absent", "half_day", "leave", "holiday", "week_off", "comp_off"}


def _user_ids(user: Dict[str, Any]) -> Set[str]:
    return {str(value) for value in (user.get("uid"), user.get("id")) if value}


def _descendants(roots: Set[str], user_map: Dict[str, Dict[str, Any]]) -> Set[str]:
    found: Set[str] = set()
    frontier = set(roots)
    while frontier:
        next_frontier: Set[str] = set()
        for key, row in user_map.items():
            identifiers = {str(row.get("id") or ""), str(row.get("uid") or "")}
            identifiers.discard("")
            if identifiers & found or identifiers & roots:
                continue
            if str(row.get("manager_id") or "") in frontier or str(row.get("lead_id") or "") in frontier:
                found.update(identifiers)
                next_frontier.update(identifiers)
        frontier = next_frontier
    return found


async def _scope(current_user: Dict[str, Any]) -> tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Set[str]]:
    role = current_user.get("role")
    user_map = await SupabaseHelper.get_public_user_map()
    me = next((row for row in user_map.values() if row.get("uid") == current_user.get("uid")), None)
    if not me:
        raise HTTPException(status_code=404, detail="Current user not found")
    if role in READ_ALL_ROLES:
        allowed = {str(row.get("id")) for row in user_map.values() if row.get("id")}
    elif role in {"lead", "manager"}:
        scope = _descendants(_user_ids(me), user_map)
        allowed = {str(row.get("id")) for row in user_map.values() if str(row.get("uid")) in scope and row.get("id")}
        allowed.add(str(me["id"]))
    else:
        allowed = {str(me["id"])}
    return user_map, list(user_map.values()), allowed


def _public_status(value: Optional[str]) -> str:
    return {"half_day": "half-day", "leave": "on-leave", "week_off": "week-off", "comp_off": "comp-off"}.get(value or "", value or "present")


def _db_status(value: str) -> str:
    normalized = value.replace("-", "_")
    aliases = {"on_leave": "leave", "halfday": "half_day"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported attendance status")
    return normalized


def _iso(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _time_display(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    raw = str(value)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return raw[:5]


def _manual_datetime(day: str, value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(f"{day} {value}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=422, detail="Attendance times must use HH:MM format")


def _elapsed_hours(start: Any, end: Any) -> float:
    if not start or not end:
        return 0.0
    start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(str(start).replace("Z", "+00:00"))
    end_dt = end if isinstance(end, datetime) else datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    if start_dt.tzinfo and end_dt.tzinfo:
        seconds = (end_dt - start_dt).total_seconds()
    else:
        seconds = (end_dt.replace(tzinfo=None) - start_dt.replace(tzinfo=None)).total_seconds()
    return round(max(0, seconds) / 3600, 2)


def _public_row(row: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    employee = user_map.get(str(row.get("user_id")), {})
    marked_by = user_map.get(str(row.get("marked_by")), {}) if row.get("marked_by") else {}
    reviewer = user_map.get(str(row.get("reviewed_by")), {}) if row.get("reviewed_by") else {}
    return {
        "id": str(row.get("id")), "userId": employee.get("uid"), "userName": employee.get("name"),
        "date": str(row.get("date")), "checkIn": _time_display(row.get("check_in_time")),
        "checkOut": _time_display(row.get("check_out_time")), "status": _public_status(row.get("status")),
        "workHours": float(row.get("total_hours") or _elapsed_hours(row.get("check_in_time"), row.get("check_out_time"))),
        "notes": row.get("notes") or "", "markedBy": marked_by.get("uid"),
        "markedByName": marked_by.get("name"), "approvalStatus": row.get("approval_status") or "approved",
        "reviewedBy": reviewer.get("uid"), "reviewedByName": reviewer.get("name"),
        "reviewReason": row.get("review_reason"), "correctionReason": row.get("correction_reason"),
        "pendingStatus": _public_status(row.get("pending_status")),
        "pendingCheckIn": row.get("pending_check_in_time"), "pendingCheckOut": row.get("pending_check_out_time"),
        "pendingNotes": row.get("pending_notes"),
        "shiftAllocationId": row.get("shift_allocation_id"), "createdAt": _iso(row.get("created_at")),
        "isLeaveDerived": bool(row.get("is_leave_derived")),
    }


def _leave_attendance(leave: Dict[str, Any], day: str, user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    row = {"user_id": leave.get("user_id"), "date": day, "status": "leave", "approval_status": "approved",
           "notes": leave.get("reason") or "Approved leave", "marked_by": leave.get("approved_by"),
           "is_leave_derived": True, "id": f"leave:{leave.get('id')}:{day}"}
    return _public_row(row, user_map)


async def _target_user(uid: str, user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    employee = next((row for row in user_map.values() if row.get("uid") == uid), None)
    if not employee or not employee.get("id"):
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


async def _assert_target_scope(current_user: Dict[str, Any], employee: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> None:
    role = current_user.get("role")
    if str(employee.get("id")) == str(current_user.get("id")):
        return
    if role in READ_ALL_ROLES:
        return
    if role in {"lead", "manager"}:
        if str(employee.get("uid")) in _descendants(_user_ids(current_user), user_map):
            return
    raise HTTPException(status_code=403, detail="You can only access attendance within your authorized scope")


def _audit(actor: Dict[str, Any], action: str, row: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    log_audit_event(actor_id=actor.get("uid"), actor_name=actor.get("name"), actor_email=actor.get("email"),
                    module="attendance", action=action, description=f"{action.replace('_', ' ').capitalize()} for {row.get('user_name') or row.get('user_id')} on {row.get('date')}.",
                    result="success", target_type="attendance", target_id=str(row.get("id")), metadata=metadata)


def _local_now() -> datetime:
    return datetime.now(LOCAL_TZ).replace(tzinfo=None, second=0, microsecond=0)


async def _approved_shift(employee_id: str, day: str) -> Optional[Dict[str, Any]]:
    rows = supabase.table("shifts").select("*").eq("employee_id", employee_id).eq("status", "approved").or_(f"shift_date.eq.{day},shift_date.is.null").order("created_at", desc=True).execute().data or []
    return next((row for row in rows if row.get("shift_date") == day), None) or next((row for row in rows if not row.get("shift_date")), None)


async def _scope_rows(current_user: Dict[str, Any], start_date: Optional[str], end_date: Optional[str]) -> tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Set[str]]:
    user_map, _, allowed = await _scope(current_user)
    query = supabase.table("attendance").select("*").order("date", desc=True)
    if allowed:
        query = query.in_("user_id", list(allowed))
    else:
        return user_map, [], allowed
    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)
    rows = query.execute().data or []
    return user_map, rows, allowed


async def _roster_data(day: str, current_user: Dict[str, Any], user_map: Dict[str, Dict[str, Any]], allowed: Set[str]) -> List[Dict[str, Any]]:
    team = [row for row in user_map.values() if row.get("id") and str(row["id"]) in allowed and row.get("uid") != current_user.get("uid") and row.get("status") != "inactive"]
    ids = [str(row["id"]) for row in team]
    shifts = supabase.table("shifts").select("*").in_("employee_id", ids).eq("status", "approved").or_(f"shift_date.eq.{day},shift_date.is.null").execute().data or [] if ids else []
    attendance = supabase.table("attendance").select("*").in_("user_id", ids).eq("date", day).execute().data or [] if ids else []
    leaves = supabase.table("leaves").select("*").in_("user_id", ids).eq("status", "approved").lte("start_date", day).gte("end_date", day).execute().data or [] if ids else []
    result = []
    for employee in team:
        matching = [row for row in shifts if str(row.get("employee_id")) == str(employee["id"])]
        shift = next((row for row in matching if row.get("shift_date") == day), None) or next((row for row in matching if not row.get("shift_date")), None)
        existing = next((row for row in attendance if str(row.get("user_id")) == str(employee["id"])), None)
        leave = next((row for row in leaves if str(row.get("user_id")) == str(employee["id"])), None)
        if existing and existing.get("approval_status") == "rejected":
            existing = None
        result.append({"uid": employee.get("uid"), "name": employee.get("name"), "email": employee.get("email"), "department": employee.get("department"),
                       "shift": {"id": str(shift.get("id")), "name": shift.get("name"), "start_time": shift.get("start_time"), "end_time": shift.get("end_time")} if shift else None,
                       "attendance": _public_row(existing, user_map) if existing else (_leave_attendance(leave, day, user_map) if leave else None)})
    return result


async def _pending_data(role: str, user_map: Dict[str, Dict[str, Any]], allowed: Set[str]) -> List[Dict[str, Any]]:
    if role not in {"lead", "manager", "director", "super_admin"}:
        return []
    candidates = supabase.table("attendance").select("*").eq("approval_status", "pending").order("created_at", desc=True).execute().data or []
    return [_public_row(row, user_map) for row in candidates
            if user_map.get(str(row.get("marked_by")), {}).get("role") in REVIEWER_CREATORS.get(role, set())
            and str(row.get("user_id")) in allowed]


@router.get("/dashboard")
async def attendance_dashboard(start_date: str = Query(...), end_date: str = Query(...), day: str = Query(...), current_user: dict = Depends(get_current_user)):
    user_map, rows, allowed = await _scope_rows(current_user, start_date, end_date)
    me = next((row for row in user_map.values() if row.get("uid") == current_user.get("uid")), {})
    role = current_user.get("role")
    employee_rows = [row for row in user_map.values() if str(row.get("id")) in allowed and row.get("status") != "inactive"]
    team = employee_rows if role in {"lead", "manager", "hr", "director", "super_admin"} else []
    roster = await _roster_data(day, current_user, user_map, allowed) if role in MANUAL_ROLES else []
    records = [_public_row(row, user_map) for row in rows]
    if allowed:
        approved_leaves = supabase.table("leaves").select("*").in_("user_id", list(allowed)).eq("status", "approved").lte("start_date", end_date).gte("end_date", start_date).execute().data or []
        occupied = {(str(row.get("user_id")), str(row.get("date"))) for row in rows if row.get("approval_status") != "rejected"}
        for leave in approved_leaves:
            leave_start = max(start_date, str(leave.get("start_date")))
            leave_end = min(end_date, str(leave.get("end_date")))
            cursor = date.fromisoformat(leave_start)
            last = date.fromisoformat(leave_end)
            while cursor <= last:
                leave_day = cursor.isoformat()
                key = (str(leave.get("user_id")), leave_day)
                if key not in occupied:
                    records.append(_leave_attendance(leave, leave_day, user_map))
                cursor += timedelta(days=1)
        records.sort(key=lambda item: (item.get("date", ""), item.get("userName", "")), reverse=True)
    pending = await _pending_data(role, user_map, allowed)
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    open_rows = supabase.table("attendance").select("*").eq("user_id", str(me.get("id"))).is_("check_out_time", "null").gte("date", yesterday).lte("date", day).order("date", desc=True).limit(1).execute().data or [] if me.get("id") else []
    self_record = next((record for record in records if record.get("userId") == current_user.get("uid") and record.get("date") == day), None)
    if not self_record and open_rows:
        self_record = _public_row(open_rows[0], user_map)
    return {"user": {"uid": current_user.get("uid"), "name": current_user.get("name"), "role": role},
            "team": [{"uid": row.get("uid"), "name": row.get("name"), "email": row.get("email"), "department": row.get("department"), "designation": row.get("designation")} for row in team if row.get("uid") != current_user.get("uid")],
            "records": records, "pending": pending, "roster": roster,
            "selfShift": await _approved_shift(str(me.get("id")), day) if me.get("id") else None,
            "selfRecord": self_record}


@router.get("/")
async def get_attendance(start_date: Optional[str] = None, end_date: Optional[str] = None, user_id: Optional[str] = None,
                         attendance_status: Optional[str] = Query(None, alias="status"), current_user: dict = Depends(get_current_user)):
    user_map, rows, allowed = await _scope_rows(current_user, start_date, end_date)
    requested_ids = set(allowed)
    if user_id:
        employee = await _target_user(user_id, user_map)
        await _assert_target_scope(current_user, employee, user_map)
        requested_ids = {str(employee.get("id"))}
        rows = [row for row in rows if str(row.get("user_id")) == str(employee.get("id"))]
    if attendance_status:
        wanted = _db_status(attendance_status)
        rows = [row for row in rows if row.get("status") == wanted]
    records = [_public_row(row, user_map) for row in rows]
    if start_date and end_date and (not attendance_status or _db_status(attendance_status) == "leave") and requested_ids:
        leaves = supabase.table("leaves").select("*").in_("user_id", list(requested_ids)).eq("status", "approved").lte("start_date", end_date).gte("end_date", start_date).execute().data or []
        occupied = {(str(row.get("user_id")), str(row.get("date"))) for row in rows if row.get("approval_status") != "rejected"}
        for leave in leaves:
            cursor = date.fromisoformat(max(start_date, str(leave.get("start_date"))))
            last = date.fromisoformat(min(end_date, str(leave.get("end_date"))))
            while cursor <= last:
                leave_day = cursor.isoformat()
                if (str(leave.get("user_id")), leave_day) not in occupied:
                    records.append(_leave_attendance(leave, leave_day, user_map))
                cursor += timedelta(days=1)
        records.sort(key=lambda item: (item.get("date", ""), item.get("userName", "")), reverse=True)
    return records


@router.get("/pending-approvals")
async def pending_approvals(current_user: dict = Depends(require_role("lead", "manager", "director", "super_admin"))):
    user_map, _, allowed = await _scope(current_user)
    return await _pending_data(current_user.get("role"), user_map, allowed)


@router.get("/roster")
async def attendance_roster(day: str = Query(...), current_user: dict = Depends(require_role(*MANUAL_ROLES))):
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format")
    user_map, _, allowed = await _scope(current_user)
    return await _roster_data(day, current_user, user_map, allowed)


@router.post("/check-in", status_code=201)
async def check_in(current_user: dict = Depends(get_current_user)):
    now = _local_now()
    employee = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    shift = await _approved_shift(str(employee["id"]), now.date().isoformat())
    if not shift:
        raise HTTPException(status_code=409, detail="No approved shift is assigned for today")
    existing = supabase.table("attendance").select("*").eq("user_id", str(employee["id"])).eq("date", now.date().isoformat()).execute()
    if existing.data and existing.data[0].get("approval_status") != "rejected":
        raise HTTPException(status_code=409, detail="Attendance has already been started for today")
    payload = {"user_id": str(employee["id"]), "date": now.date().isoformat(), "status": "present", "check_in_time": now.isoformat(),
               "check_out_time": None, "total_hours": 0, "marked_by": str(employee["id"]), "shift_allocation_id": str(shift["id"]), "approval_status": "approved", "reviewed_by": None, "review_reason": None}
    try:
        inserted = supabase.table("attendance").update(payload).eq("id", str(existing.data[0]["id"])).execute() if existing.data else supabase.table("attendance").insert(payload).execute()
    except Exception as error:
        if "23505" in str(error) or "duplicate key" in str(error).lower():
            raise HTTPException(status_code=409, detail="Attendance has already been started for today")
        raise
    if not inserted.data:
        raise HTTPException(status_code=500, detail="Unable to start attendance")
    user_map = await SupabaseHelper.get_public_user_map()
    result = _public_row(inserted.data[0], user_map)
    _audit(current_user, "attendance_checked_in", inserted.data[0], {"date": result["date"], "shift_id": shift["id"]})
    return result


@router.post("/check-out")
async def check_out(current_user: dict = Depends(get_current_user)):
    employee = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
    now = _local_now()
    rows = supabase.table("attendance").select("*").eq("user_id", str(employee["id"])).is_("check_out_time", "null").order("date", desc=True).limit(2).execute().data or []
    row = next((item for item in rows if item.get("date") in {now.date().isoformat(), (now.date() - timedelta(days=1)).isoformat()} and item.get("check_in_time")), None)
    if not row:
        raise HTTPException(status_code=409, detail="There is no open check-in to close")
    start_dt = datetime.fromisoformat(str(row["check_in_time"]).replace("Z", "+00:00"))
    local_start = start_dt.replace(tzinfo=LOCAL_TZ) if start_dt.tzinfo is None else start_dt.astimezone(LOCAL_TZ)
    if now < local_start.replace(tzinfo=None):
        raise HTTPException(status_code=422, detail="Check-out time must be after check-in")
    changes = {"check_out_time": now.isoformat(), "total_hours": _elapsed_hours(row.get("check_in_time"), now.isoformat()), "updated_at": now.isoformat()}
    updated = supabase.table("attendance").update(changes).eq("id", str(row["id"])).execute()
    user_map = await SupabaseHelper.get_public_user_map()
    result = _public_row(updated.data[0], user_map)
    _audit(current_user, "attendance_checked_out", updated.data[0], {"date": result["date"], "work_hours": result["workHours"]})
    return result


@router.post("/self-request", status_code=201)
async def request_past_attendance(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Submit a missed, past-day punch for review by the employee's hierarchy."""
    day = str(payload.get("date") or "")
    try:
        parsed_day = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format")
    today = _local_now().date()
    if parsed_day >= today:
        raise HTTPException(status_code=422, detail="Use check-in for today; past attendance requests must be for an earlier date")

    user_map, _, _ = await _scope(current_user)
    employee = next((row for row in user_map.values() if row.get("uid") == current_user.get("uid")), None)
    if not employee or not employee.get("id"):
        raise HTTPException(status_code=404, detail="Employee not found")
    shift = await _approved_shift_for_day(str(employee["id"]), day)
    if not shift:
        raise HTTPException(status_code=409, detail="An approved shift is required for past attendance")

    check_in = str(payload.get("check_in") or payload.get("checkIn") or "").strip()
    check_out = str(payload.get("check_out") or payload.get("checkOut") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not check_in or not check_out:
        raise HTTPException(status_code=422, detail="Both check-in and check-out times are required")
    if not reason:
        raise HTTPException(status_code=422, detail="A reason is required for a past attendance request")
    if len(reason) > 1000:
        raise HTTPException(status_code=422, detail="Reason must be 1000 characters or fewer")
    start = _manual_datetime(day, check_in)
    end = _manual_datetime(day, check_out)
    if end <= start:
        if str(shift.get("end_time", "")) < str(shift.get("start_time", "")):
            end += timedelta(days=1)
        else:
            raise HTTPException(status_code=422, detail="Check-out must be after check-in")

    existing = supabase.table("attendance").select("*").eq("user_id", str(employee["id"])).eq("date", day).execute().data or []
    if existing and (existing[0].get("approval_status") or "approved") != "rejected":
        raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date")
    record = {
        "user_id": str(employee["id"]), "date": day, "status": "present",
        "check_in_time": None, "check_out_time": None, "total_hours": 0,
        "notes": "", "marked_by": str(employee["id"]), "shift_allocation_id": str(shift["id"]),
        "approval_status": "pending", "pending_status": "present",
        "pending_check_in_time": check_in, "pending_check_out_time": check_out,
        "pending_notes": reason, "correction_reason": reason, "reviewed_by": None,
        "review_reason": None, "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        saved = supabase.table("attendance").update(record).eq("id", str(existing[0]["id"])).execute() if existing else supabase.table("attendance").insert(record).execute()
    except Exception as error:
        if "23505" in str(error) or "duplicate key" in str(error).lower():
            raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date")
        raise
    if not saved.data:
        raise HTTPException(status_code=500, detail="Unable to submit past attendance request")
    result = _public_row(saved.data[0], user_map)
    _audit(current_user, "attendance_past_request_submitted", saved.data[0], {"reason": reason, "shift_id": shift["id"]})
    return result


async def _approved_shift_for_day(employee_id: str, day: str) -> Optional[Dict[str, Any]]:
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format")
    shift = await _approved_shift(employee_id, day)
    return shift


@router.post("/", status_code=201)
async def create_manual_attendance(payload: dict = Body(...), current_user: dict = Depends(require_role(*MANUAL_ROLES))):
    day = str(payload.get("date") or "")
    try:
        parsed_day = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format")
    if parsed_day > _local_now().date():
        raise HTTPException(status_code=422, detail="Attendance cannot be entered for a future date")
    user_map, _, allowed = await _scope(current_user)
    employee = await _target_user(str(payload.get("user_id") or payload.get("userId") or ""), user_map)
    await _assert_target_scope(current_user, employee, user_map)
    if str(employee["id"]) not in allowed:
        raise HTTPException(status_code=403, detail="Employee is outside your attendance scope")
    if str(employee["id"]) == str(current_user.get("id")):
        raise HTTPException(status_code=403, detail="Use self check-in and check-out for your own attendance")
    shift = await _approved_shift_for_day(str(employee["id"]), day)
    attendance_status = _db_status(str(payload.get("status") or "present"))
    if attendance_status in {"present", "absent", "half_day"} and not shift:
        raise HTTPException(status_code=409, detail="An approved shift is required for work attendance")
    reason = str(payload.get("reason") or payload.get("notes") or "").strip()
    if len(reason) > 1000:
        raise HTTPException(status_code=422, detail="Notes must be 1000 characters or fewer")
    if attendance_status in {"leave", "holiday", "week_off", "comp_off"} and not reason:
        raise HTTPException(status_code=422, detail="Add a note explaining this attendance exception")
    existing = supabase.table("attendance").select("*").eq("user_id", str(employee["id"])).eq("date", day).execute()
    if existing.data and (existing.data[0].get("approval_status") or "approved") != "rejected":
        raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date")
    start = payload.get("check_in") or payload.get("checkIn")
    end = payload.get("check_out") or payload.get("checkOut")
    if attendance_status == "present" and (not start or not end):
        raise HTTPException(status_code=422, detail="Present attendance requires both check-in and check-out times")
    check_in_dt = _manual_datetime(day, start)
    check_out_dt = _manual_datetime(day, end)
    if check_in_dt and check_out_dt and check_out_dt <= check_in_dt:
        if shift and str(shift.get("end_time", "")) < str(shift.get("start_time", "")):
            check_out_dt += timedelta(days=1)
        else:
            raise HTTPException(status_code=422, detail="Check-out must be after check-in")
    role = current_user.get("role")
    # Directors are the final operational approvers for team attendance.
    # Their own entries should be final, since nobody can review their own request.
    approval_status = "approved" if role in {"director", "super_admin"} else "pending"
    record = {"user_id": str(employee["id"]), "date": day, "status": attendance_status,
              "check_in_time": check_in_dt.isoformat() if check_in_dt else None, "check_out_time": check_out_dt.isoformat() if check_out_dt else None,
              "total_hours": _elapsed_hours(check_in_dt, check_out_dt), "notes": reason, "marked_by": str(current_user.get("id")),
              "shift_allocation_id": str(shift["id"]) if shift else None, "approval_status": approval_status,
              "is_week_off": attendance_status == "week_off", "is_comp_off": attendance_status == "comp_off",
              "reviewed_by": str(current_user.get("id")) if approval_status == "approved" else None,
              "pending_status": attendance_status, "pending_check_in_time": start, "pending_check_out_time": end, "pending_notes": reason}
    try:
        if existing.data:
            response = supabase.table("attendance").update(record).eq("id", str(existing.data[0]["id"])).execute()
        else:
            response = supabase.table("attendance").insert(record).execute()
    except Exception as error:
        if "23505" in str(error) or "duplicate key" in str(error).lower():
            raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date")
        raise
    if not response.data:
        raise HTTPException(status_code=500, detail="Unable to save attendance")
    row = response.data[0]
    _audit(current_user, "attendance_manual_submitted", row, {"status": attendance_status, "approval_status": approval_status, "reason": reason})
    return _public_row(row, user_map)


@router.put("/{attendance_id}")
async def request_attendance_correction(attendance_id: str, payload: dict = Body(...), current_user: dict = Depends(require_role(*MANUAL_ROLES))):
    rows = supabase.table("attendance").select("*").eq("id", attendance_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    row = rows[0]
    if (row.get("approval_status") or "approved") == "pending":
        raise HTTPException(status_code=409, detail="This attendance record already has a pending review")
    user_map, _, allowed = await _scope(current_user)
    employee = user_map.get(str(row.get("user_id")))
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    await _assert_target_scope(current_user, employee, user_map)
    if str(employee.get("id")) not in allowed or str(employee.get("id")) == str(current_user.get("id")):
        raise HTTPException(status_code=403, detail="You cannot correct attendance outside your reporting scope")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A correction reason is required")
    status_value = _db_status(str(payload.get("status") or row.get("status")))
    shift = await _approved_shift_for_day(str(employee["id"]), str(row.get("date")))
    if status_value in {"present", "absent", "half_day"} and not shift:
        raise HTTPException(status_code=409, detail="An approved shift is required for work attendance")
    role = current_user.get("role")
    if "check_in" in payload or "checkIn" in payload:
        raw_in = payload.get("check_in", payload.get("checkIn"))
        requested_in = str(raw_in).strip() if raw_in else None
    else:
        requested_in = _time_display(row.get("check_in_time"))
    if "check_out" in payload or "checkOut" in payload:
        raw_out = payload.get("check_out", payload.get("checkOut"))
        requested_out = str(raw_out).strip() if raw_out else None
    else:
        requested_out = _time_display(row.get("check_out_time"))
    if status_value == "present" and (not requested_in or not requested_out):
        raise HTTPException(status_code=422, detail="Present attendance requires both check-in and check-out times")
    start_dt = _manual_datetime(str(row.get("date")), requested_in)
    end_dt = _manual_datetime(str(row.get("date")), requested_out)
    if start_dt and end_dt and end_dt <= start_dt:
        if str(shift.get("end_time", "")) < str(shift.get("start_time", "")):
            end_dt += timedelta(days=1)
        else:
            raise HTTPException(status_code=422, detail="Check-out must be after check-in")
    update = {"pending_status": status_value, "pending_check_in_time": requested_in,
              "pending_check_out_time": requested_out,
              "pending_notes": payload.get("notes", row.get("notes") or ""), "correction_reason": reason,
              "approval_status": "approved" if role in {"director", "super_admin"} else "pending", "marked_by": str(current_user.get("id")),
              "reviewed_by": str(current_user.get("id")) if role in {"director", "super_admin"} else None, "review_reason": None,
              "updated_at": datetime.utcnow().isoformat()}
    if role in {"director", "super_admin"}:
        immediate_in = _manual_datetime(str(row.get("date")), requested_in)
        immediate_out = _manual_datetime(str(row.get("date")), requested_out)
        if immediate_in and immediate_out and immediate_out <= immediate_in:
            immediate_out += timedelta(days=1)
        update.update({"status": status_value, "check_in_time": immediate_in.isoformat() if immediate_in else None,
                       "check_out_time": immediate_out.isoformat() if immediate_out else None,
                       "total_hours": _elapsed_hours(immediate_in, immediate_out), "notes": update["pending_notes"],
                       "is_week_off": status_value == "week_off", "is_comp_off": status_value == "comp_off"})
    changed = supabase.table("attendance").update(update).eq("id", attendance_id).eq("approval_status", row.get("approval_status") or "approved").execute()
    if not changed.data:
        raise HTTPException(status_code=409, detail="Attendance was updated by another request; reload and try again")
    _audit(current_user, "attendance_correction_submitted", row, {
        "reason": reason, "approval_status": update["approval_status"],
        "previous": {"status": row.get("status"), "check_in": _time_display(row.get("check_in_time")), "check_out": _time_display(row.get("check_out_time")), "notes": row.get("notes")},
        "requested": {"status": status_value, "check_in": requested_in, "check_out": requested_out, "notes": update["pending_notes"]},
    })
    return _public_row(changed.data[0], user_map)


async def _review_attendance(attendance_id: str, decision: str, reason: Optional[str], current_user: Dict[str, Any]) -> Dict[str, Any]:
    result = supabase.table("attendance").select("*").eq("id", attendance_id).execute().data or []
    if not result:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    row = result[0]
    if row.get("approval_status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending attendance can be reviewed")
    user_map, _, allowed = await _scope(current_user)
    creator = user_map.get(str(row.get("marked_by")), {})
    role = current_user.get("role")
    employee = user_map.get(str(row.get("user_id")), {})
    if creator.get("role") not in REVIEWER_CREATORS.get(role, set()) or str(row.get("user_id")) not in allowed:
        raise HTTPException(status_code=403, detail="You cannot review this attendance request")
    now = datetime.utcnow().isoformat()
    update: Dict[str, Any] = {"approval_status": decision, "reviewed_by": str(current_user.get("id")), "review_reason": reason, "updated_at": now}
    if decision == "approved":
        pending_in, pending_out = row.get("pending_check_in_time"), row.get("pending_check_out_time")
        start = datetime.fromisoformat(f"{row['date']}T{pending_in}") if pending_in else None
        end = datetime.fromisoformat(f"{row['date']}T{pending_out}") if pending_out else None
        if start and end and end <= start:
            end += timedelta(days=1)
        update.update({"status": row.get("pending_status") or row.get("status"), "check_in_time": start.isoformat() if start else None,
                       "check_out_time": end.isoformat() if end else None, "total_hours": _elapsed_hours(start, end),
                       "notes": row.get("pending_notes") or "", "corrected_by": str(current_user.get("id")), "corrected_at": now,
                       "is_week_off": row.get("pending_status") == "week_off", "is_comp_off": row.get("pending_status") == "comp_off"})
    updated = supabase.table("attendance").update(update).eq("id", attendance_id).eq("approval_status", "pending").execute()
    if not updated.data:
        raise HTTPException(status_code=409, detail="This attendance request was already reviewed")
    _audit(current_user, f"attendance_{decision}", updated.data[0], {"submitted_by": creator.get("uid"), "reason": reason})
    return _public_row(updated.data[0], user_map)


@router.patch("/{attendance_id}/approve")
async def approve_attendance(attendance_id: str, current_user: dict = Depends(require_role("lead", "manager", "director", "super_admin"))):
    return await _review_attendance(attendance_id, "approved", None, current_user)


@router.patch("/{attendance_id}/reject")
async def reject_attendance(attendance_id: str, payload: dict = Body(...), current_user: dict = Depends(require_role("lead", "manager", "director", "super_admin"))):
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    return await _review_attendance(attendance_id, "rejected", reason, current_user)
