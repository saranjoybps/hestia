from fastapi import APIRouter, Depends, HTTPException, status, Query
from firebase_admin import auth as firebase_auth
from app.dependencies import db, get_current_user, require_role
from app.services.audit_log import log_audit_event
from app.models import UserCreate, UserUpdate, UserResponse
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_role("hr", "director"))
):
    """
    Register a new user (HR/Director only)
    Creates user in Firebase Auth and Firestore
    """
    try:
        # Only super admin (created_by: system) can create directors
        if user_data.role == "director" and current_user.get("created_by") != "system":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super administrator can create director accounts"
            )
        
        # Create user in Firebase Auth
        firebase_user = firebase_auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.name
        )
        
        # Prepare user document for Firestore
        user_doc = {
            "email": user_data.email,
            "name": user_data.name,
            "phone": user_data.phone,
            "role": user_data.role,
            "department": user_data.department,
            "designation": user_data.designation,
            "manager_id": user_data.manager_id,
            "lead_id": user_data.lead_id,
            "status": user_data.status,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
            "created_by": current_user.get("uid")
        }
        
        # Save to Firestore
        db.collection("users").document(firebase_user.uid).set(user_doc)
        
        # TODO: Send welcome email
        
        user_doc["uid"] = firebase_user.uid

        # Audit log - employee created
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="employees",
            action="employee_created",
            description=(
                f"{current_user.get('name', 'Someone')} created an employee account for "
                f"{user_doc.get('name', firebase_user.uid)}."
            ),
            result="success",
            target_type="user",
            target_id=firebase_user.uid,
            metadata={
                "role": user_doc.get("role"),
                "department": user_doc.get("department"),
                "designation": user_doc.get("designation"),
                "status": user_doc.get("status")
            }
        )

        return UserResponse(**user_doc)
        
    except firebase_auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )


@router.get("/")
async def list_users(
    department: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    role: Optional[list[str]] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    List users with filtering and pagination
    Optimized to reduce database reads
    """
    try:
        query = db.collection("users")
        
        # Apply filters at database level
        if department:
            query = query.where("department", "==", department)
        if status_filter:
            query = query.where("status", "==", status_filter)
        
        # Handle role filter (can be multiple roles)
        if role and len(role) > 0 and len(role) <= 10:
            # Firestore 'in' query supports up to 10 values
            query = query.where("role", "in", role)
        
        # For search queries or counting, we need to fetch the results
        # Firestore doesn't support efficient counting without fetching
        if search:
            # Search requires client-side filtering
            users = query.stream()
            user_list = []
            
            for user in users:
                user_data = user.to_dict()
                user_data["uid"] = user.id
                
                # Apply search filter
                if search.lower() in user_data.get("name", "").lower() or \
                   search.lower() in user_data.get("email", "").lower():
                    user_list.append(user_data)
            
            # Get total count and paginate in memory
            total = len(user_list)
            start = (page - 1) * limit
            end = start + limit
            paginated_users = user_list[start:end]
            
        else:
            # No search - use database-level pagination for better performance
            # Calculate offset
            offset = (page - 1) * limit
            
            # Fetch one extra record to check if there are more pages
            # This avoids expensive count queries
            paginated_query = query.limit(limit + 1).offset(offset)
            
            paginated_users = []
            has_more = False
            
            for idx, user in enumerate(paginated_query.stream()):
                if idx < limit:
                    user_data = user.to_dict()
                    user_data["uid"] = user.id
                    paginated_users.append(user_data)
                else:
                    # Found the extra record, so there are more pages
                    has_more = True
                    break
            
            # Estimate total (not exact, but avoids expensive count)
            # For exact count on first page, do a quick count
            if page == 1 and not has_more:
                # We're on first page and no more results, so count is accurate
                total = len(paginated_users)
            else:
                # Estimate: current page items + pages * limit + (1 if more)
                total = offset + len(paginated_users) + (limit if has_more else 0)
        
        # Convert to response models
        user_responses = [UserResponse(**user) for user in paginated_users]
        
        return {
            "users": user_responses,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": (total + limit - 1) // limit if total > 0 else 1
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching users: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile"""
    return UserResponse(**current_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user by ID"""
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        user_data["uid"] = user_id
        return UserResponse(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user: {str(e)}"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user information
    HR/Director can update all fields
    Users can only update their own personal fields
    """
    try:
        print(f"=== UPDATE USER REQUEST ===")
        print(f"User ID: {user_id}")
        print(f"Current user role: {current_user.get('role')}")
        print(f"Update data: {user_update.model_dump()}")
        
        # Check permissions
        is_admin = current_user.get("role") in ["hr", "director"]
        is_self = current_user.get("uid") == user_id
        
        print(f"Is admin: {is_admin}, Is self: {is_self}")
        
        if not is_admin and not is_self:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
        
        # Get existing user
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        original_data = user_doc.to_dict()

        # Prepare update data
        update_data = user_update.model_dump(exclude_unset=True)
        
        print(f"Update data (exclude_unset): {update_data}")
        
        # Only super admin can change role to director
        if "role" in update_data and update_data["role"] == "director":
            if current_user.get("created_by") != "system":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only super administrator can assign director role"
                )
        
        # If not admin, restrict fields
        if not is_admin:
            allowed_fields = ["name", "phone"]
            update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        print(f"Final update data: {update_data}")
        
        # Update Firestore
        user_ref.update(update_data)
        
        print(f"✅ User updated successfully in Firestore")
        
        # Create audit log
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="employees",
            action="employee_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated profile details for "
                f"{original_data.get('name', user_id)}."
            ),
            result="success",
            target_type="user",
            target_id=user_id,
            metadata={"updated_fields": list(update_data.keys())}
        )
        
        # Return updated user data by merging original with updates
        original_data.update(update_data)
        original_data["uid"] = user_id
        
        print(f"📤 Returning updated user: {original_data}")
        
        return UserResponse(**original_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(require_role("director", "hr"))
):
    """
    Deactivate user (soft delete)
    Director/HR only
    """
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update status to inactive
        user_ref.update({
            "status": "inactive",
            "updated_at": datetime.utcnow().isoformat(),
            "deactivated_by": current_user.get("uid")
        })
        
        # Disable Firebase Auth account
        firebase_auth.update_user(user_id, disabled=True)

        # Audit log - employee deactivated
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="employees",
            action="employee_deactivated",
            description=(
                f"{current_user.get('name', 'Someone')} deactivated employee "
                f"{user_doc.to_dict().get('name', user_id)}."
            ),
            result="success",
            target_type="user",
            target_id=user_id,
            metadata={
                "status": "inactive"
            }
        )

        return {"message": "User deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deactivating user: {str(e)}"
        )


@router.get("/{user_id}/reportees", response_model=list[UserResponse])
async def get_reportees(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all reportees for a Lead or Manager
    """
    try:
        # Check if user is lead or manager
        user_role = current_user.get("role")
        if user_role not in ["lead", "manager", "director"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only leads, managers, and directors can view reportees"
            )
        
        # Query reportees
        reportees = []
        
        if user_role == "lead":
            query = db.collection("users").where("lead_id", "==", user_id)
        elif user_role in ["manager", "director"]:
            query = db.collection("users").where("manager_id", "==", user_id)
        
        for doc in query.stream():
            user_data = doc.to_dict()
            user_data["uid"] = doc.id
            reportees.append(UserResponse(**user_data))
        
        return reportees
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching reportees: {str(e)}"
        )
