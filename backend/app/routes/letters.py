from datetime import datetime
from io import BytesIO
import html
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.dependencies import get_current_user, require_role, supabase
from app.supabase_helper import SupabaseHelper

router = APIRouter()


class LetterRequest(BaseModel):
    employeeId: str
    employeeName: Optional[str] = None
    employeeEmail: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    letterType: Optional[str] = None
    templateKey: Optional[str] = None
    documentData: Dict[str, Any] = Field(default_factory=dict)
    lastWorkingDay: Optional[str] = None
    reasonForExit: Optional[str] = None
    additionalComments: Optional[str] = None
    requestedBy: Optional[str] = None
    requestedByName: Optional[str] = None
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


class TemplateVersionInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=30000)
    signatureTitle: str = Field(default="Authorized Signatory", max_length=200)
    fields: List[Dict[str, Any]] = Field(default_factory=list)


class TemplateCreateInput(TemplateVersionInput):
    templateKey: str
    name: str
    category: str = "employment"


class TemplatePreviewInput(BaseModel):
    templateKey: str
    version: Optional[int] = None
    sampleData: Dict[str, Any] = Field(default_factory=dict)


class DocumentSettingsInput(BaseModel):
    companyName: str
    companyAddress: str = ""
    companyEmail: str = ""
    companyPhone: str = ""
    labourIdentificationNumber: str = ""
    referencePrefix: str = "HESTIA/HR"


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
    company_name = html.escape(str(letter_data.get("companyName") or "Hestia"))
    company_email = html.escape(str(letter_data.get("companyEmail") or ""))
    header_left = Paragraph(company_name, title_style)
    header_right = Paragraph(f"{company_email}<br/>Date: {current_date}", right_style)
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
        story.append(Paragraph(f"Dear {html.escape(str(letter_data['employeeName']))},", normal_style))
        story.append(Paragraph(f"We are pleased to offer you the position of <b>{html.escape(str(letter_data['designation']))}</b>.", normal_style))
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
    story.append(Paragraph(f"<b>{html.escape(str(approver))}</b>", normal_style))
    story.append(Paragraph(html.escape(str(letter_data.get("signatureTitle") or "Director")), normal_style))
    story.append(Paragraph(company_name, normal_style))
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_template_pdf(template: Dict[str, Any], data: Dict[str, Any], company_name: str, reference_number: str, approver_name: str = "", document_date: Optional[datetime] = None) -> BytesIO:
    """Render a versioned template as a polished, print-ready Hestia letter."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.82 * inch, leftMargin=0.82 * inch,
                                 topMargin=0.62 * inch, bottomMargin=0.72 * inch)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#17324D")
    accent = colors.HexColor("#0F766E")
    muted = colors.HexColor("#64748B")
    ink = colors.HexColor("#263445")
    title_style = ParagraphStyle("DocumentTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17,
                                  leading=22, alignment=TA_LEFT, textColor=navy, spaceBefore=20, spaceAfter=20)
    body_style = ParagraphStyle("DocumentBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5,
                                leading=17, alignment=TA_LEFT, textColor=ink, spaceAfter=12, allowWidows=0, allowOrphans=0)
    company_style = ParagraphStyle("CompanyName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20,
                                   leading=24, textColor=navy, alignment=TA_LEFT)
    department_style = ParagraphStyle("DepartmentName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8,
                                      leading=10, textColor=accent, alignment=TA_RIGHT)
    small_style = ParagraphStyle("DocumentMeta", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5,
                                 leading=12, textColor=muted)
    sign_style = ParagraphStyle("DocumentSignatory", parent=styles["BodyText"], fontSize=9.5,
                                leading=14, textColor=ink, spaceAfter=2)

    values = {key: "" if value is None else str(value) for key, value in data.items()}
    document_date = document_date or datetime.now()
    formatted_document_date = document_date.strftime("%d/%m/%Y")
    for field in template.get("fields") or []:
        key = str(field.get("key") or "")
        value = values.get(key, "")
        if value and field.get("type") == "date":
            try:
                values[key] = datetime.strptime(value, "%Y-%m-%d").strftime("%d %B %Y")
            except ValueError:
                pass
    values.update({"companyName": company_name, "referenceNumber": reference_number,
                   "documentDate": formatted_document_date, "approverName": approver_name})

    def render_text(source: str) -> str:
        escaped = html.escape(str(source or ""))
        return re.sub(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}",
                      lambda match: html.escape(values.get(match.group(1), "")), escaped)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin, 0.52 * inch, A4[0] - doc.rightMargin, 0.52 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(doc.leftMargin, 0.34 * inch, "CONFIDENTIAL  •  HUMAN RESOURCES")
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.34 * inch, f"Page {doc.page}")
        canvas.restoreState()

    story = []
    letterhead = Table([[Paragraph(html.escape(company_name), company_style),
                         Paragraph("PEOPLE &amp; CULTURE", department_style)]],
                       colWidths=[document.width * 0.68, document.width * 0.32])
    letterhead.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(letterhead)
    contact_lines = [data.get("companyAddress"), "  ·  ".join(value for value in [data.get("companyEmail"), data.get("companyPhone")] if value), data.get("labourIdentificationNumber")]
    contact_text = "<br/>".join(html.escape(str(line)) for line in contact_lines if line)
    if contact_text:
        story.append(Spacer(1, 3))
        story.append(Paragraph(contact_text, small_style))
    story.append(Spacer(1, 14))
    meta = Table([[Paragraph(f"<b>REFERENCE</b><br/>{html.escape(reference_number)}", small_style),
                   Paragraph(f"<b>DATE</b><br/>{formatted_document_date}", small_style)]],
                 colWidths=[document.width * 0.68, document.width * 0.32])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F7F8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2EC")),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#D9E2EC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([meta, Paragraph(html.escape(str(template.get("title") or "Employee Document").upper()), title_style)])

    raw_body = str(template.get("body") or "")
    raw_body = raw_body.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").replace("\r\n", "\n").replace("\r", "\n")
    for paragraph in re.split(r"\n\s*\n", raw_body.strip()):
        content = render_text(paragraph.strip()).replace("\n", "<br/>")
        if content.strip():
            story.append(Paragraph(content, body_style))

    story.extend([Spacer(1, 16), Paragraph("Sincerely,", sign_style), Spacer(1, 30)])
    if approver_name:
        story.append(Paragraph(f"<b>{html.escape(approver_name)}</b>", sign_style))
    story.append(Paragraph(html.escape(str(template.get("signature_title") or "Authorized Signatory")), sign_style))
    story.append(Paragraph(html.escape(company_name), sign_style))
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


def _template_snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key) for key in ("id", "template_key", "name", "version", "title", "body", "signature_title", "fields")}


def _validated_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(fields) > 40:
        raise HTTPException(status_code=422, detail="A template can contain at most 40 fields")
    clean: List[Dict[str, Any]] = []
    keys = set()
    for field in fields:
        key = str(field.get("key") or "").strip()
        label = str(field.get("label") or "").strip()
        field_type = str(field.get("type") or "text").strip().lower()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,49}", key) or not label:
            raise HTTPException(status_code=422, detail="Each field needs a valid key and label")
        if key in keys:
            raise HTTPException(status_code=422, detail=f"Duplicate template field key: {key}")
        if field_type not in {"text", "date", "textarea"}:
            raise HTTPException(status_code=422, detail=f"Unsupported field type for {label}")
        keys.add(key)
        clean.append({"key": key, "label": label[:120], "type": field_type, "required": bool(field.get("required"))})
    return clean


def _published_template(template_key: str) -> Dict[str, Any]:
    rows = supabase.table("document_templates").select("*").eq("template_key", template_key).eq("is_active", True).limit(1).execute().data or []
    template = rows[0] if rows else None
    if not template or not template.get("active_version"):
        raise HTTPException(status_code=404, detail="Published document template not found")
    versions = supabase.table("document_template_versions").select("*").eq("template_id", template["id"]).eq("version", template["active_version"]).eq("status", "published").limit(1).execute().data or []
    version = versions[0] if versions else None
    if not version:
        raise HTTPException(status_code=404, detail="Published document template version not found")
    return {**version, "template_id": template["id"], "template_key": template["template_key"], "name": template["name"], "category": template["category"]}


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
        "experience_letter_link": None,
        "experience_file_id": row.get("experience_file_id"),
        "exit_letter_link": None,
        "exit_file_id": row.get("exit_file_id"),
        "offer_letter_link": None,
        "offer_file_id": row.get("offer_file_id"),
        "templateKey": row.get("letter_type"),
        "templateVersion": row.get("template_version"),
        "documentData": row.get("document_data") or {},
        "generationStatus": row.get("generation_status") or "not_generated",
        "generationError": row.get("generation_error"),
    }


async def _build_db_row(request: LetterRequest, current_user: dict, status_value: str) -> Dict[str, Any]:
    employee_row = await _user_row(request.employeeId)
    requester_row = await _user_row(current_user.get("uid"))
    if not employee_row or not requester_row:
        raise HTTPException(status_code=404, detail="Employee or requester not found")
    template_key = (request.templateKey or request.letterType or "").strip().lower()
    if template_key == "exit":
        template_key = "relieving"
    if template_key == "both":
        raise HTTPException(status_code=422, detail="Choose Experience Certificate or Relieving Letter separately")
    template = _published_template(template_key)
    employee = SupabaseHelper._public_user(employee_row) or {}
    document_data = dict(request.documentData or {})
    for key in ("lastWorkingDay", "reasonForExit", "additionalComments", "joinDate", "annualSalary", "startDate", "probationPeriod", "noticePeriod"):
        value = getattr(request, key, None)
        if value is not None:
            document_data.setdefault(key, value)
    document_data.update({
        "employeeName": employee.get("name") or "",
        "employeeEmail": employee.get("email") or "",
        "department": employee.get("department") or "",
        "designation": employee.get("designation") or "",
        "joinDate": employee.get("date_of_joining") or employee.get("dateOfJoining") or document_data.get("joinDate") or "",
    })
    settings_row = supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}
    document_data["companyName"] = settings_row.get("company_name") or "Hestia"
    document_data["companyEmail"] = settings_row.get("company_email") or ""
    document_data["companyAddress"] = settings_row.get("company_address") or ""
    document_data["companyPhone"] = settings_row.get("company_phone") or ""
    document_data["labourIdentificationNumber"] = settings_row.get("labour_identification_number") or ""
    required = [field.get("key") for field in (template.get("fields") or []) if field.get("required")]
    missing = [str(key) for key in required if not str(document_data.get(str(key)) or "").strip()]
    if missing:
        raise HTTPException(status_code=422, detail=f"Required template fields are missing: {', '.join(missing)}")
    for field in template.get("fields") or []:
        key = str(field.get("key") or "")
        value = str(document_data.get(key) or "")
        if len(value) > 4000:
            raise HTTPException(status_code=422, detail=f"The {field.get('label') or key} field is too long")
        if value and field.get("type") == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=422, detail=f"The {field.get('label') or key} field must be a valid date")

    snapshot = _template_snapshot(template)
    last_working_day = document_data.get("lastWorkingDay")
    return {
        "template_id": template["template_id"],
        "template_version": template["version"],
        "template_snapshot": snapshot,
        "document_data": document_data,
        "employee_id": str(employee_row["id"]),
        "employee_name": document_data["employeeName"],
        "employee_email": document_data["employeeEmail"],
        "department": document_data["department"],
        "designation": document_data["designation"],
        "letter_type": template_key,
        "last_working_day": last_working_day,
        "reason_for_exit": document_data.get("reasonForExit"),
        "additional_comments": request.additionalComments,
        "requested_by": str(requester_row["id"]),
        "requested_by_name": current_user.get("name"),
        "join_date": document_data.get("joinDate"),
        "annual_salary": document_data.get("annualSalary"),
        "start_date": document_data.get("startDate"),
        "probation_period": document_data.get("probationPeriod"),
        "notice_period": document_data.get("noticePeriod"),
        "status": status_value,
        "requested_on": datetime.utcnow().isoformat(),
        "employment_period": calculate_employment_period(document_data.get("joinDate"), request.lastWorkingDay or document_data.get("lastWorkingDay")) if document_data.get("joinDate") and (request.lastWorkingDay or document_data.get("lastWorkingDay")) else None,
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
        "generation_status": "not_generated",
        "generation_error": None,
    }


def _mark_document_available(letter_row: Dict[str, Any]) -> Dict[str, Any]:
    """PDFs are rendered from the immutable database snapshot on download; no file service is required."""
    if not (letter_row.get("template_snapshot") or letter_row.get("templateSnapshot")):
        raise HTTPException(status_code=409, detail="The document template snapshot is missing")
    return {"pdf_files": [], "generation_status": "available", "generation_error": None}


@router.post("/letters/request")
async def create_letter_request(request: LetterRequest, current_user: dict = Depends(require_role("hr", "director"))):
    try:
        is_director = current_user.get("role") == "director"
        db_row = await _build_db_row(request, current_user, "pending")
        response = supabase.table("letter_requests").insert(db_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create letter request")

        if is_director:
            approver_row = await _user_row(current_user.get("uid"))
            settings_row = supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}
            reference = f"{settings_row.get('reference_prefix') or 'HESTIA/HR'}/{datetime.now().strftime('%Y%m%d')}/{str(inserted['id'])[:8].upper()}"
            supabase.table("letter_requests").update({"reference_number": reference}).eq("id", inserted["id"]).execute()
            inserted["reference_number"] = reference
            updates = _mark_document_available(inserted)
            updates.update({
                "status": "approved",
                "approved_by": str(approver_row["id"]) if approver_row else None,
                "approver_name": current_user.get("name"),
                "approved_on": datetime.utcnow().isoformat(),
                "generation_status": "available",
            })
            supabase.table("letter_requests").update(updates).eq("id", inserted["id"]).execute()
            inserted = supabase.table("letter_requests").select("*").eq("id", inserted["id"]).single().execute().data

        public_row = await _public_row(inserted)
        return {
            "id": public_row["id"],
            "message": "Document approved and available for download" if is_director else "Document request submitted successfully",
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

        approver_name = current_user.get("name") or "Director"
        approver_row = await _user_row(current_user.get("uid"))
        settings_row = supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}
        reference = letter_data.get("reference_number") or f"{settings_row.get('reference_prefix') or 'HESTIA/HR'}/{datetime.now().strftime('%Y%m%d')}/{str(letter_data.get('id'))[:8].upper()}"
        letter_data["reference_number"] = reference
        updates = _mark_document_available(letter_data)
        updates.update({
            "status": "approved",
            "approved_by": str(approver_row["id"]) if approver_row else None,
            "approver_name": approver_name,
            "approved_on": datetime.utcnow().isoformat(),
            "reference_number": reference,
            "generation_status": "available",
            "generation_error": None,
        })
        supabase.table("letter_requests").update(updates).eq("id", letter_id).execute()
        result = supabase.table("letter_requests").select("*").eq("id", letter_id).single().execute().data
        return {"message": "Document approved and available for download", **await _public_row(result)}
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
        row = doc.data
        letter_data = await _public_row(row)
        if letter_data.get("status") != "approved":
            raise HTTPException(status_code=400, detail="Letter is not approved yet")
        snapshot = row.get("template_snapshot")
        if snapshot:
            settings_row = supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}
            document_values = row.get("document_data") or {}
            issued_at = row.get("approved_on") or row.get("requested_on")
            try:
                document_date = datetime.fromisoformat(str(issued_at).replace("Z", "+00:00")) if issued_at else datetime.now()
            except ValueError:
                document_date = datetime.now()
            pdf_buffer = generate_template_pdf(snapshot, document_values,
                document_values.get("companyName") or settings_row.get("company_name") or "Hestia",
                row.get("reference_number") or "", row.get("approver_name") or "", document_date)
            document_type = str(row.get("letter_type") or "document")
        else:
            # Legacy requests predate template snapshots; render the legacy format directly.
            document_type = letter_type or str(letter_data.get("letterType") or "experience")
            if document_type == "relieving":
                document_type = "exit"
            pdf_buffer = generate_letter_pdf({**letter_data, "approverName": letter_data.get("approverName", "Director")}, document_type)
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(letter_data.get("employeeName") or "employee")).strip("_") or "employee"
        safe_type = re.sub(r"[^A-Za-z0-9_-]+", "_", document_type).strip("_") or "document"
        filename = f"{safe_type}_{safe_name}.pdf"
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _version_public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": str(row.get("id")), "version": row.get("version"), "title": row.get("title"),
            "body": row.get("body"), "signatureTitle": row.get("signature_title"),
            "fields": row.get("fields") or [], "status": row.get("status"),
            "createdAt": row.get("created_at"), "publishedAt": row.get("published_at")}


@router.get("/letters/templates")
async def list_document_templates(current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    templates = supabase.table("document_templates").select("*").order("category").order("name").execute().data or []
    if not templates:
        return []
    versions = supabase.table("document_template_versions").select("*").in_("template_id", [row["id"] for row in templates]).order("version", desc=True).execute().data or []
    by_template: Dict[str, List[Dict[str, Any]]] = {}
    for version in versions:
        by_template.setdefault(str(version.get("template_id")), []).append(version)
    result = []
    for row in templates:
        rows = by_template.get(str(row["id"]), [])
        active = next((version for version in rows if version.get("version") == row.get("active_version")), None)
        draft = next((version for version in rows if version.get("status") == "draft"), None)
        result.append({"id": str(row["id"]), "templateKey": row["template_key"], "name": row["name"],
                       "category": row["category"], "isActive": bool(row.get("is_active")),
                       "activeVersion": row.get("active_version"), "published": _version_public(active) if active else None,
                       "draft": _version_public(draft) if draft else None})
    return result


@router.post("/letters/templates", status_code=status.HTTP_201_CREATED)
async def create_document_template(template: TemplateCreateInput, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    key = re.sub(r"[^a-z0-9_]+", "_", template.templateKey.strip().lower()).strip("_")
    if not key or not template.name.strip() or not template.title.strip() or not template.body.strip():
        raise HTTPException(status_code=422, detail="Template key, name, title, and body are required")
    actor = await _user_row(current_user.get("uid"))
    try:
        inserted = supabase.table("document_templates").insert({"template_key": key, "name": template.name.strip(),
                    "category": template.category.strip() or "employment", "is_active": True}).execute().data
    except Exception:
        raise HTTPException(status_code=409, detail="A template with this key already exists")
    if not inserted:
        raise HTTPException(status_code=500, detail="Unable to create document template")
    template_row = inserted[0]
    version = supabase.table("document_template_versions").insert({
        "template_id": template_row["id"], "version": 1, "title": template.title.strip(), "body": template.body,
        "signature_title": template.signatureTitle.strip() or "Authorized Signatory", "fields": _validated_fields(template.fields),
        "status": "draft", "created_by": str(actor["id"]) if actor else None,
    }).execute().data
    return {"id": str(template_row["id"]), "templateKey": key, "name": template_row["name"],
            "category": template_row["category"], "isActive": True, "activeVersion": None,
            "published": None, "draft": _version_public(version[0]) if version else None}


@router.post("/letters/templates/{template_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_document_template_version(template_id: str, version_data: TemplateVersionInput, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    template = supabase.table("document_templates").select("id").eq("id", template_id).limit(1).execute().data
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    versions = supabase.table("document_template_versions").select("version").eq("template_id", template_id).order("version", desc=True).limit(1).execute().data or []
    next_version = int(versions[0]["version"]) + 1 if versions else 1
    actor = await _user_row(current_user.get("uid"))
    row = supabase.table("document_template_versions").insert({
        "template_id": template_id, "version": next_version, "title": version_data.title.strip(),
        "body": version_data.body, "signature_title": version_data.signatureTitle.strip() or "Authorized Signatory",
        "fields": _validated_fields(version_data.fields), "status": "draft", "created_by": str(actor["id"]) if actor else None,
    }).execute().data
    supabase.table("document_templates").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", template_id).execute()
    return _version_public(row[0]) if row else None


@router.post("/letters/templates/{template_id}/versions/{version_number}/publish")
async def publish_document_template_version(template_id: str, version_number: int, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    version = supabase.table("document_template_versions").select("*").eq("template_id", template_id).eq("version", version_number).limit(1).execute().data
    if not version:
        raise HTTPException(status_code=404, detail="Template version not found")
    actor = await _user_row(current_user.get("uid"))
    published_at = datetime.utcnow().isoformat()
    supabase.table("document_template_versions").update({"status": "published", "published_at": published_at,
        "published_by": str(actor["id"]) if actor else None}).eq("id", version[0]["id"]).execute()
    supabase.table("document_templates").update({"active_version": version_number, "is_active": True,
        "updated_at": published_at}).eq("id", template_id).execute()
    return {**_version_public(version[0]), "status": "published", "publishedAt": published_at}


@router.patch("/letters/templates/{template_id}/active")
async def set_document_template_active(template_id: str, active: bool, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    result = supabase.table("document_templates").update({"is_active": active, "updated_at": datetime.utcnow().isoformat()}).eq("id", template_id).execute().data
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"id": str(result[0]["id"]), "isActive": bool(result[0].get("is_active"))}


@router.post("/letters/templates/preview")
async def preview_document_template(preview: TemplatePreviewInput, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    template_rows = supabase.table("document_templates").select("*").eq("template_key", preview.templateKey).limit(1).execute().data or []
    if not template_rows:
        raise HTTPException(status_code=404, detail="Template not found")
    template_record = template_rows[0]
    version_number = preview.version if preview.version is not None else template_record.get("active_version")
    version_rows = supabase.table("document_template_versions").select("*").eq("template_id", template_record["id"]).eq("version", version_number).limit(1).execute().data or []
    if not version_rows:
        raise HTTPException(status_code=404, detail="Template version not found")
    template = {**version_rows[0], "template_key": preview.templateKey, "template_id": template_record["id"]}
    settings_row = supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}
    sample_data = {"employeeName": "Alex Employee", "designation": "Team Member", "department": "Operations",
                   "joinDate": "01/01/2024", "startDate": "01/11/2026", "lastWorkingDay": "31/10/2026",
                   "annualSalary": "600,000", "probationPeriod": "Three months", "noticePeriod": "30 days",
                   "employmentType": "Regular", "duties": "As assigned", "socialSecurity": "As applicable",
                   "effectiveDate": "01/11/2026", "newDesignation": "Senior Team Member",
                   "verificationPurpose": "Bank verification", "certificationPurpose": "Visa application",
                   "nocPurpose": "Personal purpose", "agreementTerms": "Confidentiality and intellectual property terms",
                   "policyName": "Code of Conduct", "acknowledgementText": "I acknowledge receipt and understanding."}
    sample_data.update({"companyAddress": settings_row.get("company_address") or "", "companyEmail": settings_row.get("company_email") or "",
                        "companyPhone": settings_row.get("company_phone") or "", "labourIdentificationNumber": settings_row.get("labour_identification_number") or ""})
    for field in version_rows[0].get("fields") or []:
        sample_data.setdefault(str(field.get("key") or ""), f"Sample {field.get('label') or 'value'}")
    sample_data.update(preview.sampleData or {})
    pdf = generate_template_pdf(template, sample_data, settings_row.get("company_name") or "Hestia", "PREVIEW-0001", "Authorized Signatory")
    return StreamingResponse(pdf, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=document-template-preview.pdf"})


@router.get("/letters/settings")
async def get_document_settings(current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    return supabase.table("document_settings").select("*").eq("id", 1).single().execute().data or {}


@router.put("/letters/settings")
async def update_document_settings(settings_data: DocumentSettingsInput, current_user: dict = Depends(require_role("hr", "director", "super_admin"))):
    actor = await _user_row(current_user.get("uid"))
    updates = {"company_name": settings_data.companyName.strip(), "company_address": settings_data.companyAddress.strip(),
               "company_email": settings_data.companyEmail.strip(), "company_phone": settings_data.companyPhone.strip(),
               "labour_identification_number": settings_data.labourIdentificationNumber.strip(),
               "reference_prefix": settings_data.referencePrefix.strip().strip("/"),
               "updated_at": datetime.utcnow().isoformat(), "updated_by": str(actor["id"]) if actor else None}
    row = supabase.table("document_settings").update(updates).eq("id", 1).execute().data
    return row[0] if row else updates


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
