from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user, supabase
from app.models import TaskCreate, TaskUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class StatusUpdate(BaseModel):
    status: str


VIEW_ALL_ROLES = {"hr", "director", "super_admin", "manager"}


def _get_descendants(root_uid: str, user_map: Dict[str, Dict[str, Any]], max_depth: int = 8) -> Set[str]:
    visited: Set[str] = set()
    frontier: Set[str] = {root_uid}
    depth = 0

    while frontier and depth < max_depth:
        next_frontier: Set[str] = set()
        for uid in frontier:
            for other_uid, data in user_map.items():
                if other_uid in visited or other_uid == root_uid:
                    continue
                if data.get("manager_id") == uid or data.get("lead_id") == uid:
                    visited.add(other_uid)
                    next_frontier.add(other_uid)
        frontier = next_frontier
        depth += 1

    return visited


def _can_view_task(current_user: Dict[str, Any], task_data: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    role = current_user.get("role")
    uid = current_user.get("uid")
    assignee_id = task_data.get("assigneeId")

    if role in VIEW_ALL_ROLES:
        return True
    if assignee_id == uid:
        return True
    if role == "lead":
        return assignee_id in _get_descendants(uid, user_map)
    return False


def _can_modify_task(current_user: Dict[str, Any], task_data: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> bool:
    role = current_user.get("role")
    uid = current_user.get("uid")
    assignee_id = task_data.get("assigneeId")

    if role in VIEW_ALL_ROLES:
        return True
    if role == "lead":
        return assignee_id == uid or assignee_id in _get_descendants(uid, user_map)
    return assignee_id == uid


async def _current_internal_user_id(firebase_uid: str) -> Optional[str]:
    return await SupabaseHelper.get_internal_user_id(firebase_uid)


async def _task_to_public(row: Dict[str, Any]) -> Dict[str, Any]:
    assignee = await SupabaseHelper.get_public_user_by_id(row.get("assigned_to")) if row.get("assigned_to") else None
    creator = await SupabaseHelper.get_public_user_by_id(row.get("assigned_by")) if row.get("assigned_by") else None
    return {
        "id": str(row.get("id")),
        "title": row.get("title"),
        "description": row.get("description") or "",
        "assigneeId": assignee.get("uid") if assignee else None,
        "assigneeName": row.get("assignee_name") or (assignee.get("name") if assignee else None),
        "assigneeEmail": row.get("assignee_email") or (assignee.get("email") if assignee else None),
        "createdBy": creator.get("uid") if creator else None,
        "createdByName": row.get("created_by_name") or (creator.get("name") if creator else None),
        "dueDate": row.get("due_date"),
        "priority": row.get("priority", "medium"),
        "status": row.get("status", "todo"),
        "attachments": row.get("attachments") or [],
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


async def _fetch_task_rows(current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    role = current_user.get("role")
    uid = current_user.get("uid")
    user_row = await SupabaseHelper.get_user_row_by_firebase_uid(uid)
    internal_id = str(user_row["id"]) if user_row and user_row.get("id") else None

    query = supabase.table("tasks").select("*")
    if role in VIEW_ALL_ROLES:
        rows = query.order("created_at", desc=True).execute().data or []
    elif role == "lead":
        rows = query.order("created_at", desc=True).execute().data or []
    else:
        if not internal_id:
            return []
        rows = query.eq("assigned_to", internal_id).order("created_at", desc=True).execute().data or []

    if role != "lead":
        return rows

    user_map = await SupabaseHelper.get_public_user_map()
    visible_ids = _get_descendants(uid, user_map)
    visible_ids.add(uid)
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        assignee = await SupabaseHelper.get_public_user_by_id(row.get("assigned_to")) if row.get("assigned_to") else None
        if assignee and assignee.get("uid") in visible_ids:
            filtered.append(row)
    return filtered


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate, current_user: dict = Depends(get_current_user)):
    try:
        creator_role = current_user.get("role")
        creator_uid = current_user.get("uid")
        allowed_creators = {"lead", "manager", "director", "hr", "super_admin"}
        if creator_role not in allowed_creators:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to create tasks")

        assignee_row = await SupabaseHelper.get_user_row_by_firebase_uid(task_data.assigneeId)
        if not assignee_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

        assignee_public = await SupabaseHelper.get_public_user_by_id(assignee_row["id"])
        if creator_role == "lead":
            user_map = await SupabaseHelper.get_public_user_map()
            if assignee_public.get("role") != "employee" or task_data.assigneeId not in _get_descendants(creator_uid, user_map):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Leads can create tasks only for their reporting employees",
                )

        creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(creator_uid)
        if not creator_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        task_row = {
            "title": task_data.title,
            "description": task_data.description,
            "assigned_to": str(assignee_row["id"]),
            "assignee_name": task_data.assigneeName or assignee_public.get("name"),
            "assignee_email": task_data.assigneeEmail or assignee_public.get("email"),
            "assigned_by": str(creator_row["id"]),
            "created_by_name": current_user.get("name"),
            "due_date": task_data.dueDate,
            "priority": task_data.priority,
            "status": task_data.status,
            "attachments": task_data.attachments or [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
        }

        response = supabase.table("tasks").insert(task_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create task")

        task_doc = await _task_to_public(inserted)

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
        rows = await _fetch_task_rows(current_user)
        tasks = [await _task_to_public(row) for row in rows]
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
        task_data = await _task_to_public(row)
        user_map = await SupabaseHelper.get_public_user_map() if current_user.get("role") == "lead" else {}
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
        existing_task = await _task_to_public(existing_row)
        user_map = await SupabaseHelper.get_public_user_map() if current_user.get("role") == "lead" else {}
        if not _can_modify_task(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to update this task")

        update_data = task_update.model_dump(exclude_unset=True)
        db_update: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}

        if "title" in update_data:
            db_update["title"] = update_data["title"]
        if "description" in update_data:
            db_update["description"] = update_data["description"]
        if "dueDate" in update_data:
            db_update["due_date"] = update_data["dueDate"]
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
            db_update["assigned_to"] = str(assignee_row["id"])
            db_update["assignee_name"] = update_data.get("assigneeName") or assignee_public.get("name")
            db_update["assignee_email"] = update_data.get("assigneeEmail") or assignee_public.get("email")
        if "assigneeName" in update_data:
            db_update["assignee_name"] = update_data["assigneeName"]
        if "assigneeEmail" in update_data:
            db_update["assignee_email"] = update_data["assigneeEmail"]

        response = supabase.table("tasks").update(db_update).eq("id", task_id).execute()
        updated_row = response.data[0] if response.data else None
        if not updated_row:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task")

        task_data = await _task_to_public(updated_row)

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

        existing_task = await _task_to_public(existing_resp.data[0])
        user_map = await SupabaseHelper.get_public_user_map() if current_user.get("role") == "lead" else {}
        if not _can_modify_task(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to update this task")

        response = supabase.table("tasks").update({
            "status": status_update.status,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", task_id).execute()
        updated_row = response.data[0] if response.data else None
        if not updated_row:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task status")

        task_data = await _task_to_public(updated_row)

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

        existing_task = await _task_to_public(existing_resp.data[0])
        user_map = await SupabaseHelper.get_public_user_map() if current_user.get("role") == "lead" else {}
        if not _can_modify_task(current_user, existing_task, user_map):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to delete this task")

        task_data = existing_resp.data[0]
        supabase.table("tasks").delete().eq("id", task_id).execute()

        public_task = await _task_to_public(task_data)
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
