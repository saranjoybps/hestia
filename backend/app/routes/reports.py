from collections import defaultdict
from datetime import date, timedelta
import csv
import io
from typing import Any, Dict, List, Optional, Set

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


async def _approved_leave_attendance_rows(user_ids: set[str], start_date: str, end_date: str, existing_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not user_ids:
        return []
    overlaps = supabase.table("leaves").select("*").in_("user_id", list(user_ids)).eq("status", "approved").lte("start_date", end_date).gte("end_date", start_date).execute().data or []
    occupied = {(str(row.get("user_id")), str(row.get("date"))) for row in existing_rows}
    generated: List[Dict[str, Any]] = []
    for leave in overlaps:
        cursor = date.fromisoformat(max(start_date, str(leave["start_date"])))
        last = date.fromisoformat(min(end_date, str(leave["end_date"])))
        while cursor <= last:
            day = cursor.isoformat()
            key = (str(leave.get("user_id")), day)
            if key not in occupied:
                generated.append({"user_id": leave.get("user_id"), "date": day, "status": "leave", "approval_status": "approved",
                                  "total_hours": 0, "notes": leave.get("reason") or "Approved leave"})
            cursor += timedelta(days=1)
    return generated


async def _report_scope_ids(current_user: Dict[str, Any]) -> Set[str]:
    """Return the set of internal user ids that the current_user is allowed to see in reports."""
    role = current_user.get("role")
    users = await SupabaseHelper.get_all_user_rows()
    if role in {"hr", "director", "super_admin"}:
        return {str(row["id"]) for row in users if row.get("id")}
    if role in {"lead", "manager"}:
        uid = str(current_user.get("uid") or "")
        current_row = next((row for row in users if str(row.get("firebase_uid") or "") == uid), {})
        root_ids = {value for value in (uid, str(current_row.get("id") or current_user.get("id") or "")) if value}
        allowed_ids = {str(current_row["id"])} if current_row.get("id") else set()
        frontier = set(root_ids)
        visited = set(root_ids)
        changed = True
        while changed:
            changed = False
            for row in users:
                row_id = str(row.get("id") or "")
                if not row_id or row_id in allowed_ids:
                    continue
                parents = {str(row.get("manager_id") or ""), str(row.get("lead_id") or "")}
                if parents & frontier:
                    allowed_ids.add(row_id)
                    child_ids = {row_id, str(row.get("firebase_uid") or "")}
                    new_ids = child_ids - visited
                    if new_ids:
                        visited.update(new_ids)
                        frontier.update(new_ids)
                        changed = True
        return allowed_ids
    # employee (or any other role) sees only themselves
    if current_user.get("id"):
        return {str(current_user["id"])}
    return set()


def _validate_date_range(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD format") from exc
    if end < start:
        raise HTTPException(status_code=422, detail="End date must be on or after start date")


@router.get("/attendance")
async def get_attendance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        _validate_date_range(startDate, endDate)
        attendance_resp = supabase.table("attendance").select("*").gte("date", startDate).lte("date", endDate).execute()
        allowed_ids = await _report_scope_ids(current_user)
        docs = [row for row in (attendance_resp.data or []) if str(row.get("user_id")) in allowed_ids and (row.get("approval_status") or "approved") == "approved"]
        docs.extend(await _approved_leave_attendance_rows(allowed_ids, startDate, endDate, docs))
        all_users = await _all_users()

        scoped_users = {
            user_id: user for user_id, user in all_users.items()
            if user_id in allowed_ids and (not department or user.get("department") == department)
        }
        dept_stats = defaultdict(lambda: {
            "totalEmployees": set(),
            "presentCount": 0,
            "absentCount": 0,
            "leaveCount": 0,
            "halfDayCount": 0,
            "totalHours": 0,
            "workedRecordCount": 0,
        })

        for user_id, user in scoped_users.items():
            dept_stats[user.get("department") or "Unknown"]["totalEmployees"].add(user_id)

        for data in docs:
            if data.get("is_week_off"):
                continue
            user_id = str(data.get("user_id")) if data.get("user_id") else None
            user_data = all_users.get(user_id)
            if not user_data:
                continue
            dept = user_data.get("department") or "Unknown"
            if department and department != dept:
                continue

            dept_stats[dept]["totalEmployees"].add(user_id)
            status = data.get("status", "absent")
            if status == "present":
                dept_stats[dept]["presentCount"] += 1
                dept_stats[dept]["workedRecordCount"] += 1
            elif status == "absent":
                dept_stats[dept]["absentCount"] += 1
            elif status == "leave":
                dept_stats[dept]["leaveCount"] += 1
            elif status == "half_day":
                dept_stats[dept]["halfDayCount"] += 1
                dept_stats[dept]["workedRecordCount"] += 1
            dept_stats[dept]["totalHours"] += float(data.get("total_hours", 0) or 0)

        by_department = []
        attendance_numerator = 0.0
        attendance_denominator = 0
        for dept, stats in dept_stats.items():
            employee_count = len(stats["totalEmployees"])
            eligible_days = stats["presentCount"] + stats["absentCount"] + stats["halfDayCount"]
            attendance_rate = ((stats["presentCount"] + stats["halfDayCount"] * 0.5) / eligible_days * 100) if eligible_days > 0 else 0
            attendance_numerator += stats["presentCount"] + stats["halfDayCount"] * 0.5
            attendance_denominator += eligible_days
            avg_hours = (stats["totalHours"] / stats["workedRecordCount"]) if stats["workedRecordCount"] > 0 else 0
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

        avg_attendance_rate = attendance_numerator / attendance_denominator * 100 if attendance_denominator else 0
        return {
            "summary": {
                "totalEmployees": len(scoped_users),
                "avgAttendanceRate": round(avg_attendance_rate, 2),
            },
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating attendance report: {str(e)}")


@router.get("/leaves")
async def get_leave_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        _validate_date_range(startDate, endDate)
        allowed_ids = await _report_scope_ids(current_user)
        if not allowed_ids:
            return {"summary": {"totalLeaves": 0}, "byDepartment": []}
        leave_resp = supabase.table("leaves").select("*").lte("start_date", endDate).gte("end_date", startDate).in_("user_id", list(allowed_ids)).execute()
        docs = leave_resp.data or []
        all_users = await _all_users()

        dept_stats = defaultdict(lambda: {
            "totalLeaves": 0,
            "approvedLeaves": 0,
            "pendingLeaves": 0,
            "rejectedLeaves": 0,
            "leaveTypeCounts": defaultdict(int),
            "totalDuration": 0,
        })

        total_leaves = 0
        for data in docs:
            user_id = str(data.get("user_id")) if data.get("user_id") else None
            user_data = all_users.get(user_id)
            if not user_data:
                continue
            dept = user_data.get("department") or "Unknown"
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
            dept_stats[dept]["leaveTypeCounts"][str(leave_type)] += 1
            whole_start = date.fromisoformat(str(data["start_date"]))
            whole_end = date.fromisoformat(str(data["end_date"]))
            overlap_start = max(whole_start, date.fromisoformat(startDate))
            overlap_end = min(whole_end, date.fromisoformat(endDate))
            full_days = max((whole_end - whole_start).days + 1, 1)
            overlap_days = max((overlap_end - overlap_start).days + 1, 0)
            day_count = float(data.get("number_of_days") or full_days)
            dept_stats[dept]["totalDuration"] += day_count * overlap_days / full_days

        by_department = []
        for dept, stats in dept_stats.items():
            avg_duration = (stats["totalDuration"] / stats["totalLeaves"]) if stats["totalLeaves"] > 0 else 0
            by_department.append({
                "department": dept,
                "totalLeaves": stats["totalLeaves"],
                "approvedLeaves": stats["approvedLeaves"],
                "pendingLeaves": stats["pendingLeaves"],
                "rejectedLeaves": stats["rejectedLeaves"],
                "leaveTypeCounts": dict(stats["leaveTypeCounts"]),
                "avgLeaveDuration": round(avg_duration, 2),
            })

        return {
            "summary": {"totalLeaves": total_leaves},
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating leave report: {str(e)}")


@router.get("/performance")
async def get_performance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        _validate_date_range(startDate, endDate)
        allowed_ids = await _report_scope_ids(current_user)
        if not allowed_ids:
            return {"summary": {"avgRating": 0}, "byDepartment": []}
        perf_resp = supabase.table("performance_reviews").select("*").gte("review_date", startDate).lte("review_date", endDate).in_("employee_id", list(allowed_ids)).execute()
        docs = perf_resp.data or []
        all_users = await _all_users()

        dept_stats = defaultdict(lambda: {
            "employees": set(),
            "totalRating": 0,
            "positiveReviews": 0,
            "negativeReviews": 0,
            "pendingReviews": 0,
            "topPerformers": defaultdict(lambda: {"name": "", "ratings": []}),
        })

        total_rating = 0
        for data in docs:
            employee_id = str(data.get("employee_id") or "")
            employee = all_users.get(employee_id, {})
            dept = employee.get("department") or "Unknown"
            if department and department != dept:
                continue

            user_id = employee_id
            user_name = data.get("user_name", "Unknown")
            dept_stats[dept]["employees"].add(user_id)
            status = data.get("status", "draft")
            if status == "approved":
                rating = float(data.get("rating", 0) or 0)
                dept_stats[dept]["totalRating"] += rating
                total_rating += rating
                dept_stats[dept]["topPerformers"][user_id]["name"] = user_name
                dept_stats[dept]["topPerformers"][user_id]["ratings"].append(rating)
            elif status in {"pending", "draft"}:
                dept_stats[dept]["pendingReviews"] += 1

            if status == "approved" and data.get("review_type", "positive") == "positive":
                dept_stats[dept]["positiveReviews"] += 1
            elif status == "approved":
                dept_stats[dept]["negativeReviews"] += 1

        by_department = []
        for dept, stats in dept_stats.items():
            approved_reviews = sum(len(values["ratings"]) for values in stats["topPerformers"].values())
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

        approved_total = sum(sum(len(values["ratings"]) for values in stats["topPerformers"].values()) for stats in dept_stats.values())
        avg_rating = (total_rating / approved_total) if approved_total > 0 else 0
        return {
            "summary": {"avgRating": round(avg_rating, 2)},
            "byDepartment": sorted(by_department, key=lambda x: x["department"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating performance report: {str(e)}")


@router.get("/employees")
async def get_employee_metrics(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        _validate_date_range(startDate, endDate)
        allowed_ids = await _report_scope_ids(current_user)
        if not allowed_ids:
            return {"employees": []}
        # 1 query — all users, filtered by department if provided
        users_resp = supabase.table("users").select("*").in_("id", list(allowed_ids)).execute()
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
            .select("user_id, status, approval_status, is_week_off")
            .in_("user_id", user_ids)
            .gte("date", startDate)
            .lte("date", endDate)
            .execute().data or []
        )
        leaves_rows = (
            supabase.table("leaves")
            .select("user_id, start_date, end_date, number_of_days")
            .in_("user_id", user_ids)
            .lte("start_date", endDate)
            .gte("end_date", startDate)
            .eq("status", "approved")
            .execute().data or []
        )
        reviews_rows = (
            supabase.table("performance_reviews")
            .select("employee_id, rating")
            .in_("employee_id", user_ids)
            .gte("review_date", startDate)
            .lte("review_date", endDate)
            .eq("status", "approved")
            .execute().data or []
        )
        tasks_rows = (
            supabase.table("tasks")
            .select("assigned_to")
            .in_("assigned_to", user_ids)
            .eq("status", "completed")
            .gte("completed_at", f"{startDate}T00:00:00")
            .lte("completed_at", f"{endDate}T23:59:59.999999")
            .execute().data or []
        )

        # Group results by user_id in Python — no extra DB round trips
        attendance_by_user: Dict[str, List[str]] = defaultdict(list)
        for row in attendance_rows:
            if (row.get("is_week_off") or (row.get("approval_status") or "approved") != "approved"):
                continue
            attendance_by_user[str(row["user_id"])].append(row["status"])

        leaves_by_user: Dict[str, float] = defaultdict(float)
        for row in leaves_rows:
            whole_start = date.fromisoformat(str(row["start_date"]))
            whole_end = date.fromisoformat(str(row["end_date"]))
            overlap_start = max(whole_start, date.fromisoformat(startDate))
            overlap_end = min(whole_end, date.fromisoformat(endDate))
            full_days = max((whole_end - whole_start).days + 1, 1)
            overlap_days = max((overlap_end - overlap_start).days + 1, 0)
            days = float(row.get("number_of_days") or full_days)
            leaves_by_user[str(row["user_id"])] += days * overlap_days / full_days

        ratings_by_user: Dict[str, List[float]] = defaultdict(list)
        for row in reviews_rows:
            ratings_by_user[str(row["employee_id"])].append(float(row.get("rating") or 0))

        tasks_by_user: Dict[str, int] = defaultdict(int)
        for row in tasks_rows:
            tasks_by_user[str(row["assigned_to"])] += 1

        # Build metrics from in-memory dicts — O(users), zero DB calls
        employee_metrics = []
        for user in users:
            uid = str(user["id"])
            statuses = attendance_by_user[uid]
            eligible_days = statuses.count("present") + statuses.count("absent") + statuses.count("half_day")
            attendance_rate = ((statuses.count("present") + statuses.count("half_day") * 0.5) / eligible_days * 100) if eligible_days else 0

            ratings = ratings_by_user[uid]
            avg_rating = (sum(ratings) / len(ratings)) if ratings else 0

            employee_metrics.append({
                "name": user.get("name", "Unknown"),
                "department": user.get("department", "Unknown"),
                "designation": user.get("designation", "Unknown"),
                "attendanceRate": round(attendance_rate, 2),
                "leavesUsed": round(leaves_by_user[uid], 2),
                "avgRating": round(avg_rating, 2),
                "tasksCompleted": tasks_by_user[uid],
            })

        return {"employees": sorted(employee_metrics, key=lambda x: x["name"])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating employee metrics: {str(e)}")


@router.get("/departments")
async def get_departments(current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin"))):
    try:
        allowed_ids = await _report_scope_ids(current_user)
        if not allowed_ids:
            return {"departments": []}
        users_resp = supabase.table("users").select("id, department").in_("id", list(allowed_ids)).execute()
        depts = {row.get("department") for row in (users_resp.data or []) if row.get("department")}
        return {"departments": sorted(depts)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching departments: {str(e)}")


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
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV export is supported")

    if report_type == "attendance":
        report = await get_attendance_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type in {"leave", "leaves"}:
        report = await get_leave_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type == "performance":
        report = await get_performance_report(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("byDepartment", [])
    elif report_type in {"employee", "employees"}:
        report = await get_employee_metrics(startDate=startDate, endDate=endDate, department=department, current_user=current_user)
        rows = report.get("employees", [])
    else:
        raise HTTPException(status_code=404, detail="Unknown report type")

    canonical_type = {"leave": "leaves", "employee": "employees"}.get(report_type, report_type)
    return _csv_response(f"{canonical_type}_report.csv", rows)


@router.get("/attendance/team-export")
async def export_team_attendance(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr", "super_admin")),
):
    try:
        _validate_date_range(startDate, endDate)
        attendance_resp = supabase.table("attendance").select("*").gte("date", startDate).lte("date", endDate).execute()
        allowed_ids = await _report_scope_ids(current_user)
        docs = [row for row in (attendance_resp.data or []) if str(row.get("user_id")) in allowed_ids and (row.get("approval_status") or "approved") == "approved"]
        docs.extend(await _approved_leave_attendance_rows(allowed_ids, startDate, endDate, docs))
        users = await _public_users_by_internal_id()

        rows: List[Dict[str, Any]] = []
        for data in docs:
            user = users.get(str(data.get("user_id")))
            if not user or data.get("is_week_off"):
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting team attendance: {str(e)}")
