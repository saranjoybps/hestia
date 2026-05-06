from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from firebase_admin import auth as firebase_auth

from app.dependencies import get_current_user, invalidate_user_cache, require_role, supabase
from app.models import UserCreate, UserResponse, UserUpdate
from app.services.audit_log import log_audit_event
from app.services.zoho_smtp import send_onboarding_email
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/users", tags=["Users"])


def build_full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    parts = [part for part in [first_name, last_name] if part]
    return " ".join(parts)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_role("hr", "director")),
):
    try:
        if user_data.role == "director" and current_user.get("created_by") != "system":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super administrator can create director accounts",
            )

        display_name = build_full_name(user_data.name, user_data.last_name) or user_data.name
        firebase_user = firebase_auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=display_name,
        )

        payload = {
            "firebase_uid": firebase_user.uid,
            "email": user_data.email,
            "name": user_data.name,
            "last_name": user_data.last_name,
            "phone": user_data.phone,
            "role": user_data.role,
            "department": user_data.department,
            "designation": user_data.designation,
            "date_of_joining": user_data.dateOfJoining,
            "manager_id": user_data.manager_id,
            "lead_id": user_data.lead_id,
            "status": user_data.status,
            "created_by": current_user.get("uid"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
        }

        response = supabase.table("users").insert(payload).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create Supabase user record",
            )

        user_doc = SupabaseHelper._public_user(response.data[0]) or {}
        user_doc["uid"] = firebase_user.uid

        try:
            send_onboarding_email(
                to_email=user_data.email,
                employee_name=display_name,
                password=user_data.password,
                role=user_data.role,
                department=user_data.department,
                designation=user_data.designation,
                manager=user_data.manager_id,
                lead=user_data.lead_id,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send onboarding email: {str(e)}",
            )

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="employees",
            action="employee_created",
            description=(
                f"{current_user.get('name', 'Someone')} created an employee account for "
                f"{display_name or user_doc.get('name', firebase_user.uid)}."
            ),
            result="success",
            target_type="user",
            target_id=firebase_user.uid,
            metadata={
                "role": user_doc.get("role"),
                "department": user_doc.get("department"),
                "designation": user_doc.get("designation"),
                "status": user_doc.get("status"),
            },
        )

        return UserResponse(**user_doc)

    except firebase_auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )


@router.get("/")
async def list_users(
    department: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    role: Optional[list[str]] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    result = await SupabaseHelper.list_public_users(
        department=department,
        status_filter=status_filter,
        roles=role,
        search=search,
        page=page,
        limit=limit,
    )
    users = [UserResponse(**user) for user in result["users"]]
    return {
        "users": users,
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
        "totalPages": result["totalPages"],
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user_data = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(**user_data)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    is_admin = current_user.get("role") in ["hr", "director"]
    is_self = current_user.get("uid") == user_id
    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    existing = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"] == "director":
        if current_user.get("created_by") != "system":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super administrator can assign director role",
            )

    if not is_admin:
        update_data = {k: v for k, v in update_data.items() if k in ["name", "last_name", "phone"]}

    if "dateOfJoining" in update_data:
        update_data["date_of_joining"] = update_data.pop("dateOfJoining")

    update_data["updated_at"] = datetime.utcnow().isoformat()

    response = supabase.table("users").update(update_data).eq("firebase_uid", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated = SupabaseHelper._public_user(response.data[0]) or {}
    updated["uid"] = user_id
    invalidate_user_cache(user_id)

    log_audit_event(
        actor_id=current_user.get("uid"),
        actor_name=current_user.get("name"),
        actor_email=current_user.get("email"),
        module="employees",
        action="employee_updated",
        description=(
            f"{current_user.get('name', 'Someone')} updated profile details for "
            f"{existing.get('name', user_id)}."
        ),
        result="success",
        target_type="user",
        target_id=user_id,
        metadata={"updated_fields": list(update_data.keys())},
    )

    return UserResponse(**updated)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(require_role("director", "hr")),
):
    response = supabase.table("users").update({
        "status": "inactive",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("firebase_uid", user_id).execute()

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    firebase_auth.update_user(user_id, disabled=True)
    invalidate_user_cache(user_id)
    return {"message": "User deactivated successfully"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: dict = Depends(require_role("director", "hr")),
):
    response = supabase.table("users").update({
        "status": "active",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("firebase_uid", user_id).execute()

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    firebase_auth.update_user(user_id, disabled=False)
    invalidate_user_cache(user_id)
    return {"message": "User activated successfully"}


@router.get("/{user_id}/reportees", response_model=list[UserResponse])
async def get_reportees(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ["lead", "manager", "director"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only leads, managers, and directors can view reportees",
        )

    reportees = await SupabaseHelper.get_reportees(user_id)
    return [UserResponse(**reportee) for reportee in reportees]
