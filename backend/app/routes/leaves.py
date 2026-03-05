from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from app.dependencies import db, get_current_user, require_role
from app.models import LeaveCreate, LeaveUpdate, LeaveResponse
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel

router = APIRouter(prefix="/leaves", tags=["Leaves"])


class ApproveRequest(BaseModel):
    approvedBy: str


class RejectRequest(BaseModel):
    rejectedBy: str
    rejectionReason: str


@router.post("/", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave_data: LeaveCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new leave request
    """
    try:
        # Get user details
        user_ref = db.collection("users").document(leave_data.userId)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        # Prepare leave document
        leave_doc = {
            "userId": leave_data.userId,
            "userName": user_data.get("name", "Unknown"),
            "userEmail": user_data.get("email", ""),
            "department": user_data.get("department", ""),
            "designation": user_data.get("designation", ""),
            "leaveType": leave_data.leaveType,
            "startDate": leave_data.startDate,
            "endDate": leave_data.endDate,
            "totalDays": leave_data.totalDays,
            "reason": leave_data.reason,
            "status": "pending",
            "approvedBy": None,
            "approverName": None,
            "rejectionReason": None,
            "appliedDate": datetime.utcnow().isoformat(),
            "approvalDate": None,
        }
        
        # Save to Firestore
        doc_ref = db.collection("leaves").add(leave_doc)
        leave_doc["id"] = doc_ref[1].id
        
        return leave_doc
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating leave request: {str(e)}"
        )


@router.get("/", response_model=list)
async def list_leaves(
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    List leave requests
    """
    try:
        user_role = current_user.get("role")
        uid = current_user.get("uid")
        
        # Build query based on user_id parameter
        if user_id:
            query = db.collection("leaves").where("userId", "==", user_id)
        else:
            # No user_id specified - depends on role
            if user_role in ["hr", "director"]:
                query = db.collection("leaves")
            else:
                # Regular employee - only their leaves
                query = db.collection("leaves").where("userId", "==", uid)
        
        # Apply filters
        if status:
            query = query.where("status", "==", status)
        
        leaves = []
        for doc in query.stream():
            leave_data = doc.to_dict()
            leave_data["id"] = doc.id
            
            # Filter by leave_type client-side if needed (Firestore query limitations)
            if leave_type and leave_data.get("leaveType") != leave_type:
                continue
            
            leaves.append(leave_data)
        
        # Sort by applied date descending
        leaves.sort(key=lambda x: x.get("appliedDate", ""), reverse=True)
        
        return leaves
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching leaves: {str(e)}"
        )


@router.get("/pending-approvals")
async def get_pending_approvals(
    current_user: dict = Depends(get_current_user)
):
    """
    Get pending leave approvals for leads/managers
    """
    try:
        user_role = current_user.get("role")
        uid = current_user.get("uid")
        
        if user_role not in ["lead", "manager", "director", "hr"]:
            return []
        
        # Get reportees based on role
        if user_role in ["hr", "director"]:
            # Get all pending leaves
            query = db.collection("leaves").where("status", "==", "pending")
        elif user_role == "manager":
            # Get leaves from reportees
            reportees_query = db.collection("users").where("managerId", "==", uid)
            reportee_ids = [doc.id for doc in reportees_query.stream()]
            
            if not reportee_ids:
                return []
            
            # Firestore limitation: can only use 'in' with up to 10 items
            pending_leaves = []
            for i in range(0, len(reportee_ids), 10):
                batch = reportee_ids[i:i+10]
                query = db.collection("leaves")\
                    .where("userId", "in", batch)\
                    .where("status", "==", "pending")
                
                for doc in query.stream():
                    leave_data = doc.to_dict()
                    leave_data["id"] = doc.id
                    pending_leaves.append(leave_data)
            
            return pending_leaves
        else:  # lead
            # Get leaves from direct reportees
            reportees_query = db.collection("users").where("managerId", "==", uid)
            reportee_ids = [doc.id for doc in reportees_query.stream()]
            
            if not reportee_ids:
                return []
            
            pending_leaves = []
            for i in range(0, len(reportee_ids), 10):
                batch = reportee_ids[i:i+10]
                query = db.collection("leaves")\
                    .where("userId", "in", batch)\
                    .where("status", "==", "pending")
                
                for doc in query.stream():
                    leave_data = doc.to_dict()
                    leave_data["id"] = doc.id
                    pending_leaves.append(leave_data)
            
            return pending_leaves
        
        # For HR/Director
        pending_leaves = []
        for doc in query.stream():
            leave_data = doc.to_dict()
            leave_data["id"] = doc.id
            pending_leaves.append(leave_data)
        
        return pending_leaves
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching pending approvals: {str(e)}"
        )


@router.get("/balance/{user_id}")
async def get_leave_balance(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get leave balance for a user
    """
    try:
        # Check permissions
        if current_user.get("uid") != user_id and current_user.get("role") not in ["hr", "director", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user's leave balance"
            )
        
        # Get current year leaves
        current_year = datetime.utcnow().year
        query = db.collection("leaves")\
            .where("userId", "==", user_id)\
            .where("status", "==", "approved")
        
        # Default leave allocations
        total_allocations = {
            "casual": 12,
            "sick": 10,
            "annual": 15,
            "compOff": 5,
        }
        
        used_days = {
            "casual": 0,
            "sick": 0,
            "annual": 0,
            "compOff": 0,
        }
        
        total_used = 0
        
        for doc in query.stream():
            leave_data = doc.to_dict()
            # Check if leave is in current year
            start_date = datetime.fromisoformat(leave_data["startDate"].replace('Z', '+00:00'))
            if start_date.year == current_year:
                leave_type = leave_data["leaveType"]
                days = leave_data["totalDays"]
                total_used += days
                
                # Map frontend leave types to balance keys
                if leave_type == "comp-off":
                    used_days["compOff"] += days
                elif leave_type in used_days:
                    used_days[leave_type] += days
        
        # Calculate remaining
        casual = max(0, total_allocations["casual"] - used_days["casual"])
        sick = max(0, total_allocations["sick"] - used_days["sick"])
        annual = max(0, total_allocations["annual"] - used_days["annual"])
        compOff = max(0, total_allocations["compOff"] - used_days["compOff"])
        
        total_available = casual + sick + annual + compOff
        
        return {
            "userId": user_id,
            "casual": casual,
            "sick": sick,
            "annual": annual,
            "compOff": compOff,
            "totalUsed": total_used,
            "totalAvailable": total_available,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching leave balance: {str(e)}"
        )


@router.get("/stats")
async def get_leave_stats(
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """
    Get leave statistics for reports
    Manager/Director/HR only
    """
    try:
        query = db.collection("leaves")
        
        stats = {
            "totalRequests": 0,
            "pendingApprovals": 0,
            "approvedLeaves": 0,
            "rejectedLeaves": 0,
            "byType": {},
            "byDepartment": {},
        }
        
        for doc in query.stream():
            leave_data = doc.to_dict()
            stats["totalRequests"] += 1
            
            status = leave_data.get("status")
            if status == "pending":
                stats["pendingApprovals"] += 1
            elif status == "approved":
                stats["approvedLeaves"] += 1
            elif status == "rejected":
                stats["rejectedLeaves"] += 1
            
            # Count by type
            leave_type = leave_data.get("leaveType", "unknown")
            stats["byType"][leave_type] = stats["byType"].get(leave_type, 0) + 1
            
            # Count by department
            dept = leave_data.get("department", "Unknown")
            stats["byDepartment"][dept] = stats["byDepartment"].get(dept, 0) + 1
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching leave stats: {str(e)}"
        )


@router.post("/{leave_id}/approve")
async def approve_leave(
    leave_id: str,
    approve_data: ApproveRequest,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))
):
    """
    Approve leave request
    """
    try:
        leave_ref = db.collection("leaves").document(leave_id)
        leave_doc = leave_ref.get()
        
        if not leave_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Get approver details
        approver_ref = db.collection("users").document(approve_data.approvedBy)
        approver_doc = approver_ref.get()
        approver_name = approver_doc.to_dict().get("name", "Unknown") if approver_doc.exists else "Unknown"
        
        # Update leave status
        update_data = {
            "status": "approved",
            "approvedBy": approve_data.approvedBy,
            "approverName": approver_name,
            "approvalDate": datetime.utcnow().isoformat(),
        }
        leave_ref.update(update_data)
        
        # Get updated leave
        updated_doc = leave_ref.get()
        leave_data = updated_doc.to_dict()
        leave_data["id"] = leave_id
        return leave_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving leave: {str(e)}"
        )


@router.post("/{leave_id}/reject")
async def reject_leave(
    leave_id: str,
    reject_data: RejectRequest,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))
):
    """
    Reject leave request
    """
    try:
        leave_ref = db.collection("leaves").document(leave_id)
        leave_doc = leave_ref.get()
        
        if not leave_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Get rejecter details
        rejecter_ref = db.collection("users").document(reject_data.rejectedBy)
        rejecter_doc = rejecter_ref.get()
        rejecter_name = rejecter_doc.to_dict().get("name", "Unknown") if rejecter_doc.exists else "Unknown"
        
        # Update leave status
        update_data = {
            "status": "rejected",
            "approvedBy": reject_data.rejectedBy,
            "approverName": rejecter_name,
            "rejectionReason": reject_data.rejectionReason,
            "approvalDate": datetime.utcnow().isoformat(),
        }
        leave_ref.update(update_data)
        
        # Get updated leave
        updated_doc = leave_ref.get()
        leave_data = updated_doc.to_dict()
        leave_data["id"] = leave_id
        return leave_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting leave: {str(e)}"
        )

