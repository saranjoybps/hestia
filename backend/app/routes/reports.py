from collections import defaultdict
from datetime import date, timedelta
import csv
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.dependencies import require_role, supabase
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/reports", tags=["Reports"])


async def _all_users() -> Dict[str, Dict[str, Any]]:
    rows = await SupabaseHelper.get_all_user_rows()
    return {str(row["id"]): row for row in rows if row.get("id")}


async def _public_users_by_internal_id() -> Dict[str, Dict[str, Any]]:
    rows = await SupabaseHelper.get_all_user_rows()
    mapped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        public = SupabaseHelper._public_user(row)
        if public and row.get("id"):
            mapped[str(row["id"])] = public
    return mapped


@router.get("/attendance")
async def get_attendance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        attendance_resp = supabase.table("attendance").select("*").gte("date", startDate).lte("date", endDate).execute()
        docs = attendance_resp.data or []
        all_users = await _all_users()

        dept_stats = defaultdict(lambda: {
            "totalEmployees": set(),
            "presentCount": 0,
            "absentCount": 0,
            "leaveCount": 0,
            "halfDayCount": 0,
            "totalHours": 0,
            "recordCount": 0,
        })

        for data in docs:
            user_id = str(data.get("user_id")) if data.get("user_id") else None
            user_data = all_users.get(user_id)
            if not user_data:
                continue
            dept = user_data.get("department", "Unknown")
            if department and department != dept:
                continue

            dept_stats[dept]["totalEmployees"].add(user_id)
            status = data.get("status", "absent")
            if status == "present":
                dept_stats[dept]["presentCount"] += 1
            elif status == "absent":
                dept_stats[dept]["absentCount"] += 1
            elif status == "leave":
                dept_stats[dept]["leaveCount"] += 1
            elif status == "half_day":
                dept_stats[dept]["halfDayCount"] += 1
            dept_stats[dept]["totalHours"] += float(data.get("total_hours", 0) or 0)
            dept_stats[dept]["recordCount"] += 1

        by_department = []
        total_employees = 0
        total_attendance_rate = 0
        for dept, stats in dept_stats.items():
            employee_count = len(stats["totalEmployees"])
            total_employees += employee_count
            total_records = stats["recordCount"]
            attendance_rate = (stats["presentCount"] / total_records * 100) if total_records > 0 else 0
            avg_hours = (stats["totalHours"] / stats["presentCount"]) if stats["presentCount"] > 0 else 0
            total_attendance_rate += attendance_rate
            by_department.append({
                "department": dept,
                "totalEmployees": employee_count,
                "presentCount": stats["presentCount"],
                "absentCount": stats["absentCount"],
                "leaveCount": stats["leaveCount"],
                "halfDayCount": stats["halfDayCount"],
                "attendanceRate": round(attendance_rate, 2),
                "avgWorkingHours": round(avg_hours, 2),
            })

        avg_attendance_rate = (total_attendance_rate / len(dept_stats)) if dept_stats else 0
        return {
            "summary": {
                "totalEmployees": total_employees,
                "avgAttendanceRate": round(avg_attendance_rate, 2),
            },
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating attendance report: {str(e)}")


@router.get("/leaves")
async def get_leave_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        leave_resp = supabase.table("leaves").select("*").gte("start_date", startDate).lte("start_date", endDate).execute()
        docs = leave_resp.data or []
        all_users = await _all_users()

        dept_stats = defaultdict(lambda: {
            "totalLeaves": 0,
            "approvedLeaves": 0,
            "pendingLeaves": 0,
            "rejectedLeaves": 0,
            "casualLeaves": 0,
            "sickLeaves": 0,
            "earnedLeaves": 0,
            "totalDuration": 0,
        })

        total_leaves = 0
        for data in docs:
            user_id = str(data.get("user_id")) if data.get("user_id") else None
            user_data = all_users.get(user_id)
            if not user_data:
                continue
            dept = user_data.get("department", "Unknown")
            if department and department != dept:
                continue

            dept_stats[dept]["totalLeaves"] += 1
            total_leaves += 1
            status = data.get("status", "pending")
            if status == "approved":
                dept_stats[dept]["approvedLeaves"] += 1
            elif status == "pending":
                dept_stats[dept]["pendingLeaves"] += 1
            elif status == "rejected":
                dept_stats[dept]["rejectedLeaves"] += 1

            leave_type = data.get("leave_type", "casual")
            if leave_type == "casual":
                dept_stats[dept]["casualLeaves"] += 1
            elif leave_type == "sick":
                dept_stats[dept]["sickLeaves"] += 1
            elif leave_type == "earned":
                dept_stats[dept]["earnedLeaves"] += 1
            dept_stats[dept]["totalDuration"] += float(data.get("number_of_days", 0) or 0)

        by_department = []
        for dept, stats in dept_stats.items():
            avg_duration = (stats["totalDuration"] / stats["totalLeaves"]) if stats["totalLeaves"] > 0 else 0
            by_department.append({
                "department": dept,
                "totalLeaves": stats["totalLeaves"],
                "approvedLeaves": stats["approvedLeaves"],
                "pendingLeaves": stats["pendingLeaves"],
                "rejectedLeaves": stats["rejectedLeaves"],
                "casualLeaves": stats["casualLeaves"],
                "sickLeaves": stats["sickLeaves"],
                "earnedLeaves": stats["earnedLeaves"],
                "avgLeaveDuration": round(avg_duration, 2),
            })

        return {
            "summary": {"totalLeaves": total_leaves},
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating leave report: {str(e)}")


@router.get("/performance")
async def get_performance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        perf_resp = supabase.table("performance_reviews").select("*").gte("review_date", startDate).lte("review_date", endDate).execute()
        docs = perf_resp.data or []

        dept_stats = defaultdict(lambda: {
            "employees": set(),
            "totalRating": 0,
            "reviewCount": 0,
            "positiveReviews": 0,
            "negativeReviews": 0,
            "pendingReviews": 0,
            "topPerformers": defaultdict(lambda: {"name": "", "ratings": []}),
        })

        total_rating = 0
        total_reviews = 0
        for data in docs:
            dept = data.get("department", "Unknown")
            if department and department != dept:
                continue

            user_id = data.get("user_id")
            user_name = data.get("user_name", "Unknown")
            dept_stats[dept]["employees"].add(user_id)
            dept_stats[dept]["reviewCount"] += 1
            total_reviews += 1

            status = data.get("status", "pending")
            if status == "approved":
                rating = float(data.get("rating", 0) or 0)
                dept_stats[dept]["totalRating"] += rating
                total_rating += rating
                dept_stats[dept]["topPerformers"][user_id]["name"] = user_name
                dept_stats[dept]["topPerformers"][user_id]["ratings"].append(rating)
            elif status == "pending":
                dept_stats[dept]["pendingReviews"] += 1

            if data.get("review_type", "positive") == "positive":
                dept_stats[dept]["positiveReviews"] += 1
            else:
                dept_stats[dept]["negativeReviews"] += 1

        by_department = []
        for dept, stats in dept_stats.items():
            approved_reviews = stats["reviewCount"] - stats["pendingReviews"]
            avg_rating = (stats["totalRating"] / approved_reviews) if approved_reviews > 0 else 0
            top_performer = "N/A"
            if stats["topPerformers"]:
                top_perf_data = max(
                    stats["topPerformers"].values(),
                    key=lambda x: sum(x["ratings"]) / len(x["ratings"]) if x["ratings"] else 0,
                )
                top_performer = top_perf_data["name"]

            by_department.append({
                "department": dept,
                "employeeCount": len(stats["employees"]),
                "avgRating": round(avg_rating, 2),
                "positiveReviews": stats["positiveReviews"],
                "negativeReviews": stats["negativeReviews"],
                "pendingReviews": stats["pendingReviews"],
                "topPerformer": top_performer,
            })

        avg_rating = (total_rating / total_reviews) if total_reviews > 0 else 0
        return {
            "summary": {"avgRating": round(avg_rating, 2)},
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating performance report: {str(e)}")


@router.get("/employees")
async def get_employee_metrics(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        # 1 query — all users, filtered by department if provided
        users_resp = supabase.table("users").select("*").execute()
        users = [
            row for row in (users_resp.data or [])
            if not department or row.get("department") == department
        ]

        if not users:
            return {"employees": []}

        user_ids = [str(u["id"]) for u in users]

        # 4 bulk queries — one per table across all users at once
        attendance_rows = (
            supabase.table("attendance")
            .select("user_id, status")
            .in_("user_id", user_ids)
            .gte("date", startDate)
            .lte("date", endDate)
            .execute().data or []
        )
        leaves_rows = (
            supabase.table("leaves")
            .select("user_id")
            .in_("user_id", user_ids)
            .gte("start_date", startDate)
            .lte("start_date", endDate)
            .eq("status", "approved")
            .execute().data or []
        )
        reviews_rows = (
            supabase.table("performance_reviews")
            .select("user_id, rating")
            .in_("user_id", user_ids)
            .eq("status", "approved")
            .execute().data or []
        )
        tasks_rows = (
            supabase.table("tasks")
            .select("assigned_to")
            .in_("assigned_to", user_ids)
            .eq("status", "completed")
            .execute().data or []
        )

        # Group results by user_id in Python — no extra DB round trips
        attendance_by_user: Dict[str, List[str]] = defaultdict(list)
        for row in attendance_rows:
            attendance_by_user[str(row["user_id"])].append(row["status"])

        leaves_by_user: Dict[str, int] = defaultdict(int)
        for row in leaves_rows:
            leaves_by_user[str(row["user_id"])] += 1

        ratings_by_user: Dict[str, List[float]] = defaultdict(list)
        for row in reviews_rows:
            ratings_by_user[str(row["user_id"])].append(float(row.get("rating") or 0))

        tasks_by_user: Dict[str, int] = defaultdict(int)
        for row in tasks_rows:
            tasks_by_user[str(row["assigned_to"])] += 1

        # Build metrics from in-memory dicts — O(users), zero DB calls
        employee_metrics = []
        for user in users:
            uid = str(user["id"])
            statuses = attendance_by_user[uid]
            total_days = len(statuses)
            present_days = statuses.count("present")
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0

            ratings = ratings_by_user[uid]
            avg_rating = (sum(ratings) / len(ratings)) if ratings else 0

            employee_metrics.append({
                "name": user.get("name", "Unknown"),
                "department": user.get("department", "Unknown"),
                "designation": user.get("designation", "Unknown"),
                "attendanceRate": round(attendance_rate, 2),
                "leavesUsed": leaves_by_user[uid],
                "avgRating": round(avg_rating, 2),
                "tasksCompleted": tasks_by_user[uid],
            })

        return {"employees": sorted(employee_metrics, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating employee metrics: {str(e)}")


def _csv_response(filename: str, rows: List[Dict[str, Any]]) -> StreamingResponse:
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("")
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    format: str = Query("csv"),
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV export is supported")

    if report_type == "attendance":
        report = await get_attendance_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type == "leaves":
        report = await get_leave_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type == "performance":
        report = await get_performance_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type == "employees":
        report = await get_employee_metrics(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("employees", [])
    else:
        raise HTTPException(status_code=404, detail="Unknown report type")

    return _csv_response(f"{report_type}_report.csv", rows)


@router.get("/attendance/team-export")
async def export_team_attendance(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr")),
):
    try:
        attendance_resp = supabase.table("attendance").select("*").gte("date", startDate).lte("date", endDate).execute()
        docs = attendance_resp.data or []
        users = await _public_users_by_internal_id()

        rows: List[Dict[str, Any]] = []
        for data in docs:
            user = users.get(str(data.get("user_id")))
            if not user:
                continue
            if department and user.get("department") != department:
                continue
            rows.append({
                "date": data.get("date"),
                "employee": user.get("name"),
                "department": user.get("department"),
                "status": data.get("status"),
                "check_in": data.get("check_in_time"),
                "check_out": data.get("check_out_time"),
                "notes": data.get("notes"),
            })

        return _csv_response("team_attendance.csv", rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting team attendance: {str(e)}")
