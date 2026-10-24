from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.dependencies import get_current_user, require_role, supabase
from app.models import AnnouncementCreate, AnnouncementUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/announcements", tags=["Announcements"])


class PinRequest(BaseModel):
    isPinned: bool


async def _announcement_to_public(row: Dict[str, Any], user_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    user_map = user_map if user_map is not None else await SupabaseHelper.get_public_user_map()
    creator = user_map.get(str(row.get("created_by"))) if row.get("created_by") else None
    return {
        "id": str(row.get("id")),
        "title": row.get("title"),
        "description": row.get("description"),
        "priority": row.get("priority", "medium"),
        "targetAudience": row.get("target_audience") or [],
        "expiryDate": row.get("expiry_date"),
        "status": row.get("status", "draft"),
        "isPinned": row.get("is_pinned", False),
        "createdBy": creator.get("uid") if creator else None,
        "createdByName": row.get("created_by_name") or (creator.get("name") if creator else None),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


async def _current_internal_user_id(firebase_uid: str) -> Optional[str]:
    return await SupabaseHelper.get_internal_user_id(firebase_uid)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_announcement(
    announcement_data: AnnouncementCreate,
    current_user: dict = Depends(require_role("director", "hr", "manager", "lead", "super_admin")),
):
    try:
        creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not creator_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        if not announcement_data.title.strip() or not announcement_data.description.strip():
            raise HTTPException(status_code=422, detail="Title and description are required")
        announcement_row = {
            "title": announcement_data.title,
            "content": announcement_data.description,
            "description": announcement_data.description,
            "priority": announcement_data.priority,
            "target_audience": announcement_data.targetAudience or [],
            "expiry_date": announcement_data.expiryDate,
            "status": announcement_data.status,
            "is_pinned": announcement_data.isPinned,
            "created_by": str(creator_row["id"]),
            "created_by_name": current_user.get("name"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
        }

        response = supabase.table("announcements").insert(jsonable_encoder(announcement_row)).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create announcement")

        announcement_doc = await _announcement_to_public(inserted)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_created",
            description=f"{current_user.get('name', 'Someone')} created announcement \"{announcement_doc.get('title', '')}\".",
            result="success",
            target_type="announcement",
            target_id=announcement_doc["id"],
            metadata={
                "priority": announcement_doc.get("priority"),
                "status": announcement_doc.get("status"),
                "is_pinned": announcement_doc.get("isPinned"),
            },
        )
        return jsonable_encoder(announcement_doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating announcement: {str(e)}")


@router.get("/")
async def list_announcements(
    priority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_role = current_user.get("role")
        user_dept = current_user.get("department")

        # The public feed never returns drafts, even if a client asks for them.
        resp = supabase.table("announcements").select("*").eq("status", "published").order("created_at", desc=True).execute()
        rows = resp.data or []
        user_map = await SupabaseHelper.get_public_user_map()

        public: List[Dict[str, Any]] = []
        for row in rows:
            announcement = await _announcement_to_public(row, user_map)
            if priority and announcement.get("priority") != priority:
                continue
            expiry = announcement.get("expiryDate")
            if expiry and str(expiry)[:10] < date.today().isoformat():
                continue
            target_audience = announcement.get("targetAudience") or []
            role_label = {"super_admin": "Super Admin", "hr": "HR"}.get(str(user_role), str(user_role or "").replace("_", " ").title())
            audience = {str(value).strip().casefold() for value in target_audience}
            if not audience or "all departments" in audience or "all roles" in audience:
                public.append(announcement)
            elif str(user_dept or "").strip().casefold() in audience or role_label.casefold() in audience:
                public.append(announcement)

        public.sort(key=lambda x: (not x.get("isPinned", False), x.get("createdAt", "")), reverse=True)
        return public
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching announcements: {str(e)}")


@router.get("/my-announcements")
async def get_my_announcements(current_user: dict = Depends(require_role("director", "hr", "manager", "lead", "super_admin"))):
    try:
        creator_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not creator_row:
            return []
        resp = supabase.table("announcements").select("*").eq("created_by", str(creator_row["id"])).order("created_at", desc=True).execute()
        rows = resp.data or []
        user_map = await SupabaseHelper.get_public_user_map()
        return [await _announcement_to_public(row, user_map) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching my announcements: {str(e)}")


@router.get("/{announcement_id}")
async def get_announcement(announcement_id: str, current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("announcements").select("*").eq("id", announcement_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        row = response.data
        owns = str(row.get("created_by")) == str(await _current_internal_user_id(current_user.get("uid")))
        if row.get("status") != "published" and not (owns or current_user.get("role") in {"hr", "director", "super_admin"}):
            raise HTTPException(status_code=404, detail="Announcement not found")
        if row.get("status") == "published":
            target = row.get("target_audience") or []
            target_keys = {str(value).strip().casefold() for value in target}
            role = {"super_admin": "Super Admin", "hr": "HR"}.get(str(current_user.get("role")), str(current_user.get("role", "")).replace("_", " ").title())
            if target_keys and "all departments" not in target_keys and "all roles" not in target_keys and str(current_user.get("department", "")).casefold() not in target_keys and role.casefold() not in target_keys:
                raise HTTPException(status_code=404, detail="Announcement not found")
        return await _announcement_to_public(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching announcement: {str(e)}")


@router.put("/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    announcement_update: AnnouncementUpdate,
    current_user: dict = Depends(require_role("director", "hr", "manager", "lead", "super_admin")),
):
    try:
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not current_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        announcement_resp = supabase.table("announcements").select("*").eq("id", announcement_id).execute()
        if not announcement_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

        announcement_data = announcement_resp.data[0]
        if str(announcement_data.get("created_by")) != str(current_row["id"]) and current_user.get("role") not in {"hr", "director", "super_admin"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own announcements")

        update_data = announcement_update.model_dump(exclude_unset=True)
        db_update: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
        if "title" in update_data:
            db_update["title"] = update_data["title"]
        if "description" in update_data:
            db_update["description"] = update_data["description"]
            db_update["content"] = update_data["description"]
        if "priority" in update_data:
            db_update["priority"] = update_data["priority"]
        if "targetAudience" in update_data:
            db_update["target_audience"] = update_data["targetAudience"] or []
        if "expiryDate" in update_data:
            db_update["expiry_date"] = update_data["expiryDate"]
        if "status" in update_data:
            db_update["status"] = update_data["status"]
        if "isPinned" in update_data:
            db_update["is_pinned"] = update_data["isPinned"]

        response = supabase.table("announcements").update(jsonable_encoder(db_update)).eq("id", announcement_id).execute()
        updated = response.data[0] if response.data else None
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update announcement")

        announcement_public = await _announcement_to_public(updated)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_updated",
            description=f"{current_user.get('name', 'Someone')} updated announcement \"{announcement_public.get('title', '')}\".",
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "priority": announcement_public.get("priority"),
                "status": announcement_public.get("status"),
                "is_pinned": announcement_public.get("isPinned"),
            },
        )
        return jsonable_encoder(announcement_public)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating announcement: {str(e)}")


@router.post("/{announcement_id}/pin")
async def toggle_pin_announcement(
    announcement_id: str,
    pin_data: PinRequest,
    current_user: dict = Depends(require_role("director", "hr", "manager", "lead", "super_admin")),
):
    try:
        response = supabase.table("announcements").select("*").eq("id", announcement_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if str(response.data[0].get("created_by")) != str((current_row or {}).get("id")) and current_user.get("role") not in {"hr", "director", "super_admin"}:
            raise HTTPException(status_code=403, detail="You can only pin your own announcements")

        update_resp = supabase.table("announcements").update(jsonable_encoder({
            "is_pinned": pin_data.isPinned,
            "updated_at": datetime.utcnow().isoformat(),
        })).eq("id", announcement_id).execute()
        updated = update_resp.data[0] if update_resp.data else None
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update pin status")

        announcement_data = await _announcement_to_public(updated)
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_pinned" if pin_data.isPinned else "announcement_unpinned",
            description=(
                f"{current_user.get('name', 'Someone')} "
                f"{'pinned' if pin_data.isPinned else 'unpinned'} announcement \"{announcement_data.get('title', '')}\"."
            ),
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={"is_pinned": announcement_data.get("isPinned")},
        )
        return jsonable_encoder(announcement_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error toggling pin: {str(e)}")


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
        current_user: dict = Depends(require_role("director", "hr", "manager", "lead", "super_admin")),
):
    try:
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not current_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        response = supabase.table("announcements").select("*").eq("id", announcement_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

        announcement_data = response.data[0]
        if str(announcement_data.get("created_by")) != str(current_row["id"]) and current_user.get("role") not in {"hr", "director", "super_admin"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own announcements")

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="announcements",
            action="announcement_deleted",
            description=f"{current_user.get('name', 'Someone')} deleted announcement \"{announcement_data.get('title', '')}\".",
            result="success",
            target_type="announcement",
            target_id=announcement_id,
            metadata={
                "priority": announcement_data.get("priority"),
                "status": announcement_data.get("status"),
                "is_pinned": announcement_data.get("is_pinned"),
            },
        )

        supabase.table("announcements").delete().eq("id", announcement_id).execute()
        return {"message": "Announcement deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting announcement: {str(e)}")
