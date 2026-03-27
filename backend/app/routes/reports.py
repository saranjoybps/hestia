from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from app.dependencies import db, get_current_user, require_role
from datetime import datetime
from typing import Optional, Dict
import csv
import io
from collections import defaultdict
from datetime import timedelta, date

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/attendance")
async def get_attendance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """Get attendance report by department"""
    try:
        # Query attendance records
        query = db.collection('attendance')\
            .where('date', '>=', startDate)\
            .where('date', '<=', endDate)
        
        docs = query.stream()
        
        # Aggregate by department
        dept_stats = defaultdict(lambda: {
            'totalEmployees': set(),
            'presentCount': 0,
            'absentCount': 0,
            'leaveCount': 0,
            'halfDayCount': 0,
            'totalHours': 0,
            'recordCount': 0,
        })
        
        for doc in docs:
            data = doc.to_dict()
            user_id = data.get('user_id')
            
            # Get user's department
            user_doc = db.collection('users').document(user_id).get()
            if not user_doc.exists:
                continue
                
            user_data = user_doc.to_dict()
            dept = user_data.get('department', 'Unknown')
            
            # Filter by department if specified
            if department and department != dept:
                continue
            
            dept_stats[dept]['totalEmployees'].add(user_id)
            
            status = data.get('status', 'absent')
            if status == 'present':
                dept_stats[dept]['presentCount'] += 1
            elif status == 'absent':
                dept_stats[dept]['absentCount'] += 1
            elif status == 'leave':
                dept_stats[dept]['leaveCount'] += 1
            elif status == 'half_day':
                dept_stats[dept]['halfDayCount'] += 1
            
            dept_stats[dept]['totalHours'] += data.get('total_hours', 0)
            dept_stats[dept]['recordCount'] += 1
        
        # Calculate metrics
        by_department = []
        total_employees = 0
        total_attendance_rate = 0
        
        for dept, stats in dept_stats.items():
            employee_count = len(stats['totalEmployees'])
            total_employees += employee_count
            
            total_records = stats['recordCount']
            attendance_rate = (stats['presentCount'] / total_records * 100) if total_records > 0 else 0
            avg_hours = (stats['totalHours'] / stats['presentCount']) if stats['presentCount'] > 0 else 0
            
            total_attendance_rate += attendance_rate
            
            by_department.append({
                'department': dept,
                'totalEmployees': employee_count,
                'presentCount': stats['presentCount'],
                'absentCount': stats['absentCount'],
                'leaveCount': stats['leaveCount'],
                'halfDayCount': stats['halfDayCount'],
                'attendanceRate': round(attendance_rate, 2),
                'avgWorkingHours': round(avg_hours, 2),
            })
        
        avg_attendance_rate = (total_attendance_rate / len(dept_stats)) if dept_stats else 0
        
        return {
            'summary': {
                'totalEmployees': total_employees,
                'avgAttendanceRate': round(avg_attendance_rate, 2),
            },
            'byDepartment': sorted(by_department, key=lambda x: x['department']),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating attendance report: {str(e)}"
        )


@router.get("/leaves")
async def get_leave_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """Get leave report by department"""
    try:
        # Query leave requests
        query = db.collection('leave_requests')\
            .where('startDate', '>=', startDate)\
            .where('startDate', '<=', endDate)
        
        docs = query.stream()
        
        # Aggregate by department
        dept_stats = defaultdict(lambda: {
            'totalLeaves': 0,
            'approvedLeaves': 0,
            'pendingLeaves': 0,
            'rejectedLeaves': 0,
            'casualLeaves': 0,
            'sickLeaves': 0,
            'earnedLeaves': 0,
            'totalDuration': 0,
        })
        
        total_leaves = 0
        
        for doc in docs:
            data = doc.to_dict()
            user_id = data.get('userId')
            
            # Get user's department
            user_doc = db.collection('users').document(user_id).get()
            if not user_doc.exists:
                continue
                
            user_data = user_doc.to_dict()
            dept = user_data.get('department', 'Unknown')
            
            # Filter by department if specified
            if department and department != dept:
                continue
            
            dept_stats[dept]['totalLeaves'] += 1
            total_leaves += 1
            
            status = data.get('status', 'pending')
            if status == 'approved':
                dept_stats[dept]['approvedLeaves'] += 1
            elif status == 'pending':
                dept_stats[dept]['pendingLeaves'] += 1
            elif status == 'rejected':
                dept_stats[dept]['rejectedLeaves'] += 1
            
            leave_type = data.get('leaveType', 'casual')
            if leave_type == 'casual':
                dept_stats[dept]['casualLeaves'] += 1
            elif leave_type == 'sick':
                dept_stats[dept]['sickLeaves'] += 1
            elif leave_type == 'earned':
                dept_stats[dept]['earnedLeaves'] += 1
            
            dept_stats[dept]['totalDuration'] += data.get('duration', 0)
        
        # Calculate metrics
        by_department = []
        
        for dept, stats in dept_stats.items():
            avg_duration = (stats['totalDuration'] / stats['totalLeaves']) if stats['totalLeaves'] > 0 else 0
            
            by_department.append({
                'department': dept,
                'totalLeaves': stats['totalLeaves'],
                'approvedLeaves': stats['approvedLeaves'],
                'pendingLeaves': stats['pendingLeaves'],
                'rejectedLeaves': stats['rejectedLeaves'],
                'casualLeaves': stats['casualLeaves'],
                'sickLeaves': stats['sickLeaves'],
                'earnedLeaves': stats['earnedLeaves'],
                'avgLeaveDuration': round(avg_duration, 2),
            })
        
        return {
            'summary': {
                'totalLeaves': total_leaves,
            },
            'byDepartment': sorted(by_department, key=lambda x: x['department']),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating leave report: {str(e)}"
        )


@router.get("/performance")
async def get_performance_report(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """Get performance report by department"""
    try:
        # Query performance reviews
        query = db.collection('performance_reviews')\
            .where('reviewDate', '>=', startDate)\
            .where('reviewDate', '<=', endDate)
        
        docs = query.stream()
        
        # Aggregate by department
        dept_stats = defaultdict(lambda: {
            'employees': set(),
            'totalRating': 0,
            'reviewCount': 0,
            'positiveReviews': 0,
            'negativeReviews': 0,
            'pendingReviews': 0,
            'topPerformers': defaultdict(lambda: {'name': '', 'ratings': []}),
        })
        
        total_rating = 0
        total_reviews = 0
        
        for doc in docs:
            data = doc.to_dict()
            dept = data.get('department', 'Unknown')
            
            # Filter by department if specified
            if department and department != dept:
                continue
            
            user_id = data.get('userId')
            user_name = data.get('userName', 'Unknown')
            
            dept_stats[dept]['employees'].add(user_id)
            dept_stats[dept]['reviewCount'] += 1
            total_reviews += 1
            
            status = data.get('status', 'pending')
            if status == 'approved':
                rating = data.get('rating', 0)
                dept_stats[dept]['totalRating'] += rating
                total_rating += rating
                
                # Track top performers
                dept_stats[dept]['topPerformers'][user_id]['name'] = user_name
                dept_stats[dept]['topPerformers'][user_id]['ratings'].append(rating)
            elif status == 'pending':
                dept_stats[dept]['pendingReviews'] += 1
            
            review_type = data.get('reviewType', 'positive')
            if review_type == 'positive':
                dept_stats[dept]['positiveReviews'] += 1
            else:
                dept_stats[dept]['negativeReviews'] += 1
        
        # Calculate metrics
        by_department = []
        
        for dept, stats in dept_stats.items():
            approved_reviews = stats['reviewCount'] - stats['pendingReviews']
            avg_rating = (stats['totalRating'] / approved_reviews) if approved_reviews > 0 else 0
            
            # Find top performer in department
            top_performer = 'N/A'
            if stats['topPerformers']:
                top_perf_data = max(
                    stats['topPerformers'].values(),
                    key=lambda x: sum(x['ratings']) / len(x['ratings']) if x['ratings'] else 0
                )
                top_performer = top_perf_data['name']
            
            by_department.append({
                'department': dept,
                'employeeCount': len(stats['employees']),
                'avgRating': round(avg_rating, 2),
                'positiveReviews': stats['positiveReviews'],
                'negativeReviews': stats['negativeReviews'],
                'pendingReviews': stats['pendingReviews'],
                'topPerformer': top_performer,
            })
        
        avg_rating = (total_rating / total_reviews) if total_reviews > 0 else 0
        
        return {
            'summary': {
                'avgRating': round(avg_rating, 2),
            },
            'byDepartment': sorted(by_department, key=lambda x: x['department']),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating performance report: {str(e)}"
        )


@router.get("/employees")
async def get_employee_metrics(
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """Get individual employee metrics"""
    try:
        # Get all users
        users_query = db.collection('users')
        if department:
            users_query = users_query.where('department', '==', department)
        
        users = []
        for doc in users_query.stream():
            user_data = doc.to_dict()
            user_data['uid'] = doc.id
            users.append(user_data)
        
        employee_metrics = []
        
        for user in users:
            user_id = user['uid']
            
            # Get attendance rate
            attendance_docs = db.collection('attendance')\
                .where('user_id', '==', user_id)\
                .where('date', '>=', startDate)\
                .where('date', '<=', endDate)\
                .stream()
            
            total_days = 0
            present_days = 0
            for att_doc in attendance_docs:
                att_data = att_doc.to_dict()
                total_days += 1
                if att_data.get('status') == 'present':
                    present_days += 1
            
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
            
            # Get leaves used
            leaves_docs = db.collection('leave_requests')\
                .where('userId', '==', user_id)\
                .where('startDate', '>=', startDate)\
                .where('startDate', '<=', endDate)\
                .where('status', '==', 'approved')\
                .stream()
            
            leaves_used = len([doc for doc in leaves_docs])
            
            # Get average rating
            reviews_docs = db.collection('performance_reviews')\
                .where('userId', '==', user_id)\
                .where('status', '==', 'approved')\
                .stream()
            
            ratings = [doc.to_dict().get('rating', 0) for doc in reviews_docs]
            avg_rating = (sum(ratings) / len(ratings)) if ratings else 0
            
            # Get tasks completed
            tasks_docs = db.collection('tasks')\
                .where('assigneeId', '==', user_id)\
                .where('status', '==', 'completed')\
                .stream()
            
            tasks_completed = len([doc for doc in tasks_docs])
            
            employee_metrics.append({
                'name': user.get('name', 'Unknown'),
                'department': user.get('department', 'Unknown'),
                'designation': user.get('designation', 'Unknown'),
                'attendanceRate': round(attendance_rate, 2),
                'leavesUsed': leaves_used,
                'avgRating': round(avg_rating, 2),
                'tasksCompleted': tasks_completed,
            })
        
        return {
            'employees': sorted(employee_metrics, key=lambda x: x['name']),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating employee metrics: {str(e)}"
        )


@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    startDate: str = Query(...),
    endDate: str = Query(...),
    department: Optional[str] = None,
    format: str = Query("csv"),
    current_user: dict = Depends(require_role("manager", "director", "hr"))
):
    """Export report to CSV or PDF"""
    try:
        # Get report data based on type
        if report_type == "attendance":
            params = {'startDate': startDate, 'endDate': endDate, 'department': department}
            data_response = await get_attendance_report(**params, current_user=current_user)
            data = data_response['byDepartment']
            headers = ['Department', 'Total Employees', 'Present', 'Absent', 'On Leave', 'Half Day', 'Attendance Rate', 'Avg Hours']
            rows = [[
                d['department'],
                d['totalEmployees'],
                d['presentCount'],
                d['absentCount'],
                d['leaveCount'],
                d['halfDayCount'],
                f"{d['attendanceRate']}%",
                f"{d['avgWorkingHours']}h"
            ] for d in data]
            
        elif report_type == "leave":
            params = {'startDate': startDate, 'endDate': endDate, 'department': department}
            data_response = await get_leave_report(**params, current_user=current_user)
            data = data_response['byDepartment']
            headers = ['Department', 'Total', 'Approved', 'Pending', 'Rejected', 'Casual', 'Sick', 'Earned', 'Avg Duration']
            rows = [[
                d['department'],
                d['totalLeaves'],
                d['approvedLeaves'],
                d['pendingLeaves'],
                d['rejectedLeaves'],
                d['casualLeaves'],
                d['sickLeaves'],
                d['earnedLeaves'],
                f"{d['avgLeaveDuration']} days"
            ] for d in data]
            
        elif report_type == "performance":
            params = {'startDate': startDate, 'endDate': endDate, 'department': department}
            data_response = await get_performance_report(**params, current_user=current_user)
            data = data_response['byDepartment']
            headers = ['Department', 'Employees', 'Avg Rating', 'Positive', 'Negative', 'Pending', 'Top Performer']
            rows = [[
                d['department'],
                d['employeeCount'],
                d['avgRating'],
                d['positiveReviews'],
                d['negativeReviews'],
                d['pendingReviews'],
                d['topPerformer']
            ] for d in data]
            
        elif report_type == "employee":
            params = {'startDate': startDate, 'endDate': endDate, 'department': department}
            data_response = await get_employee_metrics(**params, current_user=current_user)
            data = data_response['employees']
            headers = ['Name', 'Department', 'Designation', 'Attendance Rate', 'Leaves Used', 'Avg Rating', 'Tasks Completed']
            rows = [[
                d['name'],
                d['department'],
                d['designation'],
                f"{d['attendanceRate']}%",
                d['leavesUsed'],
                d['avgRating'],
                d['tasksCompleted']
            ] for d in data]
        else:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        if format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(rows)
            
            response = StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv"
            )
            response.headers["Content-Disposition"] = f"attachment; filename={report_type}_report.csv"
            return response
            
        elif format == "pdf":
            # For PDF, we'll return a simple text format (in production, use reportlab or similar)
            # This is a placeholder - you'd want to use a proper PDF library
            content = f"{report_type.upper()} REPORT\n"
            content += f"Period: {startDate} to {endDate}\n\n"
            content += " | ".join(headers) + "\n"
            content += "-" * 80 + "\n"
            for row in rows:
                content += " | ".join(str(cell) for cell in row) + "\n"
            
            response = Response(content=content.encode(), media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename={report_type}_report.pdf"
            return response
        
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'pdf'")
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting report: {str(e)}"
        )


@router.get("/attendance/team-export")
async def export_team_attendance_excel(
    startDate: str = Query(..., description="Start date YYYY-MM-DD"),
    endDate: str = Query(..., description="End date YYYY-MM-DD"),
    current_user: dict = Depends(require_role("super_admin", "director", "manager", "hr"))
):
    """
    Export attendance summary per team member to Excel (.xlsx).
    Roles: super_admin, director, manager.
    Columns: Employee Name, From Date, To Date, Total Days, Present Days, Absent Days, Half Days, Attendance %.
    """
    try:
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl is required for Excel export")

        try:
            start_dt = date.fromisoformat(startDate)
            end_dt = date.fromisoformat(endDate)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail="endDate must be on/after startDate")

        total_days = (end_dt - start_dt).days + 1

        # Fetch users
        users = []
        users_iter = db.collection("users").stream()
        for u_doc in users_iter:
            data = u_doc.to_dict()
            data["uid"] = u_doc.id
            users.append(data)

        role = current_user.get("role")
        manager_id = current_user.get("uid")

        def in_scope(user_data: Dict) -> bool:
            if role in ["super_admin", "director", "hr"]:
                return True
            if role == "manager":
                user_manager_id = user_data.get("manager_id") or user_data.get("managerId")
                legacy_lead_id = user_data.get("lead_id") or user_data.get("leadId")
                return user_manager_id == manager_id or legacy_lead_id == manager_id
            return False

        scoped_users = [u for u in users if in_scope(u)]
        if not scoped_users:
            raise HTTPException(status_code=404, detail="No team members found for selected range")

        # Preload attendance in date range
        att_query = db.collection("attendance")\
            .where("date", ">=", startDate)\
            .where("date", "<=", endDate)
        attendance_docs = att_query.stream()

        stats: Dict[str, Dict[str, float]] = {
            u["uid"]: {
                "name": u.get("name", "Unknown"),
                "present": 0,
                "half_day": 0,
                "leave": 0,
            } for u in scoped_users
        }

        for doc in attendance_docs:
            data = doc.to_dict()
            uid = data.get("user_id")
            if uid not in stats:
                continue
            status = data.get("status", "absent")
            if status == "present":
                stats[uid]["present"] += 1
            elif status in ["half_day", "half-day"]:
                stats[uid]["half_day"] += 1
            elif status == "leave":
                stats[uid]["leave"] += 1
            else:
                # treat explicit absent as no present increment
                pass

        # Build workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance"
        headers = [
            "Employee Name", "From Date", "To Date",
            "Total Days", "Present Days", "Absent Days",
            "Half Days", "Attendance %"
        ]
        ws.append(headers)

        for uid, s in sorted(stats.items(), key=lambda x: x[1]["name"]):
            present = s["present"]
            half_day = s["half_day"]
            leave = s["leave"]
            absent = max(total_days - present - half_day - leave, 0)
            attendance_pct = ((present + 0.5 * half_day) / total_days * 100) if total_days > 0 else 0

            ws.append([
                s["name"],
                startDate,
                endDate,
                total_days,
                present,
                absent,
                half_day,
                round(attendance_pct, 2),
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response.headers["Content-Disposition"] = f"attachment; filename=attendance_report_{startDate}_to_{endDate}.xlsx"
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting attendance: {str(e)}"
        )
