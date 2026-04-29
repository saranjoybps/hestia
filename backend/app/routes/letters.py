from datetime import datetime
from io import BytesIO
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.dependencies import get_current_user, require_role, supabase
from app.services.google_drive import drive_service
from app.supabase_helper import SupabaseHelper

router = APIRouter()


class LetterRequest(BaseModel):
    employeeId: str
    employeeName: str
    employeeEmail: str
    department: str
    designation: str
    letterType: str
    lastWorkingDay: str
    reasonForExit: Optional[str] = None
    additionalComments: Optional[str] = None
    requestedBy: str
    requestedByName: str
    joinDate: Optional[str] = None
    annualSalary: Optional[str] = None
    startDate: Optional[str] = None
    probationPeriod: Optional[str] = None
    noticePeriod: Optional[str] = None


class ApprovalRequest(BaseModel):
    approvedBy: str
    approverName: str


class RejectionRequest(BaseModel):
    rejectedBy: str
    rejectionReason: str


def calculate_employment_period(join_date_str: str, last_working_day_str: str) -> str:
    try:
        join_date = datetime.fromisoformat(join_date_str.replace("Z", "+00:00"))
        last_day = datetime.fromisoformat(last_working_day_str.replace("Z", "+00:00"))
        years = last_day.year - join_date.year
        months = last_day.month - join_date.month
        if months < 0:
            years -= 1
            months += 12
        if years > 0 and months > 0:
            return f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
        if years > 0:
            return f"{years} year{'s' if years > 1 else ''}"
        if months > 0:
            return f"{months} month{'s' if months > 1 else ''}"
        return "Less than a month"
    except Exception:
        return "Duration not calculated"


def number_to_words_indian(number: int) -> str:
    if number == 0:
        return "zero"
    if number < 0:
        return "minus " + number_to_words_indian(abs(number))

    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def two_digits(n: int) -> str:
        if n < 20:
            return ones[n]
        return tens[n // 10] + ("" if n % 10 == 0 else " " + ones[n % 10])

    parts = []
    crore = number // 10000000
    number %= 10000000
    if crore:
        parts.append(two_digits(crore) + " crore")
    lakh = number // 100000
    number %= 100000
    if lakh:
        parts.append(two_digits(lakh) + " lakh")
    thousand = number // 1000
    number %= 1000
    if thousand:
        parts.append(two_digits(thousand) + " thousand")
    hundred = number // 100
    number %= 100
    if hundred:
        parts.append(ones[hundred] + " hundred")
    if number:
        parts.append(two_digits(number))
    return " ".join(parts).strip()


def generate_letter_pdf(letter_data: dict, letter_type: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, alignment=TA_LEFT, textColor=colors.black)
    normal_style = ParagraphStyle("NormalCustom", parent=styles["Normal"], fontSize=10, leading=12, alignment=TA_LEFT)
    right_style = ParagraphStyle("RightCustom", parent=styles["Normal"], fontSize=10, leading=12, alignment=TA_RIGHT)

    current_date = datetime.now().strftime("%d/%m/%Y")
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "logo.png"))
    header_left = Paragraph("JOYRTS", title_style) if not os.path.exists(logo_path) else Paragraph("JOYRTS", title_style)
    header_right = Paragraph(f"admin@joyrts.com<br/>Date: {current_date}", right_style)
    header = Table([[header_left, header_right]], colWidths=[2.0 * inch, 4.2 * inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.15 * inch))

    approver = letter_data.get("approverName", "Director")
    if letter_type == "offer":
        story.append(Paragraph("OFFER OF EMPLOYMENT", title_style))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(f"Dear {letter_data['employeeName']},", normal_style))
        story.append(Paragraph(f"We are pleased to offer you the position of <b>{letter_data['designation']}</b>.", normal_style))
        if letter_data.get("startDate"):
            start_date = datetime.fromisoformat(letter_data["startDate"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
            story.append(Paragraph(f"Your employment will commence on {start_date}.", normal_style))
        if letter_data.get("annualSalary"):
            salary_raw = str(letter_data.get("annualSalary") or "")
            salary_digits = "".join(ch for ch in salary_raw if ch.isdigit())
            salary_value = int(salary_digits) if salary_digits else 0
            salary_words = number_to_words_indian(salary_value) if salary_value else salary_raw
            story.append(Paragraph(f"Annual compensation: INR {salary_raw} (Rupees {salary_words} only).", normal_style))
    else:
        title = "EXPERIENCE LETTER" if letter_type == "experience" else "EXIT LETTER"
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.15 * inch))
        if letter_type == "experience":
            story.append(Paragraph(f"This is to certify that {letter_data['employeeName']} was employed with us as {letter_data['designation']}.", normal_style))
            if letter_data.get("joinDate") and letter_data.get("lastWorkingDay"):
                period = calculate_employment_period(letter_data["joinDate"], letter_data["lastWorkingDay"])
                story.append(Paragraph(f"Employment period: {period}.", normal_style))
        else:
            story.append(Paragraph(f"This letter confirms the separation of {letter_data['employeeName']} from the organization.", normal_style))
            if letter_data.get("lastWorkingDay"):
                last_day = datetime.fromisoformat(letter_data["lastWorkingDay"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
                story.append(Paragraph(f"Last working day: {last_day}.", normal_style))
        if letter_data.get("reasonForExit"):
            story.append(Paragraph(f"Reason for exit: {letter_data['reasonForExit']}", normal_style))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Sincerely,", normal_style))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(f"<b>{approver}</b>", normal_style))
    story.append(Paragraph("Director", normal_style))
    story.append(Paragraph("Joyrts", normal_style))
    doc.build(story)
    buffer.seek(0)
    return buffer


async def _user_row(firebase_uid: str):
    return await SupabaseHelper.get_user_row_by_firebase_uid(firebase_uid)


async def _public_row(row: Dict[str, Any]) -> Dict[str, Any]:
    employee = await SupabaseHelper.get_public_user_by_id(row.get("employee_id")) if row.get("employee_id") else None
    requester = await SupabaseHelper.get_public_user_by_id(row.get("requested_by")) if row.get("requested_by") else None
    reviewer = await SupabaseHelper.get_public_user_by_id(row.get("reviewed_by")) if row.get("reviewed_by") else None
    approver = await SupabaseHelper.get_public_user_by_id(row.get("approved_by")) if row.get("approved_by") else None
    rejected_by = await SupabaseHelper.get_public_user_by_id(row.get("rejected_by")) if row.get("rejected_by") else None
    return {
        "id": str(row.get("id")),
        "employeeId": employee.get("uid") if employee else None,
        "employeeName": row.get("employee_name") or (employee.get("name") if employee else None),
        "employeeEmail": row.get("employee_email") or (employee.get("email") if employee else None),
        "department": row.get("department"),
        "designation": row.get("designation"),
        "letterType": row.get("letter_type"),
        "lastWorkingDay": row.get("last_working_day"),
        "reasonForExit": row.get("reason_for_exit"),
        "additionalComments": row.get("additional_comments"),
        "requestedBy": requester.get("uid") if requester else None,
        "requestedByName": row.get("requested_by_name") or (requester.get("name") if requester else None),
        "joinDate": row.get("join_date"),
        "annualSalary": row.get("annual_salary"),
        "startDate": row.get("start_date"),
        "probationPeriod": row.get("probation_period"),
        "noticePeriod": row.get("notice_period"),
        "status": row.get("status"),
        "approvedBy": approver.get("uid") if approver else None,
        "approverName": row.get("approver_name") or (approver.get("name") if approver else None),
        "approvedOn": row.get("approved_on"),
        "rejectedBy": rejected_by.get("uid") if rejected_by else None,
        "rejectionReason": row.get("rejection_reason"),
        "rejectedOn": row.get("rejected_on"),
        "requestedOn": row.get("requested_on"),
        "employmentPeriod": row.get("employment_period"),
        "referenceNumber": row.get("reference_number"),
        "pdfFiles": row.get("pdf_files") or [],
        "experience_letter_link": row.get("experience_letter_link"),
        "experience_file_id": row.get("experience_file_id"),
        "exit_letter_link": row.get("exit_letter_link"),
        "exit_file_id": row.get("exit_file_id"),
        "offer_letter_link": row.get("offer_letter_link"),
        "offer_file_id": row.get("offer_file_id"),
    }


async def _build_db_row(request: LetterRequest, current_user: dict, status_value: str) -> Dict[str, Any]:
    employee_row = await _user_row(request.employeeId)
    requester_row = await _user_row(current_user.get("uid"))
    if not employee_row or not requester_row:
        raise HTTPException(status_code=404, detail="Employee or requester not found")
    return {
        "employee_id": str(employee_row["id"]),
        "employee_name": request.employeeName,
        "employee_email": request.employeeEmail,
        "department": request.department,
        "designation": request.designation,
        "letter_type": request.letterType,
        "last_working_day": request.lastWorkingDay,
        "reason_for_exit": request.reasonForExit,
        "additional_comments": request.additionalComments,
        "requested_by": str(requester_row["id"]),
        "requested_by_name": current_user.get("name"),
        "join_date": request.joinDate,
        "annual_salary": request.annualSalary,
        "start_date": request.startDate,
        "probation_period": request.probationPeriod,
        "notice_period": request.noticePeriod,
        "status": status_value,
        "requested_on": datetime.utcnow().isoformat(),
        "employment_period": calculate_employment_period(request.joinDate, request.lastWorkingDay) if request.joinDate else None,
        "approved_by": None,
        "approver_name": None,
        "approved_on": None,
        "rejected_by": None,
        "rejection_reason": None,
        "rejected_on": None,
        "reference_number": None,
        "pdf_files": [],
        "experience_letter_link": None,
        "experience_file_id": None,
        "exit_letter_link": None,
        "exit_file_id": None,
        "reviewed_by": None,
        "reviewed_by_name": None,
        "reviewed_at": None,
    }


async def _generate_and_store_files(letter_row: Dict[str, Any], approver_name: str) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    updates: Dict[str, Any] = {}
    letter_row = dict(letter_row)
    letter_row["approverName"] = approver_name

    if letter_row["letterType"] in ["experience", "both"]:
        exp_buffer = generate_letter_pdf(letter_row, "experience")
        filename = f"experience_letter_{letter_row['employeeName'].replace(' ', '_')}.pdf"
        result = drive_service.upload_pdf(exp_buffer, filename)
        if result:
            files.append({"type": "experience", "filename": filename, "file_id": result["file_id"], "web_view_link": result["web_view_link"], "download_link": result.get("download_link")})
            updates["experience_letter_link"] = result["web_view_link"]
            updates["experience_file_id"] = result["file_id"]

    if letter_row["letterType"] in ["exit", "both"]:
        exit_buffer = generate_letter_pdf(letter_row, "exit")
        filename = f"exit_letter_{letter_row['employeeName'].replace(' ', '_')}.pdf"
        result = drive_service.upload_pdf(exit_buffer, filename)
        if result:
            files.append({"type": "exit", "filename": filename, "file_id": result["file_id"], "web_view_link": result["web_view_link"], "download_link": result.get("download_link")})
            updates["exit_letter_link"] = result["web_view_link"]
            updates["exit_file_id"] = result["file_id"]

    if letter_row["letterType"] == "offer":
        offer_buffer = generate_letter_pdf(letter_row, "offer")
        filename = f"offer_letter_{letter_row['employeeName'].replace(' ', '_')}.pdf"
        result = drive_service.upload_pdf(offer_buffer, filename)
        if result:
            files.append({"type": "offer", "filename": filename, "file_id": result["file_id"], "web_view_link": result["web_view_link"], "download_link": result.get("download_link")})
            updates["offer_letter_link"] = result["web_view_link"]
            updates["offer_file_id"] = result["file_id"]

    updates["pdf_files"] = files
    return updates


@router.post("/letters/request")
async def create_letter_request(request: LetterRequest, current_user: dict = Depends(require_role("hr", "director"))):
    try:
        is_director = current_user.get("role") == "director"
        db_row = await _build_db_row(request, current_user, "approved" if is_director else "pending")
        response = supabase.table("letter_requests").insert(db_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create letter request")

        if is_director:
            approver_row = await _user_row(current_user.get("uid"))
            updates = await _generate_and_store_files({
                **request.model_dump(),
                "approverName": current_user.get("name"),
                "employeeName": request.employeeName,
            }, current_user.get("name"))
            updates.update({
                "approved_by": str(approver_row["id"]) if approver_row else None,
                "approver_name": current_user.get("name"),
                "approved_on": datetime.utcnow().isoformat(),
                "reference_number": f"JOYRTS/HR/{datetime.now().strftime('%Y%m%d')}/{request.employeeId}",
            })
            if request.letterType == "both":
                updates["status"] = "approved"
            supabase.table("letter_requests").update(updates).eq("id", inserted["id"]).execute()
            inserted = supabase.table("letter_requests").select("*").eq("id", inserted["id"]).single().execute().data

        public_row = await _public_row(inserted)
        return {
            "id": public_row["id"],
            "message": "Letter generated and approved successfully" if is_director else "Letter request submitted successfully",
            **public_row,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/letters/requests")
async def get_all_requests(current_user: dict = Depends(require_role("hr", "director"))):
    try:
        current_row = await _user_row(current_user.get("uid"))
        query = supabase.table("letter_requests").select("*")
        if current_user.get("role") == "hr":
            query = query.eq("requested_by", str(current_row["id"]))
        result = query.order("requested_on", desc=True).execute().data or []
        return [await _public_row(row) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/letters/pending")
async def get_pending_requests(current_user: dict = Depends(require_role("director"))):
    try:
        result = supabase.table("letter_requests").select("*").eq("status", "pending").order("requested_on", desc=True).execute().data or []
        return [await _public_row(row) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/letters/issued")
async def get_issued_letters(current_user: dict = Depends(require_role("hr", "director"))):
    try:
        result = supabase.table("letter_requests").select("*").eq("status", "approved").order("approved_on", desc=True).execute().data or []
        return [await _public_row(row) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/letters/approve/{letter_id}")
async def approve_letter_request(letter_id: str, approval: ApprovalRequest, current_user: dict = Depends(require_role("director"))):
    try:
        doc = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=404, detail="Letter request not found")
        letter_data = doc.data
        if letter_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Letter request is not pending")

        updates = await _generate_and_store_files({**await _public_row(letter_data), "approverName": approval.approverName}, approval.approverName)
        approver_row = await _user_row(current_user.get("uid"))
        updates.update({
            "status": "approved",
            "approved_by": str(approver_row["id"]) if approver_row else None,
            "approver_name": approval.approverName,
            "approved_on": datetime.utcnow().isoformat(),
            "reference_number": letter_data.get("reference_number") or f"JOYRTS/HR/{datetime.now().strftime('%Y%m%d')}/{letter_data.get('employee_id')}",
        })
        supabase.table("letter_requests").update(updates).eq("id", letter_id).execute()
        result = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute().data
        return {"message": "Letter approved and PDF uploaded to Google Drive successfully", **await _public_row(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/letters/reject/{letter_id}")
async def reject_letter_request(letter_id: str, rejection: RejectionRequest, current_user: dict = Depends(require_role("director"))):
    try:
        doc = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=404, detail="Letter request not found")
        letter_data = doc.data
        if letter_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Letter request is not pending")

        rejector_row = await _user_row(current_user.get("uid"))
        supabase.table("letter_requests").update({
            "status": "rejected",
            "rejected_by": str(rejector_row["id"]) if rejector_row else None,
            "rejection_reason": rejection.rejectionReason,
            "rejected_on": datetime.utcnow().isoformat(),
        }).eq("id", letter_id).execute()
        result = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute().data
        return {"message": "Letter request rejected", **await _public_row(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/letters/download/{letter_id}")
async def download_letter_pdf(
    letter_id: str,
    letter_type: Optional[str] = None,
    current_user: dict = Depends(require_role("hr", "director")),
):
    try:
        doc = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=404, detail="Letter not found")
        letter_data = await _public_row(doc.data)
        if letter_data.get("status") != "approved":
            raise HTTPException(status_code=400, detail="Letter is not approved yet")

        request_letter_type = letter_data["letterType"]
        if not letter_type:
            if request_letter_type in ["experience", "both"]:
                letter_type = "experience"
            elif request_letter_type == "offer":
                letter_type = "offer"
            else:
                letter_type = "exit"

        file_id_key = f"{letter_type}_file_id"
        file_id = letter_data.get(file_id_key)
        if not file_id:
            pdf_buffer = generate_letter_pdf({**letter_data, "approverName": letter_data.get("approverName", "Director")}, letter_type)
            filename = f"{letter_type}_letter_{letter_data['employeeName'].replace(' ', '_')}.pdf"
            return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})

        pdf_buffer = drive_service.get_file(file_id)
        if not pdf_buffer:
            pdf_buffer = generate_letter_pdf({**letter_data, "approverName": letter_data.get("approverName", "Director")}, letter_type)
        filename = f"{letter_type}_letter_{letter_data['employeeName'].replace(' ', '_')}.pdf"
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/letters/{letter_id}")
async def get_letter_details(letter_id: str, current_user: dict = Depends(require_role("hr", "director"))):
    try:
        doc = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=404, detail="Letter not found")
        return await _public_row(doc.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
