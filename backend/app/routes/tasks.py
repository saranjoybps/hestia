from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user, supabase
from app.models import TaskCreate, TaskUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class StatusUpdate(BaseModel):
    status: Literal["todo", "in_progress", "review", "completed"]


VIEW_ALL_ROLES = {"hr", "director", "super_admin"}
TASK_CREATOR_ROLES = {"lead", "manager", "director", "hr", "super_admin"}


def _normalize_due_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get_descendants(root_identifiers: Set[str], user_map: Dict[str, Dict[str, Any]]) -> Set[str]:
    visited: Set[str] = set()
    frontier: Set[str] = {identifier for identifier in root_identifiers if identifier}
    while frontier:
        next_frontier: Set[str] = set()
        for other_uid, data in user_map.items():
            other_public_uid = str(data.get("uid") or "")
            if other_uid in visited or other_public_uid in visited:
                continue
            manager_id = str(data.get("manager_id") or "")
            lead_id = str(data.get("lead_id") or "")
            if manager_id in frontier or lead_id in frontier:
                visited.update({other_uid, other_public_uid})
                next_frontier.update({other_uid, other_public_uid})
        frontier = next_frontier

    return visited


def _can_view_task(current_user: Dict[str, Any], task_data: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    role = current_user.get("role")
    current_identifiers = {
        str(current_user.get("uid") or ""),
        str(current_user.get("id") or ""),
    }
    assignee_id = task_data.get("assigneeId")

    if role in VIEW_ALL_ROLES:
        return True
    if assignee_id in current_identifiers:
        return True
    if role in {"lead", "manager"}:
        assignee = next((user for user in user_map.values() if str(user.get("uid")) == str(assignee_id)), {})
        current = next((user for user in user_map.values() if str(user.get("uid")) == str(current_user.get("uid"))), {})
        department = str(current.get("department") or "").strip().casefold()
        same_department = bool(department) and str(assignee.get("department") or "").strip().casefold() == department
        is_reportee = assignee_id in _get_descendants(current_identifiers, user_map)
        # Department scope includes peers in the same department; reporting
        # relationships remain visible even when the reportee belongs to a
        # different department. An unset department has no department filter.
        return same_department or is_reportee or not department
    return False


def _can_manage_task(current_user: Dict[str, Any], task_data: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    role = current_user.get("role")
    current_identifiers = {
        str(current_user.get("uid") or ""),
        str(current_user.get("id") or ""),
    }
    if role in VIEW_ALL_ROLES:
        return True
    if task_data.get("createdBy") in current_identifiers and _can_view_task(current_user, task_data, user_map):
        return True
    return role in {"lead", "manager"} and _can_view_task(current_user, task_data, user_map)


def _can_update_status(current_user: Dict[str, Any], task_data: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    current_ids = {str(current_user.get("uid") or ""), str(current_user.get("id") or "")}
    return task_data.get("assigneeId") in current_ids or _can_manage_task(current_user, task_data, user_map)


def _is_assignee_allowed(current_user: Dict[str, Any], assignee: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    if assignee.get("role") == "super_admin":
        return False
    if current_user.get("role") in VIEW_ALL_ROLES:
        return True
    if current_user.get("role") not in {"lead", "manager"}:
        return False
    identifiers = {str(current_user.get("uid") or ""), str(current_user.get("id") or "")}
    assignee_ids = {str(assignee.get("uid") or ""), str(assignee.get("id") or "")}
    current = next((user for user in user_map.values() if str(user.get("uid")) == str(current_user.get("uid"))), {})
    department = str(current.get("department") or "").strip().casefold()
    same_department = bool(department) and str(assignee.get("department") or "").strip().casefold() == department
    is_reportee = bool(assignee_ids & _get_descendants(identifiers, user_map))
    return same_department or is_reportee or not department


async def _current_internal_user_id(firebase_uid: str) -> Optional[str]:
    return await SupabaseHelper.get_internal_user_id(firebase_uid)


async def _task_to_public(row: Dict[str, Any], user_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    user_map = user_map if user_map is not None else await SupabaseHelper.get_public_user_map()
    assignee = user_map.get(str(row.get("assigned_to"))) if row.get("assigned_to") else None
    creator = user_map.get(str(row.get("assigned_by"))) if row.get("assigned_by") else None
    return {
        "id": str(row.get("id")),
        "title": row.get("title"),
        "description": row.get("description") or "",
        "assigneeId": assignee.get("uid") if assignee else None,
        "assigneeName": row.get("assignee_name") or (assignee.get("name") if assignee else None),
        "assigneeEmail": row.get("assignee_email") or (assignee.get("email") if assignee else None),
        "department": assignee.get("department") if assignee else None,
        "assigneeRole": assignee.get("role") if assignee else None,
        "createdBy": creator.get("uid") if creator else None,
        "createdByName": row.get("created_by_name") or (creator.get("name") if creator else None),
        "dueDate": row.get("due_date"),
        "priority": row.get("priority", "medium"),
        "status": row.get("status", "todo"),
        "attachments": row.get("attachments") or [],
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


async def _fetch_task_rows(current_user: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    role = current_user.get("role")
    uid = current_user.get("uid")
    user_row = await SupabaseHelper.get_user_row_by_firebase_uid(uid)
    internal_id = str(user_row["id"]) if user_row and user_row.get("id") else None

    user_map = await SupabaseHelper.get_public_user_map()
    query = supabase.table("tasks").select("*")
    if role in VIEW_ALL_ROLES:
        rows = query.order("created_at", desc=True).execute().data or []
    elif role in {"lead", "manager"}:
        identifiers = {str(uid or ""), str(internal_id or "")}
        descendants = _get_descendants(identifiers, user_map)
        current = next((user for user in user_map.values() if str(user.get("uid")) == str(uid)), {})
        department = str(current.get("department") or "").strip().casefold()
        visible_internal_ids = {
            str(user.get("id")) for user in user_map.values()
            if user.get("id") and (
                not department
                or str(user.get("department") or "").strip().casefold() == department
                or str(user.get("uid") or "") in descendants
                or str(user.get("id") or "") in descendants
            )
        }
        if not visible_internal_ids:
            return [], user_map
        rows = query.in_("assigned_to", list(visible_internal_ids)).order("created_at", desc=True).execute().data or []
    else:
        if not internal_id:
            return [], user_map
        rows = query.eq("assigned_to", internal_id).order("created_at", desc=True).execute().data or []

    filtered = [row for row in rows if _can_view_task(current_user, (await _task_to_public(row, user_map)), user_map)]
    return filtered, user_map


@router.get("/assignees")
async def list_task_assignees(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    if role not in TASK_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You are not allowed to assign tasks")

    if role in {"lead", "manager"}:
        # Use the shared reporting-tree resolver so this list follows the same
        # Firebase UID/internal ID compatibility as the Employees module.
        reportees = await SupabaseHelper.get_reportees(str(current_user.get("uid") or ""))
        current = await SupabaseHelper.get_public_user_by_firebase_uid(str(current_user.get("uid") or "")) or {}
        department = str(current.get("department") or "").strip().casefold()
        users = await SupabaseHelper.get_all_public_users()
        reportee_ids = {str(value) for person in reportees for value in (person.get("uid"), person.get("id")) if value}
        users = [person for person in users
                 if (not department
                     or str(person.get("department") or "").strip().casefold() == department
                     or str(person.get("uid") or "") in reportee_ids
                     or str(person.get("id") or "") in reportee_ids)
                 and str(person.get("role") or "").lower() != "super_admin"]
    else:
        users = await SupabaseHelper.get_all_public_users()
        users = [person for person in users if person.get("role") != "super_admin"]

    users = [person for person in users if person.get("status") != "inactive"]
    users.sort(key=lambda person: str(person.get("name") or "").casefold())
    return [{"uid": person.get("uid"), "name": person.get("name"), "email": person.get("email"),
             "role": person.get("role"), "department": person.get("department"),
             "designation": person.get("designation")} for person in users if person.get("uid")]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate, current_user: dict = Depends(get_current_user)):
    try:
        creator_role = current_user.get("role")
        creator_uid = current_user.get("uid")
        if creator_role not in TASK_CREATOR_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to create tasks")

        if not task_data.title.strip():
            raise HTTPException(status_code=422, detail="Task title is required")

        assignee_row = await SupabaseHelper.get_user_row_by_firebase_uid(task_data.assigneeId)
        if not assignee_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

        assignee_public = await SupabaseHelper.get_public_user_by_id(assignee_row["id"])
        user_map = await SupabaseHelper.get_public_user_map()
        if assignee_public.get("status") == "inactive":
            raise HTTPException(status_code=422, detail="Tasks can only be assigned to active users")
        if not _is_assignee_allowed(current_user, assignee_public, user_map):
            raise HTTPException(status_code=403, detail="You can only assign tasks within your reporting scope and department")
        creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(creator_uid)
        if not creator_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        task_row = {
            "title": task_data.title,
            "description": task_data.description,
            "assigned_to": str(assignee_row["id"]),
            "assignee_name": assignee_public.get("name"),
            "assignee_email": assignee_public.get("email"),
            "assigned_by": str(creator_row["id"]),
            "created_by_name": current_user.get("name"),
            "due_date": _normalize_due_date(task_data.dueDate),
            "priority": task_data.priority,
            "status": "todo",
            "attachments": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
        }

        response = supabase.table("tasks").insert(task_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create task")

        task_doc = await _task_to_public(inserted, user_map)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_created",
            description=(
                f"{current_user.get('name', 'Someone')} created task \"{task_doc['title']}\" "
                f"for {task_doc.get('assigneeName', task_doc.get('assigneeId'))}."
            ),
            result="success",
            target_type="task",
            target_id=task_doc["id"],
            metadata={
                "assignee_id": task_doc.get("assigneeId"),
                "assignee_name": task_doc.get("assigneeName"),
                "priority": task_doc.get("priority"),
                "status": task_doc.get("status"),
                "due_date": task_doc.get("dueDate"),
            },
        )

        return task_doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating task: {str(e)}")


@router.get("/")
async def list_tasks(current_user: dict = Depends(get_current_user)):
    try:
        rows, user_map = await _fetch_task_rows(current_user)
        tasks = [await _task_to_public(row, user_map) for row in rows]
        tasks.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return tasks
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching tasks: {str(e)}")


@router.get("/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        row = response.data[0]
        user_map = await SupabaseHelper.get_public_user_map()
        task_data = await _task_to_public(row, user_map)
        if not _can_view_task(current_user, task_data, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to view this task")
        return task_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching task: {str(e)}")


@router.put("/{task_id}")
async def update_task(task_id: str, task_update: TaskUpdate, current_user: dict = Depends(get_current_user)):
    try:
        existing_resp = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not existing_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        existing_row = existing_resp.data[0]
        user_map = await SupabaseHelper.get_public_user_map()
        existing_task = await _task_to_public(existing_row, user_map)
        if not _can_manage_task(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to update this task")

        update_data = task_update.model_dump(exclude_unset=True)
        db_update: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}

        if "title" in update_data:
            if not str(update_data["title"] or "").strip():
                raise HTTPException(status_code=422, detail="Task title is required")
            db_update["title"] = update_data["title"]
        if "description" in update_data:
            db_update["description"] = update_data["description"]
        if "dueDate" in update_data:
            db_update["due_date"] = _normalize_due_date(update_data["dueDate"])
        if "priority" in update_data:
            db_update["priority"] = update_data["priority"]
        if "status" in update_data:
            db_update["status"] = update_data["status"]
            if update_data["status"] == "completed" and existing_row.get("status") != "completed":
                db_update["completed_at"] = datetime.utcnow().isoformat()
            elif update_data["status"] != "completed" and existing_row.get("status") == "completed":
                db_update["completed_at"] = None
        if "attachments" in update_data:
            db_update["attachments"] = update_data["attachments"] or []
        if "assigneeId" in update_data and update_data["assigneeId"]:
            assignee_row = await SupabaseHelper.get_user_row_by_firebase_uid(update_data["assigneeId"])
            if not assignee_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
            assignee_public = await SupabaseHelper.get_public_user_by_id(assignee_row["id"])
            if assignee_public.get("status") == "inactive" or not _is_assignee_allowed(current_user, assignee_public, user_map):
                raise HTTPException(status_code=403, detail="The selected assignee is outside your active task scope")
            db_update["assigned_to"] = str(assignee_row["id"])
            db_update["assignee_name"] = assignee_public.get("name")
            db_update["assignee_email"] = assignee_public.get("email")

        response = supabase.table("tasks").update(db_update).eq("id", task_id).execute()
        updated_row = response.data[0] if response.data else None
        if not updated_row:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task")

        task_data = await _task_to_public(updated_row, user_map)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_updated",
            description=f"{current_user.get('name', 'Someone')} updated task \"{task_data.get('title', task_id)}\".",
            result="success",
            target_type="task",
            target_id=task_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "assignee_id": task_data.get("assigneeId"),
                "assignee_name": task_data.get("assigneeName"),
                "status": task_data.get("status"),
                "priority": task_data.get("priority"),
            },
        )
        return task_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating task: {str(e)}")


@router.patch("/{task_id}/status")
async def update_task_status(task_id: str, status_update: StatusUpdate, current_user: dict = Depends(get_current_user)):
    try:
        existing_resp = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not existing_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        user_map = await SupabaseHelper.get_public_user_map()
        existing_task = await _task_to_public(existing_resp.data[0], user_map)
        if not _can_update_status(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to update this task status")

        status_payload = {
            "status": status_update.status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if status_update.status == "completed" and existing_task.get("status") != "completed":
            status_payload["completed_at"] = datetime.utcnow().isoformat()
        elif status_update.status != "completed" and existing_task.get("status") == "completed":
            status_payload["completed_at"] = None
        response = supabase.table("tasks").update(status_payload).eq("id", task_id).execute()
        updated_row = response.data[0] if response.data else None
        if not updated_row:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task status")

        task_data = await _task_to_public(updated_row, user_map)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_status_updated",
            description=(
                f"{current_user.get('name', 'Someone')} changed status of task "
                f"\"{task_data.get('title', task_id)}\" to {task_data.get('status')}."
            ),
            result="success",
            target_type="task",
            target_id=task_id,
            metadata={
                "status": task_data.get("status"),
                "assignee_id": task_data.get("assigneeId"),
                "assignee_name": task_data.get("assigneeName"),
            },
        )

        return task_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating task status: {str(e)}")


@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    try:
        existing_resp = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not existing_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        user_map = await SupabaseHelper.get_public_user_map()
        existing_task = await _task_to_public(existing_resp.data[0], user_map)
        if not _can_manage_task(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to delete this task")

        task_data = existing_resp.data[0]
        supabase.table("tasks").delete().eq("id", task_id).execute()

        public_task = await _task_to_public(task_data, user_map)
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_deleted",
            description=f"{current_user.get('name', 'Someone')} deleted task \"{public_task.get('title', task_id)}\".",
            result="success",
            target_type="task",
            target_id=task_id,
            metadata={
                "assignee_id": public_task.get("assigneeId"),
                "assignee_name": public_task.get("assigneeName"),
                "status": public_task.get("status"),
                "priority": public_task.get("priority"),
            },
        )

        return {"message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting task: {str(e)}")
