from datetime import date, datetime, timezone
from secrets import token_urlsafe
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from firebase_admin import auth as firebase_auth

from app.dependencies import get_current_user, invalidate_user_cache, require_role, supabase
from app.models import CandidateActivityCreate, CandidateActivityUpdate, CandidateConversion, CandidateCreate, CandidateUpdate
from app.services.audit_log import log_audit_event
from app.services.zoho_smtp import send_employee_password_setup_email
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/candidates", tags=["Candidates"])

ADMIN_ROLES = {"hr", "director", "super_admin"}
CREATE_ROLES = ADMIN_ROLES | {"manager"}
READ_ROLES = ADMIN_ROLES | {"manager", "lead"}
PIPELINE_STATUSES = {"new", "screening", "shortlisted", "interview_scheduled", "interview_completed", "selected", "offer_sent", "rejected", "withdrawn"}


def _parse_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"Invalid {label}")


async def _actor_row(current_user: Dict[str, Any]) -> Dict[str, Any]:
    row = await SupabaseHelper.get_user_row_by_firebase_uid(str(current_user.get("uid") or ""))
    if not row:
        raise HTTPException(status_code=404, detail="Current user not found")
    return row


async def _candidate_row(candidate_id: str) -> Dict[str, Any]:
    candidate_id = _parse_uuid(candidate_id, "candidate id")
    response = supabase.table("recruitment_candidates").select("*").eq("id", candidate_id).is_("deleted_at", "null").limit(1).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return response.data[0]


async def _can_view_candidate(candidate: Dict[str, Any], current_user: Dict[str, Any], actor: Dict[str, Any]) -> bool:
    role = str(current_user.get("role") or "")
    if role in ADMIN_ROLES:
        return True
    if role == "manager":
        department = str(actor.get("department") or "").strip().casefold()
        if department:
            return department == str(candidate.get("department") or "").strip().casefold()
        return str(candidate.get("owner_id") or "") == str(actor.get("id") or "")
    if role == "lead":
        assignments = supabase.table("candidate_activity_interviewers").select("activity_id").eq("candidate_id", str(candidate["id"])).eq("interviewer_id", str(actor["id"])).limit(1).execute()
        return bool(assignments.data)
    return False


async def _require_candidate_access(candidate: Dict[str, Any], current_user: Dict[str, Any], actor: Dict[str, Any]) -> None:
    if not await _can_view_candidate(candidate, current_user, actor):
        raise HTTPException(status_code=404, detail="Candidate not found")


def _candidate_public(row: Dict[str, Any], user_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    user_map = user_map or {}
    owner = user_map.get(str(row.get("owner_id")), {})
    converted = user_map.get(str(row.get("converted_user_id")), {})
    return {
        "id": str(row.get("id")),
        "firstName": row.get("first_name"),
        "lastName": row.get("last_name"),
        "name": " ".join(value for value in [row.get("first_name"), row.get("last_name")] if value),
        "email": row.get("email"),
        "phone": row.get("phone"),
        "department": row.get("department"),
        "designation": row.get("designation"),
        "source": row.get("source"),
        "currentCompany": row.get("current_company"),
        "currentDesignation": row.get("current_designation"),
        "experienceYears": float(row["experience_years"]) if row.get("experience_years") is not None else None,
        "noticePeriodDays": row.get("notice_period_days"),
        "expectedSalary": float(row["expected_salary"]) if row.get("expected_salary") is not None else None,
        "location": row.get("location"),
        "status": row.get("status"),
        "ownerId": owner.get("uid"),
        "ownerName": owner.get("name"),
        "convertedUserId": converted.get("uid"),
        "convertedAt": row.get("converted_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _activity_public(row: Dict[str, Any], interviewer_rows: List[Dict[str, Any]], user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    interviewers = [user_map[str(item.get("interviewer_id"))] for item in interviewer_rows if str(item.get("activity_id")) == str(row.get("id")) and str(item.get("interviewer_id")) in user_map]
    author = user_map.get(str(row.get("created_by")), {})
    return {
        "id": str(row.get("id")),
        "candidateId": str(row.get("candidate_id")),
        "type": row.get("activity_type"),
        "title": row.get("title"),
        "body": row.get("body") or "",
        "startsAt": row.get("starts_at"),
        "endsAt": row.get("ends_at"),
        "timezone": row.get("timezone") or "Asia/Kolkata",
        "meetingUrl": row.get("meeting_url"),
        "location": row.get("location"),
        "status": row.get("status"),
        "createdBy": author.get("uid"),
        "createdByName": author.get("name"),
        "interviewers": [{"uid": person.get("uid"), "name": person.get("name"), "email": person.get("email"), "designation": person.get("designation")} for person in interviewers],
        "createdAt": row.get("created_at"),
    }


async def _validate_department(name: Optional[str]) -> Optional[str]:
    normalized = str(name or "").strip()
    if not normalized:
        return None
    found = supabase.table("departments").select("name").ilike("name", normalized).limit(1).execute().data or []
    if not found:
        raise HTTPException(status_code=422, detail="Choose a department from the organization list")
    return str(found[0]["name"])


async def _interviewer_rows(ids: List[str], candidate: Dict[str, Any], current_user: Dict[str, Any], actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    identifiers = list(dict.fromkeys(str(value).strip() for value in ids if str(value).strip()))
    if not identifiers:
        return []
    rows = []
    for identifier in identifiers:
        row = await SupabaseHelper.get_user_row_by_firebase_uid(identifier)
        if not row:
            try:
                row = await SupabaseHelper.get_user_row_by_id(str(UUID(identifier)))
            except ValueError:
                row = None
        if not row or row.get("status") != "active":
            raise HTTPException(status_code=422, detail="One or more interviewers are unavailable")
        rows.append(row)
    role = str(current_user.get("role") or "")
    for row in rows:
        if row.get("role") == "super_admin":
            raise HTTPException(status_code=422, detail="Super administrators cannot be assigned as interviewers")
        if role == "manager" and str(row.get("department") or "").strip().casefold() != str(candidate.get("department") or "").strip().casefold():
            raise HTTPException(status_code=403, detail="Managers can assign interviewers from their candidate's department only")
    return rows


@router.get("/options")
async def get_candidate_options(current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor_row(current_user)
    role = str(current_user.get("role"))
    if role in ADMIN_ROLES:
        departments = supabase.table("departments").select("id,name").order("name").execute().data or []
        people = supabase.table("users").select("*").eq("status", "active").neq("role", "super_admin").order("name").limit(500).execute().data or []
    elif role == "manager" and actor.get("department"):
        departments = [{"id": None, "name": actor["department"]}]
        people = supabase.table("users").select("*").eq("status", "active").eq("department", actor["department"]).neq("role", "super_admin").order("name").limit(500).execute().data or []
    elif role == "manager":
        departments, people = [], []
    else:
        departments = [{"id": None, "name": actor.get("department")}] if actor.get("department") else []
        people = [actor]
    return {
        "departments": departments,
        "interviewers": [{"uid": row.get("firebase_uid"), "name": row.get("name"), "email": row.get("email"), "role": row.get("role"), "department": row.get("department"), "designation": row.get("designation")} for row in people],
    }


@router.get("")
async def list_candidates(
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = None,
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(*READ_ROLES)),
):
    if status_filter and status_filter not in PIPELINE_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported candidate status")
    actor = await _actor_row(current_user)
    role = str(current_user.get("role"))
    query = supabase.table("recruitment_candidates").select("*", count="exact").is_("deleted_at", "null")
    if role == "manager":
        manager_department = str(actor.get("department") or "").strip()
        if manager_department:
            query = query.eq("department", manager_department)
        else:
            query = query.eq("owner_id", str(actor["id"]))
    elif role == "lead":
        assignments = supabase.table("candidate_activity_interviewers").select("candidate_id").eq("interviewer_id", str(actor["id"])).execute().data or []
        candidate_ids = list({str(row["candidate_id"]) for row in assignments if row.get("candidate_id")})
        if not candidate_ids:
            return {"candidates": [], "total": 0, "page": page, "limit": limit, "totalPages": 0}
        query = query.in_("id", candidate_ids)
    if department:
        if role == "manager" and str(actor.get("department") or "").strip().casefold() != department.strip().casefold():
            raise HTTPException(status_code=403, detail="You can only filter candidates in your department")
        query = query.eq("department", department)
    if status_filter:
        query = query.eq("status", status_filter)
    if search:
        safe_search = search.replace("%", "").replace("_", "").replace(",", " ").strip()
        if safe_search:
            query = query.or_(f"first_name.ilike.%{safe_search}%,last_name.ilike.%{safe_search}%,email.ilike.%{safe_search}%,designation.ilike.%{safe_search}%")
    response = query.order("created_at", desc=True).range((page - 1) * limit, page * limit - 1).execute()
    user_map = await SupabaseHelper.get_public_user_map()
    candidates = [_candidate_public(row, user_map) for row in (response.data or [])]
    total = int(response.count or 0)
    return {"candidates": candidates, "total": total, "page": page, "limit": limit, "totalPages": (total + limit - 1) // limit}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidate(payload: CandidateCreate, current_user: dict = Depends(require_role(*CREATE_ROLES))):
    actor = await _actor_row(current_user)
    role = str(current_user.get("role"))
    department = await _validate_department(payload.department)
    if role == "manager":
        own_department = str(actor.get("department") or "").strip()
        if not own_department:
            raise HTTPException(status_code=403, detail="A department must be assigned before creating candidates")
        if department and department.casefold() != own_department.casefold():
            raise HTTPException(status_code=403, detail="You can only create candidates for your department")
        department = own_department
    email = str(payload.email).lower()
    if supabase.table("users").select("id").ilike("email", email).limit(1).execute().data:
        raise HTTPException(status_code=409, detail="This email already belongs to an employee")
    existing = supabase.table("recruitment_candidates").select("id,status").ilike("email", email).is_("deleted_at", "null").execute().data or []
    if any(row.get("status") not in {"rejected", "withdrawn"} for row in existing):
        raise HTTPException(status_code=409, detail="An active candidate profile already exists for this email")
    row = {
        "first_name": payload.firstName.strip(), "last_name": (payload.lastName or "").strip() or None,
        "email": email, "phone": payload.phone, "department": department, "designation": payload.designation.strip(),
        "source": payload.source, "current_company": payload.currentCompany, "current_designation": payload.currentDesignation,
        "experience_years": payload.experienceYears, "notice_period_days": payload.noticePeriodDays,
        "expected_salary": payload.expectedSalary, "location": payload.location, "status": "new",
        "owner_id": str(actor["id"]), "created_by": str(actor["id"]), "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = supabase.table("recruitment_candidates").insert(row).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Candidate could not be created")
    created = response.data[0]
    log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"), module="candidates", action="candidate_created", description=f"{current_user.get('name', 'Someone')} added candidate {payload.firstName.strip()}.", result="success", target_type="candidate", target_id=str(created["id"]))
    user_map = await SupabaseHelper.get_public_user_map()
    return _candidate_public(created, user_map)


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    candidate = await _candidate_row(candidate_id)
    actor = await _actor_row(current_user)
    await _require_candidate_access(candidate, current_user, actor)
    activity_rows = supabase.table("candidate_activities").select("*").eq("candidate_id", candidate["id"]).order("starts_at", desc=True).order("created_at", desc=True).execute().data or []
    activity_ids = [str(row["id"]) for row in activity_rows]
    assignments = supabase.table("candidate_activity_interviewers").select("activity_id, interviewer_id").in_("activity_id", activity_ids).execute().data or [] if activity_ids else []
    user_map = await SupabaseHelper.get_public_user_map()
    return {"candidate": _candidate_public(candidate, user_map), "activities": [_activity_public(row, assignments, user_map) for row in activity_rows]}


@router.patch("/{candidate_id}")
async def update_candidate(candidate_id: str, payload: CandidateUpdate, current_user: dict = Depends(require_role(*READ_ROLES))):
    candidate = await _candidate_row(candidate_id)
    actor = await _actor_row(current_user)
    await _require_candidate_access(candidate, current_user, actor)
    role = str(current_user.get("role"))
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _candidate_public(candidate, await SupabaseHelper.get_public_user_map())
    if role == "lead":
        raise HTTPException(status_code=403, detail="Interviewers can add notes and feedback but cannot edit candidate profiles")
    if role == "manager" and set(changes) != {"status"}:
        raise HTTPException(status_code=403, detail="Managers can update the pipeline status; HR manages candidate profile details")
    department = changes.get("department")
    if "department" in changes:
        normalized = await _validate_department(department)
        if role == "manager" and str(normalized or "").casefold() != str(actor.get("department") or "").casefold():
            raise HTTPException(status_code=403, detail="You can only keep candidates within your department")
        changes["department"] = normalized
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
        if supabase.table("users").select("id").ilike("email", changes["email"]).limit(1).execute().data:
            raise HTTPException(status_code=409, detail="This email already belongs to an employee")
        existing = supabase.table("recruitment_candidates").select("id").ilike("email", changes["email"]).is_("deleted_at", "null").neq("id", candidate_id).limit(1).execute().data
        if existing:
            raise HTTPException(status_code=409, detail="Another candidate profile already uses this email")
    if changes.get("status") == "new" and role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Only HR or executive administrators can reopen a candidate")
    if changes.get("status") not in {None, "rejected", "withdrawn"} and candidate.get("status") in {"rejected", "withdrawn"}:
        duplicate = supabase.table("recruitment_candidates").select("id").ilike("email", candidate.get("email", "")).is_("deleted_at", "null").neq("id", candidate_id).not_.in_("status", ["rejected", "withdrawn"]).limit(1).execute().data
        if duplicate:
            raise HTTPException(status_code=409, detail="An active candidate profile already exists for this email")
    mapping = {
        "firstName": "first_name", "lastName": "last_name", "currentCompany": "current_company",
        "currentDesignation": "current_designation", "experienceYears": "experience_years",
        "noticePeriodDays": "notice_period_days", "expectedSalary": "expected_salary",
    }
    update = {mapping.get(key, key): value for key, value in changes.items()}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    response = supabase.table("recruitment_candidates").update(update).eq("id", candidate_id).is_("deleted_at", "null").execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Candidate not found")
    log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"), module="candidates", action="candidate_updated", description=f"{current_user.get('name', 'Someone')} updated candidate {candidate.get('first_name')}.", result="success", target_type="candidate", target_id=candidate_id, metadata={"updated_fields": list(changes.keys())})
    # Do not fetch the entire users table after a successful update. A lookup
    # failure here used to return an HTTP error after the candidate was saved,
    # leaving the UI unable to tell whether the update had succeeded.
    return _candidate_public(response.data[0])


@router.delete("/{candidate_id}")
async def delete_candidate(candidate_id: str, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    candidate = await _candidate_row(candidate_id)
    if candidate.get("converted_user_id") or candidate.get("status") == "hired":
        raise HTTPException(status_code=409, detail="Converted candidates are retained as employee history")
    supabase.table("recruitment_candidates").delete().eq("id", candidate_id).execute()
    log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"), module="candidates", action="candidate_deleted", description=f"{current_user.get('name', 'Someone')} deleted a candidate profile.", result="success", target_type="candidate", target_id=candidate_id)
    return {"message": "Candidate deleted"}


@router.post("/{candidate_id}/activities", status_code=status.HTTP_201_CREATED)
async def create_candidate_activity(candidate_id: str, payload: CandidateActivityCreate, current_user: dict = Depends(require_role(*READ_ROLES))):
    candidate = await _candidate_row(candidate_id)
    actor = await _actor_row(current_user)
    await _require_candidate_access(candidate, current_user, actor)
    role = str(current_user.get("role"))
    if payload.type in {"interview", "meeting"} and role not in (ADMIN_ROLES | {"manager"}):
        raise HTTPException(status_code=403, detail="Only HR, management, and executives can schedule interviews or meetings")
    if payload.type == "note" and payload.interviewerIds:
        raise HTTPException(status_code=422, detail="Interviewers can only be assigned to scheduled activities")
    interviewer_rows = await _interviewer_rows(payload.interviewerIds, candidate, current_user, actor) if payload.interviewerIds else []
    if role == "manager" and payload.type in {"interview", "meeting"} and not interviewer_rows:
        raise HTTPException(status_code=422, detail="Assign at least one interviewer")
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "candidate_id": candidate_id, "activity_type": payload.type, "title": payload.title.strip(), "body": payload.body,
        "starts_at": payload.startsAt.isoformat() if payload.startsAt else None, "ends_at": payload.endsAt.isoformat() if payload.endsAt else None,
        "timezone": payload.timezone, "meeting_url": payload.meetingUrl, "location": payload.location,
        "status": "scheduled" if payload.type in {"interview", "meeting"} else "completed",
        "created_by": str(actor["id"]), "created_at": now, "updated_at": now,
    }
    result = supabase.table("candidate_activities").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Candidate activity could not be saved")
    activity = result.data[0]
    if interviewer_rows:
        link_rows = [{"activity_id": str(activity["id"]), "candidate_id": candidate_id, "interviewer_id": str(person["id"])} for person in interviewer_rows]
        supabase.table("candidate_activity_interviewers").insert(link_rows).execute()
    if payload.type == "interview" and candidate.get("status") in {"new", "screening", "shortlisted"}:
        supabase.table("recruitment_candidates").update({"status": "interview_scheduled", "updated_at": now}).eq("id", candidate_id).execute()
    log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"), module="candidates", action=f"candidate_{payload.type}_created", description=f"{current_user.get('name', 'Someone')} added {payload.type} activity for {candidate.get('first_name')}.", result="success", target_type="candidate", target_id=candidate_id)
    assignments = [{"activity_id": str(activity["id"]), "interviewer_id": str(person["id"])} for person in interviewer_rows]
    user_map = await SupabaseHelper.get_public_user_map()
    return _activity_public(activity, assignments, user_map)


@router.patch("/{candidate_id}/activities/{activity_id}")
async def update_candidate_activity(candidate_id: str, activity_id: str, payload: CandidateActivityUpdate, current_user: dict = Depends(require_role(*READ_ROLES))):
    candidate = await _candidate_row(candidate_id)
    actor = await _actor_row(current_user)
    await _require_candidate_access(candidate, current_user, actor)
    activity_id = _parse_uuid(activity_id, "activity id")
    found = supabase.table("candidate_activities").select("*").eq("id", activity_id).eq("candidate_id", candidate_id).limit(1).execute().data or []
    if not found:
        raise HTTPException(status_code=404, detail="Candidate activity not found")
    activity = found[0]
    role = str(current_user.get("role"))
    changes = payload.model_dump(exclude_unset=True)
    interviewer_ids = changes.pop("interviewerIds", None)
    if role == "lead":
        if activity.get("activity_type") == "note" or not await _can_view_candidate(candidate, current_user, actor):
            raise HTTPException(status_code=403, detail="You can only update interview feedback for candidates assigned to you")
        changes = {key: value for key, value in changes.items() if key in {"body", "status"}}
        if not changes:
            raise HTTPException(status_code=403, detail="Interviewers can update feedback and completion status only")
    elif role == "manager" and activity.get("activity_type") in {"interview", "meeting"}:
        if str(candidate.get("department") or "").casefold() != str(actor.get("department") or "").casefold():
            raise HTTPException(status_code=403, detail="Candidate is outside your department")
    if interviewer_ids is not None and role not in (ADMIN_ROLES | {"manager"}):
        raise HTTPException(status_code=403, detail="Only recruiting managers can change interviewer assignments")
    if "startsAt" in changes:
        changes["starts_at"] = changes.pop("startsAt").isoformat() if changes["startsAt"] else None
    if "endsAt" in changes:
        changes["ends_at"] = changes.pop("endsAt").isoformat() if changes["endsAt"] else None
    for source, target in [("meetingUrl", "meeting_url")]:
        if source in changes:
            changes[target] = changes.pop(source)
    if "status" in changes and activity.get("activity_type") == "note":
        raise HTTPException(status_code=422, detail="Notes do not have a schedule status")
    final_start = changes.get("starts_at", activity.get("starts_at"))
    final_end = changes.get("ends_at", activity.get("ends_at"))
    if final_start and final_end and datetime.fromisoformat(str(final_end).replace("Z", "+00:00")) <= datetime.fromisoformat(str(final_start).replace("Z", "+00:00")):
        raise HTTPException(status_code=422, detail="The end time must be after the start time")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated_rows = supabase.table("candidate_activities").update(changes).eq("id", activity_id).eq("candidate_id", candidate_id).execute().data or []
    updated = updated_rows[0] if updated_rows else {**activity, **changes}
    if interviewer_ids is not None:
        interviewer_rows = await _interviewer_rows(interviewer_ids, candidate, current_user, actor)
        supabase.table("candidate_activity_interviewers").delete().eq("activity_id", activity_id).execute()
        if interviewer_rows:
            supabase.table("candidate_activity_interviewers").insert([{"activity_id": activity_id, "candidate_id": candidate_id, "interviewer_id": str(person["id"])} for person in interviewer_rows]).execute()
    if activity.get("activity_type") == "interview" and updated.get("status") == "completed":
        pending = supabase.table("candidate_activities").select("id").eq("candidate_id", candidate_id).eq("activity_type", "interview").eq("status", "scheduled").limit(1).execute().data or []
        if not pending and candidate.get("status") == "interview_scheduled":
            supabase.table("recruitment_candidates").update({"status": "interview_completed", "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", candidate_id).execute()
    assignments = supabase.table("candidate_activity_interviewers").select("activity_id, interviewer_id").eq("activity_id", activity_id).execute().data or []
    user_map = await SupabaseHelper.get_public_user_map()
    return _activity_public(updated, assignments, user_map)


@router.delete("/{candidate_id}/activities/{activity_id}")
async def delete_candidate_activity(candidate_id: str, activity_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    candidate = await _candidate_row(candidate_id)
    actor = await _actor_row(current_user)
    await _require_candidate_access(candidate, current_user, actor)
    activity_id = _parse_uuid(activity_id, "activity id")
    found = supabase.table("candidate_activities").select("id,activity_type,created_by").eq("id", activity_id).eq("candidate_id", candidate_id).limit(1).execute().data or []
    if not found:
        raise HTTPException(status_code=404, detail="Candidate activity not found")
    activity = found[0]
    role = str(current_user.get("role"))
    if role not in ADMIN_ROLES and not (activity.get("activity_type") == "note" and str(activity.get("created_by")) == str(actor.get("id"))):
        raise HTTPException(status_code=403, detail="You can delete only your own notes")
    supabase.table("candidate_activities").delete().eq("id", activity_id).eq("candidate_id", candidate_id).execute()
    return {"message": "Activity deleted"}


@router.post("/{candidate_id}/convert", status_code=status.HTTP_201_CREATED)
async def convert_candidate(candidate_id: str, payload: CandidateConversion, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    candidate = await _candidate_row(candidate_id)
    if candidate.get("status") not in {"selected", "offer_sent"}:
        raise HTTPException(status_code=409, detail="Select the candidate or send an offer before conversion")
    if candidate.get("converted_user_id"):
        raise HTTPException(status_code=409, detail="This candidate has already been converted")
    role = str(current_user.get("role"))
    if payload.role == "director" and role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a super administrator can create Director accounts")
    department = await _validate_department(payload.department)
    if not department:
        raise HTTPException(status_code=422, detail="Choose a department")
    try:
        date.fromisoformat(payload.dateOfJoining)
    except ValueError:
        raise HTTPException(status_code=422, detail="Joining date must be a valid date")
    manager_row = None
    if payload.managerId:
        manager_row = await SupabaseHelper.get_user_row_by_firebase_uid(payload.managerId)
        if not manager_row:
            manager_row = await SupabaseHelper.get_user_row_by_id(payload.managerId)
    if payload.role in {"director"} and payload.managerId:
        raise HTTPException(status_code=422, detail="Directors cannot have a reporting manager")
    allowed_manager_roles = {"employee": {"lead", "manager", "director"}, "lead": {"manager", "director"}, "manager": {"director"}, "hr": set(), "director": set()}
    if payload.managerId and (not manager_row or str(manager_row.get("role")) not in allowed_manager_roles[payload.role]):
        raise HTTPException(status_code=422, detail="The selected reporting person is not valid for this role")
    if manager_row and str(manager_row.get("department") or "").strip().casefold() != department.casefold():
        raise HTTPException(status_code=422, detail="The reporting person must belong to the employee's department")
    if await SupabaseHelper.get_user_row_by_firebase_uid(candidate.get("email")) or supabase.table("users").select("id").ilike("email", candidate.get("email", "")).limit(1).execute().data:
        raise HTTPException(status_code=409, detail="An employee account already exists for this email")

    full_name = " ".join(value for value in [candidate.get("first_name"), candidate.get("last_name")] if value).strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Candidate name is required for conversion")
    random_password = token_urlsafe(48)
    firebase_user = None
    inserted_user = None
    try:
        firebase_user = firebase_auth.create_user(email=str(candidate["email"]).lower(), password=random_password, display_name=full_name)
        inserted = supabase.table("users").insert({
            "firebase_uid": firebase_user.uid,
            "email": str(candidate["email"]).lower(),
            "name": candidate.get("first_name"),
            "last_name": candidate.get("last_name"),
            "phone": candidate.get("phone"),
            "role": payload.role,
            "department": department,
            "designation": payload.designation.strip(),
            "date_of_joining": payload.dateOfJoining,
            "manager_id": manager_row.get("firebase_uid") if manager_row else None,
            "lead_id": None,
            "status": "active",
            "created_by": current_user.get("uid"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        inserted_user = inserted.data[0] if inserted.data else None
        if not inserted_user:
            raise RuntimeError("Employee record could not be created")
        reset_link = firebase_auth.generate_password_reset_link(str(candidate["email"]).lower())
        send_employee_password_setup_email(to_email=str(candidate["email"]).lower(), employee_name=full_name, setup_url=reset_link)
        updated = supabase.table("recruitment_candidates").update({
            "status": "hired", "converted_user_id": str(inserted_user["id"]), "converted_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", candidate_id).in_("status", ["selected", "offer_sent"]).is_("converted_user_id", "null").execute().data or []
        if not updated:
            raise RuntimeError("Candidate was updated by another user; conversion was rolled back")
    except firebase_auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail="This email already has a Firebase account")
    except HTTPException:
        if inserted_user:
            supabase.table("users").delete().eq("id", str(inserted_user["id"])).execute()
        if firebase_user:
            try:
                firebase_auth.delete_user(firebase_user.uid)
            except Exception:
                pass
        raise
    except Exception as exc:
        if inserted_user:
            supabase.table("users").delete().eq("id", str(inserted_user["id"])).execute()
        if firebase_user:
            try:
                firebase_auth.delete_user(firebase_user.uid)
            except Exception:
                pass
        raise HTTPException(status_code=502, detail=f"Employee setup could not be completed: {str(exc)}")

    invalidate_user_cache(firebase_user.uid)
    log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"), module="candidates", action="candidate_converted_to_employee", description=f"{current_user.get('name', 'Someone')} converted {full_name} to an employee.", result="success", target_type="candidate", target_id=candidate_id, metadata={"employee_uid": firebase_user.uid, "role": payload.role, "department": department})
    user_map = await SupabaseHelper.get_public_user_map()
    return {"message": "Employee created. A password setup link was sent to the candidate's email.", "employee": SupabaseHelper._public_user(inserted_user), "candidate": _candidate_public(updated[0], user_map)}
