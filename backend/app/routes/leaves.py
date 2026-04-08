from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from app.dependencies import db, get_current_user, require_role, get_user_cached
from app.models import LeaveCreate, LeaveUpdate, LeaveResponse
from app.services.audit_log import log_audit_event
from app.services.zoho_smtp import send_email_smtp
from datetime import datetime
from typing import Optional, Dict
from google.cloud.firestore_v1 import FieldFilter
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
        # Validate leave type allocation
        leave_type = leave_data.leaveType
        if leave_type == "casual":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Casual leaves are not allocated. Only Sick leaves are available."
            )
        elif leave_type == "annual":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Annual leaves are not allocated. Only Sick leaves are available."
            )
        
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

        # Send email notification (Zoho SMTP) BEFORE saving
        try:
            manager_id = user_data.get("manager_id") or user_data.get("lead_id")
            manager_email = None
            manager_name = None
            if manager_id:
                manager_data = get_user_cached(manager_id)
                if manager_data:
                    manager_email = manager_data.get("email")
                    manager_name = manager_data.get("name")

            if not manager_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reporting manager email not found for this employee"
                )

            subject = f"Leave Request: {leave_doc['userName']} ({leave_doc['leaveType']})"
            body = (
                "Hello"
                + (f" {manager_name}," if manager_name else ",")
                + "\n\n"
                f"{leave_doc['userName']} has submitted a leave request for your review.\n\n"
                f"Details:\n"
                f"- Leave Type: {leave_doc['leaveType']}\n"
                f"- Dates: {leave_doc['startDate']} to {leave_doc['endDate']}\n"
                f"- Total Days: {leave_doc['totalDays']}\n"
                f"- Reason: {leave_doc['reason']}\n\n"
                "Please review and take the appropriate action at your earliest convenience.\n\n"
                "Regards,\n"
                "JoyHR"
            )

            send_email_smtp(
                to_email=manager_email,
                subject=subject,
                body=body,
                cc_emails=[leave_doc["userEmail"]] if leave_doc.get("userEmail") else None
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send leave request email: {str(e)}"
            )

        # Save to Firestore only after email succeeds
        doc_ref = db.collection("leaves").add(leave_doc)
        leave_doc["id"] = doc_ref[1].id
        
        # Audit log - leave request created
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="leave_request",
            action="leave_requested",
            description=(
                f"{current_user.get('name', 'Someone')} submitted a leave request "
                f"from {leave_doc['startDate']} to {leave_doc['endDate']} "
                f"({leave_doc['totalDays']} day(s), {leave_doc['leaveType']})."
            ),
            result="success",
            target_type="leave",
            target_id=leave_doc["id"],
            metadata={
                "user_id": leave_doc["userId"],
                "user_name": leave_doc.get("userName"),
                "leave_type": leave_doc["leaveType"],
                "start_date": leave_doc["startDate"],
                "end_date": leave_doc["endDate"],
                "total_days": leave_doc["totalDays"],
                "status": leave_doc["status"]
            }
        )

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
    Get pending leave approvals per hierarchy:
    - HR/Director: all pending
    - Manager: pending for users where manager_id or lead_id == manager
    - Lead: pending for users where lead_id == lead
    """
    try:
        user_role = current_user.get("role")
        uid = current_user.get("uid")

        if user_role not in ["lead", "manager", "director", "hr"]:
            return []

        pending_leaves = []

        if user_role in ["hr", "director"]:
            query = db.collection("leaves").where(filter=FieldFilter("status", "==", "pending"))
            for doc in query.stream():
                data = doc.to_dict()
                data["id"] = doc.id
                pending_leaves.append(data)
            return pending_leaves

        def batched_ids(ids_list):
            for i in range(0, len(ids_list), 10):
                yield ids_list[i:i+10]

        if user_role == "manager":
            # Load all users once (1 read) instead of 4 separate Firestore queries
            all_users = {doc.id: doc.to_dict() for doc in db.collection("users").stream()}
            ids = {
                user_id for user_id, data in all_users.items()
                if (data.get("manager_id") == uid or
                    data.get("managerId") == uid or
                    data.get("lead_id") == uid or
                    data.get("leadId") == uid)
            }
        else:  # lead
            # Load all users once (1 read) instead of 4 separate Firestore queries
            all_users = {doc.id: doc.to_dict() for doc in db.collection("users").stream()}
            ids = {
                user_id for user_id, data in all_users.items()
                if (data.get("manager_id") == uid or
                    data.get("managerId") == uid or
                    data.get("lead_id") == uid or
                    data.get("leadId") == uid)
            }

        if not ids:
            return []

        for batch in batched_ids(list(ids)):
            query = db.collection("leaves")\
                .where(filter=FieldFilter("userId", "in", batch))\
                .where(filter=FieldFilter("status", "==", "pending"))
            for doc in query.stream():
                data = doc.to_dict()
                data["id"] = doc.id
                pending_leaves.append(data)

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
        # Fetch all leaves for this user (approved and pending)
        all_leaves_query = db.collection("leaves").where("userId", "==", user_id)
        
        # Default leave allocations
        total_allocations = {
            "casual": 0,
            "sick": 5,
            "annual": 0,
            "compOff": 0,
        }
        
        used_days = {
            "casual": 0,
            "sick": 0,
            "annual": 0,
            "compOff": 0,
        }
        
        approved_used_days = {
            "casual": 0,
            "sick": 0,
            "annual": 0,
            "compOff": 0,
        }
        
        total_used = 0
        
        for doc in all_leaves_query.stream():
            leave_data = doc.to_dict()
            # Check if leave is in current year
            start_date = datetime.fromisoformat(leave_data["startDate"].replace('Z', '+00:00'))
            if start_date.year == current_year:
                leave_type = leave_data["leaveType"]
                days = leave_data["totalDays"]
                status = leave_data.get("status")
                
                # Count approved leaves for totalUsed
                if status == "approved":
                    total_used += days
                    if leave_type == "comp-off":
                        approved_used_days["compOff"] += days
                    elif leave_type in approved_used_days:
                        approved_used_days[leave_type] += days
                
                # Count both approved and pending for available balance
                if status in ["approved", "pending"]:
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

        # Get leave data for email and audit
        leave_data = leave_doc.to_dict()
        leave_data["id"] = leave_id

        # Send approval email BEFORE updating
        try:
            manager_id = current_user.get("uid")
            manager_email = None
            manager_doc = db.collection("users").document(manager_id).get()
            if manager_doc.exists:
                manager_info = manager_doc.to_dict()
                manager_email = manager_info.get("email")

            employee_email = leave_data.get("userEmail")
            if not employee_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Employee email not found for this leave request"
                )

            subject = "Leave Request Approved"
            body = "Your leave request has been approved."

            send_email_smtp(
                to_email=employee_email,
                subject=subject,
                body=body,
                cc_emails=[manager_email] if manager_email else None
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send approval email: {str(e)}"
            )

        # Update leave status
        update_data = {
            "status": "approved",
            "approvedBy": approve_data.approvedBy,
            "approverName": approver_name,
            "approvalDate": datetime.utcnow().isoformat(),
        }
        leave_ref.update(update_data)

        # Refresh for audit log status
        updated_doc = leave_ref.get()
        leave_data = updated_doc.to_dict()
        leave_data["id"] = leave_id

        # Audit log - leave approved
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="leave_request",
            action="leave_approved",
            description=(
                f"{current_user.get('name', 'Someone')} approved leave for "
                f"{leave_data.get('userName', leave_data.get('userId'))} "
                f"({leave_data.get('leaveType')}) from {leave_data.get('startDate')} "
                f"to {leave_data.get('endDate')}."
            ),
            result="success",
            target_type="leave",
            target_id=leave_id,
            metadata={
                "user_id": leave_data.get("userId"),
                "user_name": leave_data.get("userName"),
                "leave_type": leave_data.get("leaveType"),
                "start_date": leave_data.get("startDate"),
                "end_date": leave_data.get("endDate"),
                "status": leave_data.get("status")
            }
        )

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

        # Get leave data for email and audit
        leave_data = leave_doc.to_dict()
        leave_data["id"] = leave_id

        # Send rejection email BEFORE updating
        try:
            manager_id = current_user.get("uid")
            manager_email = None
            manager_doc = db.collection("users").document(manager_id).get()
            if manager_doc.exists:
                manager_info = manager_doc.to_dict()
                manager_email = manager_info.get("email")

            employee_email = leave_data.get("userEmail")
            if not employee_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Employee email not found for this leave request"
                )

            subject = "Leave Request Rejected"
            body = "Your leave request has been rejected."

            send_email_smtp(
                to_email=employee_email,
                subject=subject,
                body=body,
                cc_emails=[manager_email] if manager_email else None
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send rejection email: {str(e)}"
            )

        # Update leave status
        update_data = {
            "status": "rejected",
            "approvedBy": reject_data.rejectedBy,
            "approverName": rejecter_name,
            "rejectionReason": reject_data.rejectionReason,
            "approvalDate": datetime.utcnow().isoformat(),
        }
        leave_ref.update(update_data)

        # Refresh for audit log status
        updated_doc = leave_ref.get()
        leave_data = updated_doc.to_dict()
        leave_data["id"] = leave_id

        # Audit log - leave rejected
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="leave_request",
            action="leave_rejected",
            description=(
                f"{current_user.get('name', 'Someone')} rejected leave for "
                f"{leave_data.get('userName', leave_data.get('userId'))} "
                f"({leave_data.get('leaveType')}) from {leave_data.get('startDate')} "
                f"to {leave_data.get('endDate')}. Reason: {leave_data.get('rejectionReason')}."
            ),
            result="success",
            target_type="leave",
            target_id=leave_id,
            metadata={
                "user_id": leave_data.get("userId"),
                "user_name": leave_data.get("userName"),
                "leave_type": leave_data.get("leaveType"),
                "start_date": leave_data.get("startDate"),
                "end_date": leave_data.get("endDate"),
                "status": leave_data.get("status"),
                "rejection_reason": leave_data.get("rejectionReason")
            }
        )

        return leave_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting leave: {str(e)}"
        )

