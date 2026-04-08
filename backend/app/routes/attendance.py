from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.dependencies import db, get_current_user, require_role
from app.models import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.services.audit_log import log_audit_event
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance(
    attendance_data: AttendanceCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create attendance record
    Leads can mark attendance for reportees
    Managers/Directors can mark for anyone
    """
    try:
        user_role = current_user.get("role")

        # Fetch employee document once — reused for permission check and audit log
        employee_doc = db.collection("users").document(attendance_data.user_id).get()
        employee_name = employee_doc.to_dict().get("name") if employee_doc.exists else attendance_data.user_id

        # Check permissions
        if user_role == "lead":
            # Single reporting flow: manager_id is source of truth.
            # Keep legacy lead fields as read fallback for older records.
            if not employee_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only mark attendance for your reportees"
                )
            reportee = employee_doc.to_dict()
            manager_id = reportee.get("manager_id") or reportee.get("managerId")
            legacy_lead_id = reportee.get("lead_id") or reportee.get("leadId")
            if manager_id != current_user.get("uid") and legacy_lead_id != current_user.get("uid"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only mark attendance for your reportees"
                )
        elif user_role not in ["manager", "director", "hr"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        # Prepare attendance document
        attendance_doc = attendance_data.model_dump()
        attendance_doc["created_at"] = datetime.utcnow()
        attendance_doc["updated_at"] = None
        attendance_doc["corrected_by"] = None
        
        # Save to Firestore
        doc_ref = db.collection("attendance").add(attendance_doc)
        
        attendance_doc["id"] = doc_ref[1].id

        # Audit log
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="attendance",
            action="attendance_marked",
            description=(
                f"{current_user.get('name', 'Someone')} marked attendance for {employee_name} "
                f"on {attendance_data.date} as {attendance_data.status}."
            ),
            result="success",
            target_type="attendance",
            target_id=attendance_doc["id"],
            metadata={
                "user_id": attendance_data.user_id,
                "user_name": employee_name,
                "date": attendance_data.date,
                "status": attendance_data.status,
                "check_in": attendance_data.check_in,
                "check_out": attendance_data.check_out
            }
        )

        return AttendanceResponse(**attendance_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating attendance: {str(e)}"
        )


@router.get("/", response_model=list[AttendanceResponse])
async def get_attendance(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    attendance_status: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    try:
        query = db.collection("attendance")

        if user_id:
            query = query.where("user_id", "==", user_id)

        if attendance_status:
            query = query.where("status", "==", attendance_status)

        query = query.limit(1000)

        attendance_list = []
        for doc in query.stream():
            attendance_data = doc.to_dict()
            attendance_data["id"] = doc.id

            if start_date and attendance_data.get("date", "") < start_date:
                continue
            if end_date and attendance_data.get("date", "") > end_date:
                continue

            attendance_list.append(AttendanceResponse(**attendance_data))

        return attendance_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching attendance: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=list[AttendanceResponse])
async def get_user_attendance(
    user_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Get attendance records for a specific user
    """
    try:
        query = db.collection("attendance").where("user_id", "==", user_id)
        
        # Apply date filters
        if start_date:
            query = query.where("date", ">=", start_date)
        if end_date:
            query = query.where("date", "<=", end_date)
        
        query = query.order_by("date", direction="DESCENDING")
        
        attendance_list = []
        for doc in query.stream():
            attendance_data = doc.to_dict()
            attendance_data["id"] = doc.id
            attendance_list.append(AttendanceResponse(**attendance_data))
        
        return attendance_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching attendance: {str(e)}"
        )


@router.get("/monthly/{user_id}/{year}/{month}")
async def get_monthly_attendance(
    user_id: str,
    year: int,
    month: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get monthly attendance summary for calendar view
    """
    try:
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        query = db.collection("attendance")\
            .where("user_id", "==", user_id)\
            .where("date", ">=", start_date)\
            .where("date", "<", end_date)
        
        attendance_dict = {}
        stats = {
            "present": 0,
            "absent": 0,
            "half_day": 0,
            "leave": 0,
            "holiday": 0,
            "total_hours": 0.0
        }
        
        for doc in query.stream():
            data = doc.to_dict()
            attendance_dict[data["date"]] = {
                "id": doc.id,
                "status": data["status"],
                "check_in": data.get("check_in"),
                "check_out": data.get("check_out"),
                "total_hours": data.get("total_hours", 0.0),
                "notes": data.get("notes")
            }
            
            # Update stats
            stats[data["status"]] += 1
            stats["total_hours"] += data.get("total_hours", 0.0)
        
        return {
            "year": year,
            "month": month,
            "attendance": attendance_dict,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching monthly attendance: {str(e)}"
        )


@router.put("/{attendance_id}", response_model=AttendanceResponse)
async def update_attendance(
    attendance_id: str,
    attendance_update: AttendanceUpdate,
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """
    Update/correct attendance record
    Manager/Director only
    """
    try:
        attendance_ref = db.collection("attendance").document(attendance_id)
        attendance_doc = attendance_ref.get()
        
        if not attendance_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found"
            )
        
        # Prepare update data
        update_data = attendance_update.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        update_data["corrected_by"] = current_user.get("uid")
        
        # Update Firestore
        attendance_ref.update(update_data)
        
        # Get updated record
        updated_doc = attendance_ref.get()
        attendance_data = updated_doc.to_dict()
        attendance_data["id"] = attendance_id

        # Fetch employee details for clearer audit logs
        employee_ref = db.collection("users").document(attendance_data.get("user_id"))
        employee_doc = employee_ref.get()
        employee_name = employee_doc.to_dict().get("name") if employee_doc.exists else attendance_data.get("user_id")

        # Audit log
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="attendance",
            action="attendance_updated",
            description=(
                f"{current_user.get('name', 'Someone')} updated attendance for {employee_name} "
                f"on {attendance_data.get('date')}."
            ),
            result="success",
            target_type="attendance",
            target_id=attendance_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "user_id": attendance_data.get("user_id"),
                "user_name": employee_name,
                "status": attendance_data.get("status"),
                "check_in": attendance_data.get("check_in"),
                "check_out": attendance_data.get("check_out")
            }
        )

        return AttendanceResponse(**attendance_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating attendance: {str(e)}"
        )


@router.get("/reports/summary")
async def get_attendance_summary(
    department: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """
    Get attendance summary report
    Manager/Director/HR only
    """
    try:
        # Get all users (filtered by department if specified)
        users_query = db.collection("users").where("status", "==", "active")
        if department:
            users_query = users_query.where("department", "==", department)
        
        summary = []
        
        for user_doc in users_query.stream():
            user_data = user_doc.to_dict()
            user_id = user_doc.id
            
            # Get attendance for user
            att_query = db.collection("attendance").where("user_id", "==", user_id)
            if start_date:
                att_query = att_query.where("date", ">=", start_date)
            if end_date:
                att_query = att_query.where("date", "<=", end_date)
            
            stats = {
                "present": 0,
                "absent": 0,
                "half_day": 0,
                "leave": 0,
                "total_hours": 0.0
            }
            
            for att_doc in att_query.stream():
                att_data = att_doc.to_dict()
                stats[att_data["status"]] += 1
                stats["total_hours"] += att_data.get("total_hours", 0.0)
            
            total_days = sum([stats["present"], stats["absent"], stats["half_day"], stats["leave"]])
            attendance_percentage = (stats["present"] + stats["half_day"] * 0.5) / total_days * 100 if total_days > 0 else 0
            
            summary.append({
                "user_id": user_id,
                "name": user_data.get("name"),
                "department": user_data.get("department"),
                "stats": stats,
                "attendance_percentage": round(attendance_percentage, 2)
            })
        
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating attendance summary: {str(e)}"
        )
