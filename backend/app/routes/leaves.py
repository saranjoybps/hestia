import asyncio
from datetime import date, datetime
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


async def _assert_leave_scope(current_user: Dict[str, Any], employee: Dict[str, Any], *, allow_self: bool = True) -> None:
    uid = str(employee.get("uid") or "")
    if allow_self and uid and uid == str(current_user.get("uid")):
        return
    role = current_user.get("role")
    if role in {"hr", "director", "super_admin"}:
        return
    if role in {"lead", "manager"}:
        reportees = await SupabaseHelper.get_reportees(str(current_user.get("uid")))
        ids = {str(value) for row in reportees for value in (row.get("uid"), row.get("id")) if value}
        if uid in ids or str(employee.get("id")) in ids:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access leave records outside your authorized scope")


@router.post("/", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave_data: LeaveCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        leave_type = leave_data.leaveType
        try:
            start_day = date.fromisoformat(leave_data.startDate)
            end_day = date.fromisoformat(leave_data.endDate)
        except ValueError:
            raise HTTPException(status_code=422, detail="Leave dates must use YYYY-MM-DD format")
        if end_day < start_day:
            raise HTTPException(status_code=422, detail="End date must be on or after the start date")
        total_days = (end_day - start_day).days + 1
        if not leave_data.reason.strip():
            raise HTTPException(status_code=422, detail="A reason is required for a leave request")

        employee = await SupabaseHelper.get_public_user_by_firebase_uid(leave_data.userId)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if employee.get("uid") != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only request leave for yourself")

        overlap = supabase.table("leaves").select("id").eq("user_id", str(employee["id"])).in_("status", ["pending", "approved"]).lte("start_date", end_day.isoformat()).gte("end_date", start_day.isoformat()).execute().data or []
        if overlap:
            raise HTTPException(status_code=409, detail="This request overlaps an existing pending or approved leave")

        insert_payload = {
            "user_id": employee["id"],
            "leave_type": leave_type,
            "start_date": leave_data.startDate,
            "end_date": leave_data.endDate,
            "number_of_days": total_days,
            "reason": leave_data.reason.strip(),
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

        # Email is a notification only. Missing reporting contact details must
        # never prevent a leave request from entering the in-app approval queue.
        reporting_id = employee.get("lead_id") or employee.get("manager_id")
        manager_data = next((row for row in user_map.values() if reporting_id and str(row.get("uid")) == str(reporting_id)), None)
        if not manager_data and reporting_id:
            manager_data = next((row for row in user_map.values() if str(row.get("id")) == str(reporting_id)), None)
        if manager_data and manager_data.get("email"):
            subject = f"Leave Request: {employee.get('name', 'Employee')} ({leave_type})"
            body = (f"Hello {manager_data.get('name') or 'Manager'},\n\n"
                    f"{employee.get('name', 'Employee')} submitted a leave request.\n"
                    f"Dates: {leave_data.startDate} to {leave_data.endDate} ({total_days} days)\n"
                    f"Reason: {leave_data.reason.strip()}\n\nReview it in Hestia.")
            try:
                await asyncio.to_thread(send_email_smtp, to_email=manager_data["email"], subject=subject, body=body,
                                        cc_emails=[employee.get("email")] if employee.get("email") else None)
            except Exception:
                pass

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
                await _assert_leave_scope(current_user, employee)
                query = query.eq("user_id", employee["id"])
            else:
                return []
        else:
            role = current_user.get("role")
            if role in {"lead", "manager"}:
                reportees = await SupabaseHelper.get_reportees(str(current_user.get("uid")))
                allowed_ids = {str(row.get("id")) for row in reportees if row.get("id")}
                current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
                if current_row and current_row.get("id"):
                    allowed_ids.add(str(current_row["id"]))
                if not allowed_ids:
                    return []
                query = query.in_("user_id", list(allowed_ids))
            elif role not in {"hr", "director", "super_admin"}:
                internal_id = current_user.get("id")
                if not internal_id:
                    current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
                    internal_id = current_row.get("id") if current_row else None
                if not internal_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not resolve user identity")
                query = query.eq("user_id", str(internal_id))

        if status:
            query = query.eq("status", status)
        if leave_type:
            query = query.eq("leave_type", leave_type)

        response = query.execute()
        user_map = await _load_user_map()
        leaves = [_leave_row(row, user_map) for row in (response.data or [])]
        leaves.sort(key=lambda x: x.get("appliedDate", ""), reverse=True)
        return [LeaveResponse(**leave) for leave in leaves]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leaves: {str(e)}")


@router.get("/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin"))):
    try:
        user_map = await _load_user_map()
        role = current_user.get("role")
        response = supabase.table("leaves").select("*").eq("status", "pending").execute()
        rows = response.data or []
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        rows = [row for row in rows if str(row.get("user_id")) != str(current_row.get("id"))] if current_row else []
        if role not in ["hr", "director", "super_admin"]:
            reportees = await SupabaseHelper.get_reportees(current_user.get("uid"))
            reportee_ids = {str(row.get("id")) for row in reportees if row.get("id")}
            rows = [row for row in rows if str(row.get("user_id")) in reportee_ids]

        leaves = [_leave_row(row, user_map) for row in rows]
        return [LeaveResponse(**leave) for leave in leaves]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching pending approvals: {str(e)}")


@router.get("/balance/{user_id}")
async def get_leave_balance(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        employee = await SupabaseHelper.get_public_user_by_firebase_uid(user_id)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        await _assert_leave_scope(current_user, employee)

        response = supabase.table("leaves").select("*").eq("user_id", employee["id"]).eq("status", "approved").execute()
        rows = response.data or []

        total_used = sum(float(row.get("number_of_days") or 0) for row in rows)
        by_type: Dict[str, float] = {}
        for row in rows:
            leave_type = str(row.get("leave_type") or "other")
            by_type[leave_type] = by_type.get(leave_type, 0) + float(row.get("number_of_days") or 0)
        return {
            "userId": user_id,
            "totalUsed": total_used,
            "byTypeUsed": by_type,
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
        role = current_user.get("role")
        if role not in {"hr", "director", "super_admin"}:
            if role in {"lead", "manager"}:
                reportees = await SupabaseHelper.get_reportees(str(current_user.get("uid")))
                allowed_ids = {str(row.get("id")) for row in reportees if row.get("id")}
                allowed_ids.add(str(current_user.get("id")))
            else:
                allowed_ids = {str(current_user.get("id"))}
            rows = [row for row in rows if str(row.get("user_id")) in allowed_ids]

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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leave stats: {str(e)}")


@router.get("/{leave_id}", response_model=LeaveResponse)
async def get_leave(leave_id: str, current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        user_map = await _load_user_map()
        employee = user_map.get(str(response.data[0].get("user_id")))
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        await _assert_leave_scope(current_user, employee)
        return LeaveResponse(**_leave_row(response.data[0], user_map))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching leave request: {str(e)}")


@router.post("/{leave_id}/approve", status_code=status.HTTP_200_OK)
async def approve_leave(
    leave_id: str,
    payload: ApproveRequest = Body(...),
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        leave = response.data[0]
        user_map = await _load_user_map()
        employee = user_map.get(str(leave.get("user_id")))
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        await _assert_leave_scope(current_user, employee, allow_self=False)
        if leave.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending leave requests can be approved")
        if payload.approvedBy != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Approver must match the signed-in user")

        approver = await SupabaseHelper.get_public_user_by_firebase_uid(current_user.get("uid"))
        if not approver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        update_response = supabase.table("leaves").update({
            "status": "approved",
            "approved_by": approver["id"],
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "rejection_reason": None,
        }).eq("id", leave_id).eq("status", "pending").execute()

        if not update_response.data:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This leave request was already reviewed")

        log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"),
                        module="leave_request", action="leave_approved", description=f"{current_user.get('name')} approved {employee.get('name')}'s leave request.",
                        result="success", target_type="leave", target_id=leave_id,
                        metadata={"employee_uid": employee.get("uid"), "start_date": leave.get("start_date"), "end_date": leave.get("end_date")})

        return {"message": "Leave request approved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error approving leave: {str(e)}")


@router.post("/{leave_id}/reject", status_code=status.HTTP_200_OK)
async def reject_leave(
    leave_id: str,
    payload: RejectRequest = Body(...),
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        response = supabase.table("leaves").select("*").eq("id", leave_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        leave = response.data[0]
        user_map = await _load_user_map()
        employee = user_map.get(str(leave.get("user_id")))
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        await _assert_leave_scope(current_user, employee, allow_self=False)
        if leave.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending leave requests can be rejected")
        if payload.rejectedBy != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rejecter must match the signed-in user")
        rejection_reason = payload.rejectionReason.strip()
        if not rejection_reason:
            raise HTTPException(status_code=422, detail="A rejection reason is required")

        rejecter = await SupabaseHelper.get_public_user_by_firebase_uid(current_user.get("uid"))
        if not rejecter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rejecter not found")

        update_response = supabase.table("leaves").update({
            "status": "rejected",
            "approved_by": rejecter["id"],
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "rejection_reason": rejection_reason,
        }).eq("id", leave_id).eq("status", "pending").execute()

        if not update_response.data:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This leave request was already reviewed")

        log_audit_event(actor_id=current_user.get("uid"), actor_name=current_user.get("name"), actor_email=current_user.get("email"),
                        module="leave_request", action="leave_rejected", description=f"{current_user.get('name')} rejected {employee.get('name')}'s leave request.",
                        result="success", target_type="leave", target_id=leave_id,
                        metadata={"employee_uid": employee.get("uid"), "start_date": leave.get("start_date"), "end_date": leave.get("end_date"), "reason": rejection_reason})

        return {"message": "Leave request rejected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error rejecting leave: {str(e)}")
