from fastapi import APIRouter, Depends, HTTPException, status, Body
from app.dependencies import db, get_current_user, require_role
from app.models import TaskCreate, TaskUpdate, TaskResponse
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class StatusUpdate(BaseModel):
    status: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new task"""
    try:
        task_doc = {
            "title": task_data.title,
            "description": task_data.description,
            "assigneeId": task_data.assigneeId,
            "assigneeName": task_data.assigneeName,
            "assigneeEmail": task_data.assigneeEmail,
            "createdBy": task_data.createdBy,
            "createdByName": task_data.createdByName,
            "dueDate": task_data.dueDate,
            "priority": task_data.priority,
            "status": task_data.status,
            "attachments": task_data.attachments,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": None,
        }
        
        doc_ref = db.collection("tasks").add(task_doc)
        task_doc["id"] = doc_ref[1].id
        
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
        
        # Leads, managers, directors, and HR can see all tasks
        # Regular employees see only their assigned tasks
        if user_role in ["lead", "manager", "director", "hr"]:
            query = db.collection("tasks")
        else:
            query = db.collection("tasks").where("assigneeId", "==", uid)
        
        tasks = []
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
        
        update_data = task_update.model_dump(exclude_unset=True)
        update_data["updatedAt"] = datetime.utcnow().isoformat()
        
        task_ref.update(update_data)
        
        updated_doc = task_ref.get()
        task_data = updated_doc.to_dict()
        task_data["id"] = task_id
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
        
        task_ref.update({
            "status": status_update.status,
            "updatedAt": datetime.utcnow().isoformat()
        })
        
        updated_doc = task_ref.get()
        task_data = updated_doc.to_dict()
        task_data["id"] = task_id
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
        
        task_ref.delete()
        return {"message": "Task deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting task: {str(e)}"
        )
