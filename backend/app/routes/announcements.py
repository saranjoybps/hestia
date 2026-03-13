from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from app.dependencies import db, get_current_user, require_role
from app.models import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.services.audit_log import log_audit_event
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/announcements", tags=["Announcements"])


class PinRequest(BaseModel):
    isPinned: bool


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_announcement(
    announcement_data: AnnouncementCreate,
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Create a new announcement
    Director/HR only
    """
    try:
        announcement_doc = {
            "title": announcement_data.title,
            "description": announcement_data.description,
            "priority": announcement_data.priority,
            "targetAudience": announcement_data.targetAudience,
            "expiryDate": announcement_data.expiryDate,
            "status": announcement_data.status,
            "isPinned": announcement_data.isPinned,
            "createdBy": announcement_data.createdBy,
            "createdByName": announcement_data.createdByName,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": None,
        }
        
        doc_ref = db.collection("announcements").add(announcement_doc)
        announcement_doc["id"] = doc_ref[1].id

        # Audit log - announcement created
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_created",
            description=(
                f"{current_user.get('name', 'Someone')} created announcement "
                f"\"{announcement_doc.get('title', '')}\"."
            ),
            result="success",
            target_type="announcement",
            target_id=announcement_doc["id"],
            metadata={
                "priority": announcement_doc.get("priority"),
                "status": announcement_doc.get("status"),
                "is_pinned": announcement_doc.get("isPinned")
            }
        )
        
        return announcement_doc
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating announcement: {str(e)}"
        )


@router.get("/")
async def list_announcements(
    priority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    List announcements visible to current user
    """
    try:
        user_role = current_user.get("role")
        user_dept = current_user.get("department")
        
        query = db.collection("announcements")
        
        # Apply filters
        if status:
            query = query.where("status", "==", status)
        elif user_role not in ["hr", "director"]:
            # Regular users only see published
            query = query.where("status", "==", "published")
        
        # Get all announcements
        all_announcements = []
        for doc in query.stream():
            announcement_data = doc.to_dict()
            announcement_data["id"] = doc.id
            
            # Filter by priority if specified
            if priority and announcement_data.get("priority") != priority:
                continue
            
            # Filter by target audience
            target_audience = announcement_data.get("targetAudience", [])
            if not target_audience or "All Departments" in target_audience or "All Roles" in target_audience:
                all_announcements.append(announcement_data)
            elif user_dept in target_audience or user_role.capitalize() in target_audience:
                all_announcements.append(announcement_data)
        
        # Sort: pinned first, then by created_at descending
        all_announcements.sort(
            key=lambda x: (not x.get("isPinned", False), x.get("createdAt", "")),
            reverse=True
        )
        
        return all_announcements
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching announcements: {str(e)}"
        )


@router.get("/my-announcements")
async def get_my_announcements(
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Get announcements created by current user
    Director/HR only
    """
    try:
        query = db.collection("announcements").where("createdBy", "==", current_user.get("uid"))
        
        announcements = []
        for doc in query.stream():
            announcement_data = doc.to_dict()
            announcement_data["id"] = doc.id
            announcements.append(announcement_data)
        
        # Sort by created_at descending
        announcements.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        return announcements
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching my announcements: {str(e)}"
        )


@router.get("/{announcement_id}")
async def get_announcement(
    announcement_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get announcement by ID"""
    try:
        announcement_ref = db.collection("announcements").document(announcement_id)
        announcement_doc = announcement_ref.get()
        
        if not announcement_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        announcement_data = announcement_doc.to_dict()
        announcement_data["id"] = announcement_id
        return announcement_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching announcement: {str(e)}"
        )


@router.put("/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    announcement_update: AnnouncementUpdate,
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Update announcement
    Director/HR only
    """
    try:
        announcement_ref = db.collection("announcements").document(announcement_id)
        announcement_doc = announcement_ref.get()
        
        if not announcement_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        # Check ownership
        announcement_data = announcement_doc.to_dict()
        if announcement_data.get("createdBy") != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own announcements"
            )
        
        update_data = announcement_update.model_dump(exclude_unset=True)
        update_data["updatedAt"] = datetime.utcnow().isoformat()
        
        announcement_ref.update(update_data)
        
        updated_doc = announcement_ref.get()
        announcement_data = updated_doc.to_dict()
        announcement_data["id"] = announcement_id

        # Audit log - announcement updated
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated announcement "
                f"\"{announcement_data.get('title', '')}\"."
            ),
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "priority": announcement_data.get("priority"),
                "status": announcement_data.get("status"),
                "is_pinned": announcement_data.get("isPinned")
            }
        )

        return announcement_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating announcement: {str(e)}"
        )


@router.post("/{announcement_id}/pin")
async def toggle_pin_announcement(
    announcement_id: str,
    pin_data: PinRequest,
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Pin/unpin announcement
    Director/HR only
    """
    try:
        announcement_ref = db.collection("announcements").document(announcement_id)
        announcement_doc = announcement_ref.get()
        
        if not announcement_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        announcement_ref.update({
            "isPinned": pin_data.isPinned,
            "updatedAt": datetime.utcnow().isoformat()
        })
        
        updated_doc = announcement_ref.get()
        announcement_data = updated_doc.to_dict()
        announcement_data["id"] = announcement_id

        # Audit log - announcement pinned/unpinned
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_pinned" if pin_data.isPinned else "announcement_unpinned",
            description=(
                f"{current_user.get('name', 'Someone')} "
                f"{'pinned' if pin_data.isPinned else 'unpinned'} announcement "
                f"\"{announcement_data.get('title', '')}\"."
            ),
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={
                "is_pinned": announcement_data.get("isPinned")
            }
        )

        return announcement_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling pin: {str(e)}"
        )


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Delete announcement
    Director/HR only
    """
    try:
        announcement_ref = db.collection("announcements").document(announcement_id)
        announcement_doc = announcement_ref.get()
        
        if not announcement_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        # Check ownership
        announcement_data = announcement_doc.to_dict()
        if announcement_data.get("createdBy") != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own announcements"
            )

        # Audit log - announcement deleted
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_deleted",
            description=(
                f"{current_user.get('name', 'Someone')} deleted announcement "
                f"\"{announcement_data.get('title', '')}\"."
            ),
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={
                "priority": announcement_data.get("priority"),
                "status": announcement_data.get("status"),
                "is_pinned": announcement_data.get("isPinned")
            }
        )

        announcement_ref.delete()
        return {"message": "Announcement deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting announcement: {str(e)}"
        )
