from datetime import datetime, date as date_type
from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, require_role, supabase
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def _time_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if len(text) >= 5:
        return text[:5]
    return text or None


def _display_status(status_value: Optional[str]) -> str:
    if status_value == "half_day":
        return "half-day"
    if status_value == "leave":
        return "on-leave"
    return status_value or "present"


def _db_status(status_value: str) -> str:
    if status_value == "half-day":
        return "half_day"
    if status_value in {"on-leave", "week-off", "comp-off"}:
        return "leave"
    return status_value


def _parse_time_for_date(day: str, value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    candidate = value.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%H:%M",
    ]
    for fmt in formats:
        try:
            if fmt.startswith("%H"):
                parsed_time = datetime.strptime(candidate, fmt).time()
                parsed_date = datetime.strptime(day, "%Y-%m-%d").date()
                return datetime.combine(parsed_date, parsed_time)
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def _work_hours(day: str, check_in: Optional[str], check_out: Optional[str]) -> float:
    start = _parse_time_for_date(day, check_in)
    end = _parse_time_for_date(day, check_out)
    if not start or not end or end <= start:
        return 0.0
    return round((end - start).total_seconds() / 3600, 2)


def _attendance_row(
    row: Dict[str, Any],
    user_map: Dict[str, Dict[str, Any]],
    marked_by: Optional[str] = None,
) -> Dict[str, Any]:
    user = user_map.get(str(row.get("user_id")), {})
    check_in = _time_str(row.get("check_in_time"))
    check_out = _time_str(row.get("check_out_time"))
    work_hours = row.get("total_hours")
    if work_hours is None:
        work_hours = _work_hours(str(row.get("date")), check_in, check_out)

    corrected_by = row.get("corrected_by")
    corrected_user = user_map.get(str(corrected_by), {}) if corrected_by else {}

    return {
        "id": str(row.get("id")),
        "userId": user.get("uid") or str(row.get("user_id")),
        "userName": user.get("name"),
        "date": str(row.get("date")),
        "checkIn": check_in,
        "checkOut": check_out,
        "status": _display_status(row.get("status")),
        "workHours": float(work_hours or 0),
        "notes": row.get("notes") or "",
        "markedBy": marked_by or user.get("uid"),
        "correctedBy": corrected_user.get("uid"),
        "created_at": row.get("created_at"),
    }


async def _load_user_map() -> Dict[str, Dict[str, Any]]:
    return await SupabaseHelper.get_public_user_map()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_attendance(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = payload.get("user_id") or payload.get("userId")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")

        employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user_role = current_user.get("role")
        if user_role == "lead":
            manager_id = str(employee.get("manager_id") or "")
            legacy_lead_id = str(employee.get("lead_id") or "")
            current_internal_id = str(current_user.get("id") or "")
            if manager_id != current_internal_id and legacy_lead_id != current_internal_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only mark attendance for your reportees",
                )
        elif user_role not in ["manager", "director", "hr"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        day = payload.get("date")
        if not day:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date is required")

        status_value = _db_status(payload.get("status", "present"))
        check_in = payload.get("check_in") or payload.get("checkIn")
        check_out = payload.get("check_out") or payload.get("checkOut")
        notes = payload.get("notes")

        insert_payload = {
            "user_id": employee["id"],
            "date": day,
            "status": status_value,
            "check_in_time": _parse_time_for_date(day, check_in),
            "check_out_time": _parse_time_for_date(day, check_out),
            "notes": notes,
            "marked_by": current_user.get("id"),
            "corrected_by": None,
            "corrected_at": None,
        }

        response = supabase.table("attendance").insert(insert_payload).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create attendance")

        user_map = await _load_user_map()
        attendance_doc = _attendance_row(response.data[0], user_map, marked_by=current_user.get("uid"))

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="attendance",
            action="attendance_marked",
            description=(
                f"{current_user.get('name', 'Someone')} marked attendance for {employee.get('name', user_id)} "
                f"on {day} as {attendance_doc['status']}."
            ),
            result="success",
            target_type="attendance",
            target_id=attendance_doc["id"],
            metadata={
                "user_id": attendance_doc["userId"],
                "user_name": attendance_doc["userName"],
                "date": day,
                "status": attendance_doc["status"],
                "check_in": attendance_doc["checkIn"],
                "check_out": attendance_doc["checkOut"],
            },
        )

        return attendance_doc

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating attendance: {str(e)}")


@router.get("/")
async def get_attendance(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    attendance_status: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = supabase.table("attendance").select("*")
        if user_id:
            employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
            if employee:
                query = query.eq("user_id", employee["id"])
            else:
                return []
        if attendance_status:
            query = query.eq("status", _db_status(attendance_status))
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        response = query.execute()
        rows = response.data or []
        user_map = await _load_user_map()
        return [_attendance_row(row, user_map) for row in rows]

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching attendance: {str(e)}")


@router.get("/user/{user_id}")
async def get_user_attendance(
    user_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
        if not employee:
            return []

        query = supabase.table("attendance").select("*").eq("user_id", employee["id"])
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        query = query.order("date", desc=True)

        response = query.execute()
        user_map = await _load_user_map()
        return [_attendance_row(row, user_map) for row in response.data or []]

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching attendance: {str(e)}")


@router.get("/monthly/{user_id}/{year}/{month}")
async def get_monthly_attendance(
    user_id: str,
    year: int,
    month: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
        if not employee:
            return {"year": year, "month": month, "attendance": {}, "stats": {}}

        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        response = (
            supabase.table("attendance")
            .select("*")
            .eq("user_id", employee["id"])
            .gte("date", start_date)
            .lt("date", end_date)
            .execute()
        )

        attendance_dict: Dict[str, Dict[str, Any]] = {}
        stats = {
            "present": 0,
            "absent": 0,
            "half_day": 0,
            "leave": 0,
            "holiday": 0,
            "total_hours": 0.0,
        }

        user_map = await _load_user_map()
        for row in response.data or []:
            record = _attendance_row(row, user_map)
            attendance_dict[record["date"]] = {
                "id": record["id"],
                "status": record["status"],
                "check_in": record["checkIn"],
                "check_out": record["checkOut"],
                "total_hours": record["workHours"],
                "notes": record["notes"],
            }
            db_status = _db_status(record["status"])
            if db_status in stats:
                stats[db_status] += 1
            stats["total_hours"] += record["workHours"]

        return {"year": year, "month": month, "attendance": attendance_dict, "stats": stats}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching monthly attendance: {str(e)}")


@router.put("/{attendance_id}")
async def update_attendance(
    attendance_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        existing = supabase.table("attendance").select("*").eq("id", attendance_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

        update_data: Dict[str, Any] = {}
        if "check_in" in payload or "checkIn" in payload:
            update_data["check_in_time"] = _parse_time_for_date(str(existing.data[0].get("date")), payload.get("check_in") or payload.get("checkIn"))
        if "check_out" in payload or "checkOut" in payload:
            update_data["check_out_time"] = _parse_time_for_date(str(existing.data[0].get("date")), payload.get("check_out") or payload.get("checkOut"))
        if "status" in payload:
            update_data["status"] = _db_status(payload.get("status"))
        if "notes" in payload:
            update_data["notes"] = payload.get("notes")

        update_data["updated_at"] = datetime.utcnow().isoformat()
        update_data["corrected_by"] = current_user.get("id")
        update_data["corrected_at"] = datetime.utcnow().isoformat()

        response = supabase.table("attendance").update(update_data).eq("id", attendance_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

        user_map = await _load_user_map()
        return _attendance_row(response.data[0], user_map, marked_by=current_user.get("uid"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating attendance: {str(e)}")
