from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_user, require_role, supabase
from app.models import LeaveCreate, LeaveResponse, LeaveUpdate
from app.services.audit_log import log_audit_event
from app.services.zoho_smtp import send_email_smtp
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/leaves", tags=["Leaves"])


class ApproveRequest(BaseModel):
    approvedBy: str


class RejectRequest(BaseModel):
    rejectedBy: str
    rejectionReason: str


def _leave_row(row: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    user = user_map.get(str(row.get("user_id")), {})
    approver = user_map.get(str(row.get("approved_by")), {})

    return {
        "id": str(row.get("id")),
        "userId": user.get("uid") or str(row.get("user_id")),
        "userName": user.get("name"),
        "userEmail": user.get("email"),
        "leaveType": row.get("leave_type"),
        "startDate": str(row.get("start_date")),
        "endDate": str(row.get("end_date")),
        "totalDays": float(row.get("number_of_days") or 0),
        "reason": row.get("reason") or "",
        "status": row.get("status"),
        "approvedBy": approver.get("uid"),
        "approverName": approver.get("name"),
        "rejectionReason": row.get("rejection_reason"),
        "appliedDate": row.get("created_at"),
        "approvalDate": row.get("approved_at"),
        "department": user.get("department"),
        "designation": user.get("designation"),
    }


async def _load_user_map() -> Dict[str, Dict[str, Any]]:
    return await SupabaseHelper.get_public_user_map()


@router.post("/", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave_data: LeaveCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        leave_type = leave_data.leaveType
        if leave_type == "casual":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Casual leaves are not allocated. Only Sick leaves are available.")
        if leave_type == "annual":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Annual leaves are not allocated. Only Sick leaves are available.")

        employee = await SupabaseHelper.get_public_user_by_firebase_uid(leave_data.userId)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        manager_id = employee.get("manager_id") or employee.get("lead_id")
        manager_data = await SupabaseHelper.get_public_user_by_firebase_uid(manager_id) if manager_id else None

        if not manager_data or not manager_data.get("email"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reporting manager email not found for this employee")

        subject = f"Leave Request: {employee.get('name', 'Employee')} ({leave_type})"
        body = (
            "Hello"
            + (f" {manager_data.get('name')}," if manager_data.get("name") else ",")
            + "\n\n"
            f"{employee.get('name', 'Employee')} has submitted a leave request for your review.\n\n"
            f"Details:\n"
            f"- Leave Type: {leave_type}\n"
            f"- Dates: {leave_data.startDate} to {leave_data.endDate}\n"
            f"- Total Days: {leave_data.totalDays}\n"
            f"- Reason: {leave_data.reason}\n\n"
            "Please review and take the appropriate action at your earliest convenience.\n\n"
            "Regards,\n"
            "JoyHR"
        )

        send_email_smtp(
            to_email=manager_data["email"],
            subject=subject,
            body=body,
            cc_emails=[employee.get("email")] if employee.get("email") else None,
        )

        insert_payload = {
            "user_id": employee["id"],
            "leave_type": leave_type,
            "start_date": leave_data.startDate,
            "end_date": leave_data.endDate,
            "number_of_days": leave_data.totalDays,
            "reason": leave_data.reason,
            "status": "pending",
            "approved_by": None,
            "approved_at": None,
            "rejection_reason": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("leaves").insert(insert_payload).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create leave request")

        user_map = await _load_user_map()
        leave_doc = _leave_row(response.data[0], user_map)

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
                "status": leave_doc["status"],
            },
        )

        return LeaveResponse(**leave_doc)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating leave request: {str(e)}")


@router.get("/", response_model=list[LeaveResponse])
async def list_leaves(
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = supabase.table("leaves").select("*")

        if user_id:
            employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
            if employee:
                query = query.eq("user_id", employee["id"])
            else:
                return []
        else:
            if current_user.get("role") not in ["hr", "director"]:
                internal_id = current_user.get("id")
                if not internal_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not resolve user identity")
                query = query.eq("user_id", internal_id)

        if status:
            query = query.eq("status", status)
        if leave_type:
            query = query.eq("leave_type", leave_type)

        response = query.execute()
        user_map = await _load_user_map()
        leaves = [_leave_row(row, user_map) for row in (response.data or [])]
        leaves.sort(key=lambda x: x.get("appliedDate", ""), reverse=True)
        return [LeaveResponse(**leave) for leave in leaves]

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leaves: {str(e)}")


@router.get("/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))):
    try:
        user_map = await _load_user_map()
        role = current_user.get("role")
        response = supabase.table("leaves").select("*").eq("status", "pending").execute()
        rows = response.data or []
        if role not in ["hr", "director"]:
            reportees = await SupabaseHelper.get_reportees(current_user.get("uid"))
            reportee_ids = {row.get("id") for row in reportees if row.get("id")}
            rows = [row for row in rows if str(row.get("user_id")) in reportee_ids]

        leaves = [_leave_row(row, user_map) for row in rows]
        return [LeaveResponse(**leave) for leave in leaves]

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching pending approvals: {str(e)}")


@router.get("/balance/{user_id}")
async def get_leave_balance(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        response = supabase.table("leaves").select("*").eq("user_id", employee["id"]).eq("status", "approved").execute()
        rows = response.data or []

        sick_used = sum(float(row.get("number_of_days") or 0) for row in rows if row.get("leave_type") == "sick")
        total_used = sum(float(row.get("number_of_days") or 0) for row in rows)

        sick_total = 5
        return {
            "userId": user_id,
            "casual": 0,
            "sick": max(0, sick_total - sick_used),
            "annual": 0,
            "compOff": 0,
            "totalUsed": total_used,
            "totalAvailable": max(0, sick_total - sick_used),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leave balance: {str(e)}")


@router.get("/stats")
async def get_leave_stats(current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("leaves").select("*").execute()
        rows = response.data or []
        user_map = await _load_user_map()

        total_requests = len(rows)
        pending = [row for row in rows if row.get("status") == "pending"]
        approved = [row for row in rows if row.get("status") == "approved"]
        rejected = [row for row in rows if row.get("status") == "rejected"]

        by_type: Dict[str, int] = {}
        by_department: Dict[str, int] = {}
        for row in rows:
            leave_type = row.get("leave_type") or "unknown"
            by_type[leave_type] = by_type.get(leave_type, 0) + 1
            user = user_map.get(str(row.get("user_id")), {})
            department = user.get("department") or "Unknown"
            by_department[department] = by_department.get(department, 0) + 1

        return {
            "totalRequests": total_requests,
            "pendingApprovals": len(pending),
            "approvedLeaves": len(approved),
            "rejectedLeaves": len(rejected),
            "byType": by_type,
            "byDepartment": by_department,
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leave stats: {str(e)}")


@router.get("/{leave_id}", response_model=LeaveResponse)
async def get_leave(leave_id: str, current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        user_map = await _load_user_map()
        return LeaveResponse(**_leave_row(response.data[0], user_map))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leave request: {str(e)}")


@router.post("/{leave_id}/approve", status_code=status.HTTP_200_OK)
async def approve_leave(
    leave_id: str,
    payload: ApproveRequest = Body(...),
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr")),
):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

        approver = await SupabaseHelper.get_public_user_by_firebase_uid(payload.approvedBy)
        if not approver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        update_response = supabase.table("leaves").update({
            "status": "approved",
            "approved_by": approver["id"],
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "rejection_reason": None,
        }).eq("id", leave_id).execute()

        if not update_response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to approve leave")

        return {"message": "Leave request approved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error approving leave: {str(e)}")


@router.post("/{leave_id}/reject", status_code=status.HTTP_200_OK)
async def reject_leave(
    leave_id: str,
    payload: RejectRequest = Body(...),
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr")),
):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

        rejecter = await SupabaseHelper.get_public_user_by_firebase_uid(payload.rejectedBy)
        if not rejecter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rejecter not found")

        update_response = supabase.table("leaves").update({
            "status": "rejected",
            "approved_by": rejecter["id"],
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "rejection_reason": payload.rejectionReason,
        }).eq("id", leave_id).execute()

        if not update_response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reject leave")

        return {"message": "Leave request rejected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error rejecting leave: {str(e)}")
