from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.dependencies import db, get_current_user, require_role
from app.models import OnboardingRequestCreate, OnboardingRequestUpdate, OnboardingRequestResponse
from datetime import datetime
from typing import Optional
from firebase_admin import auth as firebase_auth

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_onboarding_request(
    request_data: OnboardingRequestCreate,
    current_user: dict = Depends(require_role("hr"))
):
    """
    Create employee onboarding request
    HR only - requires director approval
    """
    try:
        # Check if email already exists in users or pending requests
        existing_user = db.collection("users").where("email", "==", request_data.email).limit(1).get()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        pending_request = db.collection("onboarding_requests")\
            .where("email", "==", request_data.email)\
            .where("status", "==", "pending")\
            .limit(1).get()
        
        if pending_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pending onboarding request already exists for this email"
            )
        
        # Create onboarding request
        request_doc = {
            **request_data.model_dump(),
            "status": "pending",
            "requested_by": current_user.get("uid"),
            "requested_by_name": current_user.get("name"),
            "reviewed_by": None,
            "reviewed_by_name": None,
            "rejection_reason": None,
            "created_at": datetime.utcnow(),
            "reviewed_at": None,
        }
        
        doc_ref = db.collection("onboarding_requests").add(request_doc)
        request_doc["id"] = doc_ref[1].id
        
        return request_doc
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating onboarding request: {str(e)}"
        )


@router.get("/requests", response_model=list[OnboardingRequestResponse])
async def list_onboarding_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    """
    List onboarding requests
    HR sees their own requests, Directors see all pending requests
    """
    try:
        user_role = current_user.get("role")
        
        query = db.collection("onboarding_requests")
        
        # Apply status filter
        if status_filter:
            query = query.where("status", "==", status_filter)
        
        # HR users see only their own requests
        if user_role == "hr":
            query = query.where("requested_by", "==", current_user.get("uid"))
        # Directors see all requests (no additional filter needed)
        elif user_role != "director":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Order by created date descending
        query = query.order_by("created_at", direction="DESCENDING")
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            requests.append(OnboardingRequestResponse(**request_data))
        
        return requests
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching onboarding requests: {str(e)}"
        )


@router.get("/requests/{request_id}", response_model=OnboardingRequestResponse)
async def get_onboarding_request(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get onboarding request by ID"""
    try:
        doc = db.collection("onboarding_requests").document(request_id).get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding request not found"
            )
        
        request_data = doc.to_dict()
        request_data["id"] = doc.id
        
        # Check permissions
        user_role = current_user.get("role")
        if user_role == "hr" and request_data.get("requested_by") != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own requests"
            )
        elif user_role not in ["hr", "director"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return OnboardingRequestResponse(**request_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching onboarding request: {str(e)}"
        )


@router.patch("/requests/{request_id}/approve", status_code=status.HTTP_200_OK)
async def approve_onboarding_request(
    request_id: str,
    current_user: dict = Depends(require_role("director"))
):
    """
    Approve onboarding request and create user account
    Directors only
    """
    try:
        doc_ref = db.collection("onboarding_requests").document(request_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding request not found"
            )
        
        request_data = doc.to_dict()
        
        if request_data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Request is already {request_data.get('status')}"
            )
        
        # Create Firebase user
        try:
            # Generate temporary password (user will reset on first login)
            temp_password = f"TempPass@{datetime.utcnow().strftime('%Y%m%d')}"
            
            firebase_user = firebase_auth.create_user(
                email=request_data.get("email"),
                password=temp_password,
                display_name=request_data.get("name")
            )
            
            # Create user document in Firestore
            user_doc = {
                "email": request_data.get("email"),
                "name": request_data.get("name"),
                "phone": request_data.get("phone"),
                "role": request_data.get("role"),
                "department": request_data.get("department"),
                "designation": request_data.get("designation"),
                "manager_id": request_data.get("manager_id"),
                "lead_id": request_data.get("lead_id"),
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": None,
                "created_by": current_user.get("uid"),
            }
            
            db.collection("users").document(firebase_user.uid).set(user_doc)
            
            # Update onboarding request status
            doc_ref.update({
                "status": "approved",
                "reviewed_by": current_user.get("uid"),
                "reviewed_by_name": current_user.get("name"),
                "reviewed_at": datetime.utcnow(),
            })
            
            return {
                "message": "Onboarding request approved and user created successfully",
                "user_id": firebase_user.uid,
                "temp_password": temp_password
            }
            
        except firebase_auth.EmailAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists in Firebase"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving onboarding request: {str(e)}"
        )


@router.patch("/requests/{request_id}/reject", status_code=status.HTTP_200_OK)
async def reject_onboarding_request(
    request_id: str,
    update_data: OnboardingRequestUpdate,
    current_user: dict = Depends(require_role("director"))
):
    """
    Reject onboarding request
    Directors only
    """
    try:
        doc_ref = db.collection("onboarding_requests").document(request_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding request not found"
            )
        
        request_data = doc.to_dict()
        
        if request_data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Request is already {request_data.get('status')}"
            )
        
        if not update_data.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required"
            )
        
        # Update onboarding request status
        doc_ref.update({
            "status": "rejected",
            "reviewed_by": current_user.get("uid"),
            "reviewed_by_name": current_user.get("name"),
            "reviewed_at": datetime.utcnow(),
            "rejection_reason": update_data.rejection_reason,
        })
        
        return {
            "message": "Onboarding request rejected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting onboarding request: {str(e)}"
        )


@router.delete("/requests/{request_id}", status_code=status.HTTP_200_OK)
async def delete_onboarding_request(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete onboarding request
    HR can delete their own pending requests
    """
    try:
        doc_ref = db.collection("onboarding_requests").document(request_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding request not found"
            )
        
        request_data = doc.to_dict()
        
        # Check permissions
        if request_data.get("requested_by") != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own requests"
            )
        
        if request_data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only delete pending requests"
            )
        
        doc_ref.delete()
        
        return {
            "message": "Onboarding request deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting onboarding request: {str(e)}"
        )
