from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from firebase_admin import auth as firebase_auth

from app.dependencies import get_current_user, require_role, supabase
from app.models import OnboardingRequestCreate, OnboardingRequestUpdate, OnboardingRequestResponse
from app.services.zoho_smtp import send_onboarding_email
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def build_full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    parts = [part for part in [first_name, last_name] if part]
    return " ".join(parts)


async def _request_to_public(row):
    requester = await SupabaseHelper.get_public_user_by_id(row.get("requested_by")) if row.get("requested_by") else None
    reviewer = await SupabaseHelper.get_public_user_by_id(row.get("reviewed_by")) if row.get("reviewed_by") else None
    return {
        "id": str(row.get("id")),
        "email": row.get("email"),
        "name": row.get("name"),
        "last_name": row.get("last_name"),
        "phone": row.get("phone"),
        "role": row.get("role"),
        "department": row.get("department"),
        "designation": row.get("designation"),
        "dateOfJoining": row.get("date_of_joining"),
        "manager_id": row.get("manager_id"),
        "lead_id": row.get("lead_id"),
        "notes": row.get("notes"),
        "status": row.get("status"),
        "requested_by": requester.get("uid") if requester else None,
        "requested_by_name": row.get("requested_by_name") or (requester.get("name") if requester else None),
        "reviewed_by": reviewer.get("uid") if reviewer else None,
        "reviewed_by_name": row.get("reviewed_by_name") or (reviewer.get("name") if reviewer else None),
        "rejection_reason": row.get("rejection_reason"),
        "created_at": row.get("created_at"),
        "reviewed_at": row.get("reviewed_at"),
    }


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_onboarding_request(
    request_data: OnboardingRequestCreate,
    current_user: dict = Depends(require_role("hr")),
):
    try:
        existing_user = supabase.table("users").select("id").eq("email", request_data.email).limit(1).execute()
        if existing_user.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

        pending_request = supabase.table("onboarding_requests").select("id").eq("email", request_data.email).eq("status", "pending").limit(1).execute()
        if pending_request.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pending onboarding request already exists for this email")

        requester_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not requester_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        request_doc = {
            "email": request_data.email,
            "name": request_data.name,
            "last_name": request_data.last_name,
            "phone": request_data.phone,
            "role": request_data.role,
            "department": request_data.department,
            "designation": request_data.designation,
            "date_of_joining": request_data.dateOfJoining,
            "manager_id": request_data.manager_id,
            "lead_id": request_data.lead_id,
            "notes": request_data.notes,
            "status": "pending",
            "requested_by": str(requester_row["id"]),
            "requested_by_name": current_user.get("name"),
            "reviewed_by": None,
            "reviewed_by_name": None,
            "rejection_reason": None,
            "created_at": datetime.utcnow().isoformat(),
            "reviewed_at": None,
        }

        response = supabase.table("onboarding_requests").insert(request_doc).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create onboarding request")
        return await _request_to_public(inserted)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating onboarding request: {str(e)}")


@router.get("/requests", response_model=list[OnboardingRequestResponse])
async def list_onboarding_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_role = current_user.get("role")
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not current_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        query = supabase.table("onboarding_requests").select("*")
        if status_filter:
            query = query.eq("status", status_filter)
        if user_role == "hr":
            query = query.eq("requested_by", str(current_row["id"]))
        elif user_role != "director":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        resp = query.order("created_at", desc=True).execute()
        requests = [await _request_to_public(row) for row in (resp.data or [])]
        return requests
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching onboarding requests: {str(e)}")


@router.get("/requests/{request_id}", response_model=OnboardingRequestResponse)
async def get_onboarding_request(request_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = supabase.table("onboarding_requests").select("*").eq("id", request_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding request not found")

        request_data = await _request_to_public(doc.data)
        user_role = current_user.get("role")
        if user_role == "hr":
            current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
            if not current_row or request_data.get("requested_by") != current_user.get("uid"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own requests")
        elif user_role not in ["hr", "director"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        return request_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching onboarding request: {str(e)}")


@router.patch("/requests/{request_id}/approve", status_code=status.HTTP_200_OK)
async def approve_onboarding_request(request_id: str, current_user: dict = Depends(require_role("director"))):
    try:
        doc = supabase.table("onboarding_requests").select("*").eq("id", request_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding request not found")

        request_data = doc.data[0]
        if request_data.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {request_data.get('status')}")

        temp_password = f"TempPass@{datetime.utcnow().strftime('%Y%m%d')}"
        display_name = build_full_name(request_data.get("name"), request_data.get("last_name")) or request_data.get("name")

        try:
            firebase_user = firebase_auth.create_user(
                email=request_data.get("email"),
                password=temp_password,
                display_name=display_name,
            )
        except firebase_auth.EmailAlreadyExistsError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists in Firebase")

        requester_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not requester_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        user_doc = {
            "firebase_uid": firebase_user.uid,
            "email": request_data.get("email"),
            "name": request_data.get("name"),
            "last_name": request_data.get("last_name"),
            "phone": request_data.get("phone"),
            "role": request_data.get("role"),
            "department": request_data.get("department"),
            "designation": request_data.get("designation"),
            "date_of_joining": request_data.get("date_of_joining"),
            "manager_id": request_data.get("manager_id"),
            "lead_id": request_data.get("lead_id"),
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
            "created_by": current_user.get("uid"),
        }
        supabase.table("users").insert(user_doc).execute()

        supabase.table("onboarding_requests").update({
            "status": "approved",
            "reviewed_by": str(requester_row["id"]),
            "reviewed_by_name": current_user.get("name"),
            "reviewed_at": datetime.utcnow().isoformat(),
        }).eq("id", request_id).execute()

        try:
            send_onboarding_email(
                to_email=request_data.get("email"),
                employee_name=display_name,
                password=temp_password,
                role=request_data.get("role"),
                department=request_data.get("department"),
                designation=request_data.get("designation"),
                manager=request_data.get("manager_id"),
                lead=request_data.get("lead_id"),
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send onboarding email: {str(e)}")

        return {
            "message": "Onboarding request approved and user created successfully",
            "user_id": firebase_user.uid,
            "temp_password": temp_password,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error approving onboarding request: {str(e)}")


@router.patch("/requests/{request_id}/reject", status_code=status.HTTP_200_OK)
async def reject_onboarding_request(
    request_id: str,
    update_data: OnboardingRequestUpdate,
    current_user: dict = Depends(require_role("director")),
):
    try:
        doc = supabase.table("onboarding_requests").select("*").eq("id", request_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding request not found")

        request_data = doc.data[0]
        if request_data.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {request_data.get('status')}")
        if not update_data.rejection_reason:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection reason is required")

        reviewer_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not reviewer_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current user not found")

        supabase.table("onboarding_requests").update({
            "status": "rejected",
            "reviewed_by": str(reviewer_row["id"]),
            "reviewed_by_name": current_user.get("name"),
            "reviewed_at": datetime.utcnow().isoformat(),
            "rejection_reason": update_data.rejection_reason,
        }).eq("id", request_id).execute()

        return {"message": "Onboarding request rejected successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error rejecting onboarding request: {str(e)}")


@router.delete("/requests/{request_id}", status_code=status.HTTP_200_OK)
async def delete_onboarding_request(request_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = supabase.table("onboarding_requests").select("*").eq("id", request_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding request not found")

        request_data = doc.data[0]
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        if not current_row or str(request_data.get("requested_by")) != str(current_row["id"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own requests")
        if request_data.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only delete pending requests")

        supabase.table("onboarding_requests").delete().eq("id", request_id).execute()
        return {"message": "Onboarding request deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting onboarding request: {str(e)}")
