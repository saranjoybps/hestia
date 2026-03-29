from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import db, get_current_user
from app.models import TaskCreate, TaskUpdate
from app.services.audit_log import log_audit_event
from datetime import datetime
from typing import Dict, Any, Set
from pydantic import BaseModel
from google.cloud.firestore_v1 import FieldFilter

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class StatusUpdate(BaseModel):
    status: str


VIEW_ALL_ROLES = {"hr", "director", "super_admin", "manager"}


def _get_direct_reportee_ids(manager_uid: str) -> Set[str]:
    ids: Set[str] = set()
    queries = [
        db.collection("users").where(filter=FieldFilter("manager_id", "==", manager_uid)),
        db.collection("users").where(filter=FieldFilter("managerId", "==", manager_uid)),
        # Legacy fallback
        db.collection("users").where(filter=FieldFilter("lead_id", "==", manager_uid)),
        db.collection("users").where(filter=FieldFilter("leadId", "==", manager_uid)),
    ]
    for query in queries:
        for doc in query.stream():
            ids.add(doc.id)
    return ids


def _is_descendant(manager_uid: str, target_uid: str, max_depth: int = 8) -> bool:
    if not manager_uid or not target_uid or manager_uid == target_uid:
        return False

    visited: Set[str] = {manager_uid}
    frontier: Set[str] = {manager_uid}
    depth = 0

    while frontier and depth < max_depth:
        next_frontier: Set[str] = set()
        for uid in frontier:
            reportees = _get_direct_reportee_ids(uid)
            if target_uid in reportees:
                return True
            for rid in reportees:
                if rid not in visited:
                    visited.add(rid)
                    next_frontier.add(rid)
        frontier = next_frontier
        depth += 1

    return False


def _can_view_task(current_user: Dict[str, Any], task_data: Dict[str, Any]) -> bool:
    role = current_user.get("role")
    uid = current_user.get("uid")
    assignee_id = task_data.get("assigneeId")

    if role in VIEW_ALL_ROLES:
        return True
    if assignee_id == uid:
        return True
    if role == "lead" and _is_descendant(uid, assignee_id):
        return True
    return False


def _can_modify_task(current_user: Dict[str, Any], task_data: Dict[str, Any]) -> bool:
    role = current_user.get("role")
    uid = current_user.get("uid")
    assignee_id = task_data.get("assigneeId")

    if role in VIEW_ALL_ROLES:
        return True
    if role == "lead":
        # Leads can work on their own assigned tasks and their reportee tasks.
        return assignee_id == uid or _is_descendant(uid, assignee_id)
    # Employees can only modify their own assigned tasks.
    return assignee_id == uid


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new task"""
    try:
        creator_role = current_user.get("role")
        creator_uid = current_user.get("uid")
        allowed_creators = {"lead", "manager", "director", "hr", "super_admin"}
        if creator_role not in allowed_creators:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to create tasks"
            )

        assignee_doc = db.collection("users").document(task_data.assigneeId).get()
        if not assignee_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignee not found"
            )
        assignee_data = assignee_doc.to_dict()
        assignee_role = assignee_data.get("role")

        if creator_role == "lead":
            if assignee_role != "employee" or not _is_descendant(creator_uid, task_data.assigneeId):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Leads can create tasks only for their reporting employees"
                )

        task_doc = {
            "title": task_data.title,
            "description": task_data.description,
            "assigneeId": task_data.assigneeId,
            "assigneeName": assignee_data.get("name") or task_data.assigneeName,
            "assigneeEmail": assignee_data.get("email") or task_data.assigneeEmail,
            "createdBy": creator_uid,
            "createdByName": current_user.get("name"),
            "dueDate": task_data.dueDate,
            "priority": task_data.priority,
            "status": task_data.status,
            "attachments": task_data.attachments,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": None,
        }
        
        doc_ref = db.collection("tasks").add(task_doc)
        task_doc["id"] = doc_ref[1].id

        # Audit log - task created
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
                "due_date": task_doc.get("dueDate")
            }
        )
        
        return task_doc
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating task: {str(e)}"
        )


@router.get("/")
async def list_tasks(
    current_user: dict = Depends(get_current_user)
):
    """List all tasks visible to current user"""
    try:
        user_role = current_user.get("role")
        uid = current_user.get("uid")

        tasks = []
        if user_role in VIEW_ALL_ROLES:
            query = db.collection("tasks")
            for doc in query.stream():
                task_data = doc.to_dict()
                task_data["id"] = doc.id
                tasks.append(task_data)
        elif user_role == "lead":
            query = db.collection("tasks")
            for doc in query.stream():
                task_data = doc.to_dict()
                task_data["id"] = doc.id
                if _can_view_task(current_user, task_data):
                    tasks.append(task_data)
        else:
            query = db.collection("tasks").where("assigneeId", "==", uid)
            for doc in query.stream():
                task_data = doc.to_dict()
                task_data["id"] = doc.id
                tasks.append(task_data)
        
        # Sort by created date descending
        tasks.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        return tasks
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching tasks: {str(e)}"
        )


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get task by ID"""
    try:
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        
        if not task_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        task_data = task_doc.to_dict()
        task_data["id"] = task_id
        if not _can_view_task(current_user, task_data):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view this task"
            )
        return task_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching task: {str(e)}"
        )


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update task"""
    try:
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        
        if not task_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        existing_task = task_doc.to_dict()
        existing_task["id"] = task_id
        if not _can_modify_task(current_user, existing_task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to update this task"
            )

        update_data = task_update.model_dump(exclude_unset=True)
        update_data["updatedAt"] = datetime.utcnow().isoformat()
        
        task_ref.update(update_data)
        
        updated_doc = task_ref.get()
        task_data = updated_doc.to_dict()
        task_data["id"] = task_id

        # Audit log - task updated
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated task "
                f"\"{task_data.get('title', task_id)}\"."
            ),
            result="success",
            target_type="task",
            target_id=task_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "assignee_id": task_data.get("assigneeId"),
                "assignee_name": task_data.get("assigneeName"),
                "status": task_data.get("status"),
                "priority": task_data.get("priority")
            }
        )

        return task_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating task: {str(e)}"
        )


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: str,
    status_update: StatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update task status (for drag and drop)"""
    try:
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        
        if not task_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        existing_task = task_doc.to_dict()
        existing_task["id"] = task_id
        if not _can_modify_task(current_user, existing_task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to update this task"
            )

        task_ref.update({
            "status": status_update.status,
            "updatedAt": datetime.utcnow().isoformat()
        })
        
        updated_doc = task_ref.get()
        task_data = updated_doc.to_dict()
        task_data["id"] = task_id

        # Audit log - task status updated
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
                "assignee_name": task_data.get("assigneeName")
            }
        )

        return task_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating task status: {str(e)}"
        )


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete task"""
    try:
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        
        if not task_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        existing_task = task_doc.to_dict()
        existing_task["id"] = task_id
        if not _can_modify_task(current_user, existing_task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to delete this task"
            )

        task_data = task_doc.to_dict()
        task_ref.delete()

        # Audit log - task deleted
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="tasks",
            action="task_deleted",
            description=(
                f"{current_user.get('name', 'Someone')} deleted task "
                f"\"{task_data.get('title', task_id)}\"."
            ),
            result="success",
            target_type="task",
            target_id=task_id,
            metadata={
                "assignee_id": task_data.get("assigneeId"),
                "assignee_name": task_data.get("assigneeName"),
                "status": task_data.get("status"),
                "priority": task_data.get("priority")
            }
        )

        return {"message": "Task deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting task: {str(e)}"
        )
