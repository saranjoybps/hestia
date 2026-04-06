from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.dependencies import db, get_current_user, require_role
from app.services.google_drive import drive_service
from io import BytesIO
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os
from google.cloud import firestore

router = APIRouter()

# Pydantic Models
class LetterRequest(BaseModel):
    employeeId: str
    employeeName: str
    employeeEmail: str
    department: str
    designation: str
    letterType: str  # 'exit', 'experience', 'both', 'offer'
    lastWorkingDay: str
    reasonForExit: Optional[str] = None
    additionalComments: Optional[str] = None
    requestedBy: str
    requestedByName: str
    joinDate: Optional[str] = None
    # Offer letter specific fields
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

# Helper function to calculate employment period
def calculate_employment_period(join_date_str: str, last_working_day_str: str) -> str:
    """Calculate employment period from join date to last working day"""
    try:
        join_date = datetime.fromisoformat(join_date_str.replace('Z', '+00:00'))
        last_day = datetime.fromisoformat(last_working_day_str.replace('Z', '+00:00'))
        
        years = last_day.year - join_date.year
        months = last_day.month - join_date.month
        
        if months < 0:
            years -= 1
            months += 12
        
        if years > 0 and months > 0:
            return f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
        elif years > 0:
            return f"{years} year{'s' if years > 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            return "Less than a month"
    except:
        return "Duration not calculated"

def number_to_words_indian(number: int) -> str:
    """Convert a number to words in the Indian numbering system (up to crores)."""
    if number == 0:
        return "zero"
    if number < 0:
        return "minus " + number_to_words_indian(abs(number))

    ones = [
        "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"
    ]
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

# Helper function to generate PDF
def generate_letter_pdf(letter_data: dict, letter_type: str) -> BytesIO:
    """Generate PDF letter using ReportLab"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=8,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=4,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=6
    )
    
    center_style = ParagraphStyle(
        'CustomCenter',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=8
    )
    
    right_style = ParagraphStyle(
        'CustomRight',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=6
    )

    header_right_style = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
        textColor=colors.black
    )

    line_color = colors.HexColor('#38bdf8')

    def draw_page_lines(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(line_color)
        canvas_obj.setLineWidth(1.5)
        page_width, page_height = A4
        top_y = page_height - 1.05 * inch
        bottom_y = 0.65 * inch
        canvas_obj.line(doc_obj.leftMargin, top_y, page_width - doc_obj.rightMargin, top_y)
        canvas_obj.line(doc_obj.leftMargin, bottom_y, page_width - doc_obj.rightMargin, bottom_y)
        canvas_obj.restoreState()
    
    # Company Header with logo and contact
    current_date = datetime.now().strftime("%d/%m/%Y")
    logo_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "logo.png")
    )
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=1.4*inch, height=0.5*inch)
    else:
        logo = Paragraph("JOYRTS", title_style)

    header_right = Paragraph(
        f"admin@joyrts.com<br/>Date: {current_date}",
        header_right_style
    )

    header_table = Table(
        [[logo, header_right]],
        colWidths=[2.0*inch, 4.2*inch]
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.1*inch))
    
    # Letter Title and Content based on type
    if letter_type == 'offer':
        # Offer Letter
        letter_title = "OFFER OF EMPLOYMENT"
        story.append(Paragraph(letter_title, heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("<b>Subject: Offer of Employment and Contractual Commitment</b>", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph(f"Dear {letter_data['employeeName']},", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph(
            "We are pleased to extend this formal offer of employment to you following your application and successful interview with Joyrts.",
            normal_style
        ))
        story.append(Paragraph(
            f"We are delighted to offer you the position of <b>{letter_data['designation']}</b>. We believe your skills and experience will be a valuable addition to our organization.",
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        start_date_formatted = datetime.fromisoformat(letter_data['startDate'].replace('Z', '+00:00')).strftime('%d/%m/%Y')
        probation = letter_data.get('probationPeriod', 'three months')
        notice = letter_data.get('noticePeriod', '45 days')
        salary_raw = str(letter_data.get('annualSalary', '') or '')
        salary_digits = ''.join(ch for ch in salary_raw if ch.isdigit())
        salary_value = int(salary_digits) if salary_digits else 0
        salary_words = number_to_words_indian(salary_value) if salary_value else salary_raw
        salary_display = salary_value if salary_value else salary_raw
        
        story.append(Paragraph("<b>Compensation (Annual Gross Emoluments):</b>", normal_style))
        story.append(Paragraph(
            f"Your annual gross compensation, inclusive of all benefits, will be INR {salary_display} (Rupees {salary_words} only).",
            normal_style
        ))
        story.append(Paragraph(
            "Your performance will be reviewed periodically, typically at the end of each financial year. Continued employment is subject to satisfactory performance as per company standards.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Joining Details:</b>", normal_style))
        story.append(Paragraph(
            f"Your employment will commence on {start_date_formatted}.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Probation Period:</b>", normal_style))
        story.append(Paragraph(
            f"You will be on a probation period of {probation} from your date of joining.",
            normal_style
        ))
        story.append(Paragraph(
            "Upon successful completion of probation, you will be confirmed as a permanent employee of the company.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Leave Policy:</b>", normal_style))
        story.append(Paragraph("During probation: No leave. If leave is taken, it will be treated as loss of pay.", normal_style))
        story.append(Paragraph("After confirmation: 2 day(s) per month. If exceeded, it will be treated as loss of pay.", normal_style))
        story.append(Paragraph("Unused leaves may be carried forward as per company policy.", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Contractual Commitment:</b>", normal_style))
        story.append(Paragraph(
            "You are required to serve a minimum period of three months from the date of joining.",
            normal_style
        ))
        story.append(Paragraph(
            "Resignation during this period will not be permitted except under exceptional circumstances and subject to management approval.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Notice Period:</b>", normal_style))
        story.append(Paragraph(
            f"After completion of the commitment period, a {notice} notice period will be applicable for resignation.",
            normal_style
        ))
        story.append(Paragraph("A buyout option may be available as per company policy.", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Relocation Clause:</b>", normal_style))
        story.append(Paragraph(
            "You may be required to relocate to other locations based on business requirements.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Other Terms and Conditions:</b>", normal_style))
        story.append(Paragraph(
            "All additional terms of employment, including roles and responsibilities, will be governed by company policies.",
            normal_style
        ))
        story.append(Paragraph(
            "Any breach of agreement may lead to appropriate action as per company rules and applicable laws.",
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(
            "We warmly welcome you to Joyrts and look forward to your valuable contribution.",
            normal_style
        ))
        story.append(Paragraph(
            "For any queries, please contact fedolin HR at jfedolin@gmail.com / Email.",
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(
            "Please sign and return a copy of this letter as a token of your acceptance of the above terms.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("Welcome aboard!", normal_style))
        story.append(Paragraph("Sincerely,", normal_style))
        story.append(Paragraph("Joyrts ltd", normal_style))
        story.append(Spacer(1, 0.25*inch))
        
        story.append(Paragraph("<b>Employee Acknowledgment</b>", normal_style))
        story.append(Paragraph(
            f"I, {letter_data['employeeName']}, accept the terms and conditions mentioned above and agree to serve Joyrts as a {letter_data['designation']}, adhering to all policies including contractual commitment and notice period.",
            normal_style
        ))
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Signature: _______________________", normal_style))
        story.append(Paragraph("Date: _______________________", normal_style))
    elif letter_type == 'experience':
        letter_title = "EXPERIENCE CERTIFICATE"
        story.append(Paragraph(letter_title, heading_style))
        story.append(Spacer(1, 0.2*inch))
    else:
        letter_title = "EXIT LETTER"
        story.append(Paragraph(letter_title, heading_style))
        story.append(Spacer(1, 0.2*inch))
    
    # Letter Body
    if letter_type == 'experience':
        # Experience Letter Content
        story.append(Paragraph("To Whom It May Concern,", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        content = f"""
        This is to certify that <b>{letter_data['employeeName']}</b> was employed with Joyrts as 
        <b>{letter_data['designation']}</b> in the <b>{letter_data['department']}</b> department.
        """
        story.append(Paragraph(content, normal_style))
        
        employment_period = letter_data.get('employmentPeriod', 'the duration of their employment')
        period_content = f"""
        The period of employment was from <b>{datetime.fromisoformat(letter_data['joinDate'].replace('Z', '+00:00')).strftime('%B %d, %Y')}</b> 
        to <b>{datetime.fromisoformat(letter_data['lastWorkingDay']).strftime('%B %d, %Y')}</b>, 
        totaling <b>{employment_period}</b>.
        """
        story.append(Paragraph(period_content, normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        performance = f"""
        During their tenure, {letter_data['employeeName']} demonstrated professionalism, dedication, and 
        contributed significantly to the team and organizational goals. We appreciate their service and 
        wish them success in their future endeavors.
        """
        story.append(Paragraph(performance, normal_style))
        
    elif letter_type == 'exit':
        # Exit Letter Content
        story.append(Paragraph(f"Dear {letter_data['employeeName']},", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        content = f"""
        This letter is to formally acknowledge your resignation from the position of 
        <b>{letter_data['designation']}</b> in the <b>{letter_data['department']}</b> department at Joyrts.
        """
        story.append(Paragraph(content, normal_style))
        
        last_day_content = f"""
        Your last working day with Joyrts will be <b>{datetime.fromisoformat(letter_data['lastWorkingDay']).strftime('%B %d, %Y')}</b>.
        """
        story.append(Paragraph(last_day_content, normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        employment_period = letter_data.get('employmentPeriod', 'your time')
        closing = f"""
        We sincerely appreciate your contributions during {employment_period} with our organization. 
        Your dedication and professionalism have been valuable to our team. We wish you all the best 
        in your future professional and personal endeavors.
        """
        story.append(Paragraph(closing, normal_style))
        
        if letter_data.get('reasonForExit'):
            story.append(Spacer(1, 0.1*inch))
            reason_content = f"""
            <b>Reason for Exit:</b> {letter_data['reasonForExit']}
            """
            story.append(Paragraph(reason_content, normal_style))
    
    # Only add closing signature for non-offer letters (offer has its own signature section)
    if letter_type != 'offer':
        story.append(Spacer(1, 0.3*inch))
        
        # Closing
        story.append(Paragraph("Sincerely,", normal_style))
        story.append(Spacer(1, 0.5*inch))
        
        # Signature section
        story.append(Paragraph(f"<b>{letter_data['approverName']}</b>", normal_style))
        story.append(Paragraph("Director", normal_style))
        story.append(Paragraph("Joyrts", normal_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Footer intentionally omitted\n\n    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Endpoints
@router.post("/letters/request")
async def create_letter_request(
    request: LetterRequest,
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Create a new letter request (HR and Directors can create)"""
    try:
        # Calculate employment period
        employment_period = ""
        if request.joinDate:
            employment_period = calculate_employment_period(
                request.joinDate, 
                request.lastWorkingDay
            )
        
        # Create request document
        # If submitted by director, auto-approve and generate PDF
        is_director = current_user.get('role') == 'director'
        
        letter_data = {
            "employeeId": request.employeeId,
            "employeeName": request.employeeName,
            "employeeEmail": request.employeeEmail,
            "department": request.department,
            "designation": request.designation,
            "letterType": request.letterType,
            "lastWorkingDay": request.lastWorkingDay,
            "reasonForExit": request.reasonForExit,
            "additionalComments": request.additionalComments,
            "requestedBy": request.requestedBy,
            "requestedByName": request.requestedByName,
            "requestedOn": datetime.now().isoformat(),
            "status": "approved" if is_director else "pending",
            "employmentPeriod": employment_period,
            "joinDate": request.joinDate,
        }
        
        # If director, add approval info immediately
        if is_director:
            letter_data.update({
                "approvedBy": current_user.get('uid'),
                "approverName": current_user.get('name'),
                "approvedOn": datetime.now().isoformat(),
            })
        
        # Add offer letter specific fields
        if request.letterType == 'offer':
            letter_data.update({
                "annualSalary": request.annualSalary,
                "startDate": request.startDate,
                "probationPeriod": request.probationPeriod or "three months",
                "noticePeriod": request.noticePeriod or "45 days",
            })
        
        # Add to Firestore
        doc_ref = db.collection('letter_requests').add(letter_data)
        letter_id = doc_ref[1].id
        
        # If director submitted, generate PDF immediately
        if is_director:
            letter_data['referenceNumber'] = f"JOYRTS/HR/{datetime.now().strftime('%Y%m%d')}/{request.employeeId}"
            
            if request.letterType == 'both':
                # Generate both letters
                exp_pdf = generate_letter_pdf(letter_data, 'experience')
                exit_pdf = generate_letter_pdf(letter_data, 'exit')
                
                # Upload to Google Drive
                exp_file = drive_service.upload_pdf(
                    exp_pdf,
                    f"{request.employeeName.replace(' ', '_')}_experience_certificate.pdf"
                )
                exit_file = drive_service.upload_pdf(
                    exit_pdf,
                    f"{request.employeeName.replace(' ', '_')}_exit_letter.pdf"
                )
                
                # Update request with file info (only if upload succeeded)
                update_payload = {}
                pdf_files = []
                if exp_file:
                    update_payload.update({
                        'experience_letter_link': exp_file['web_view_link'],
                        'experience_file_id': exp_file['file_id'],
                    })
                    pdf_files.append({
                        'type': 'experience',
                        'filename': f"{request.employeeName.replace(' ', '_')}_experience_certificate.pdf",
                        'file_id': exp_file['file_id'],
                        'web_view_link': exp_file['web_view_link']
                    })
                if exit_file:
                    update_payload.update({
                        'exit_letter_link': exit_file['web_view_link'],
                        'exit_file_id': exit_file['file_id'],
                    })
                    pdf_files.append({
                        'type': 'exit',
                        'filename': f"{request.employeeName.replace(' ', '_')}_exit_letter.pdf",
                        'file_id': exit_file['file_id'],
                        'web_view_link': exit_file['web_view_link']
                    })
                if pdf_files:
                    update_payload['pdfFiles'] = pdf_files
                if update_payload:
                    db.collection('letter_requests').document(letter_id).update(update_payload)
            else:
                # Generate single letter
                pdf_buffer = generate_letter_pdf(letter_data, request.letterType)
                
                letter_type_name = 'offer_letter' if request.letterType == 'offer' else f'{request.letterType}_letter'
                filename = f"{request.employeeName.replace(' ', '_')}_{letter_type_name}.pdf"
                
                # Upload to Google Drive
                file_info = drive_service.upload_pdf(pdf_buffer, filename)
                
                # Update request with file info (only if upload succeeded)
                if file_info:
                    db.collection('letter_requests').document(letter_id).update({
                        f'{request.letterType}_letter_link': file_info['web_view_link'],
                        f'{request.letterType}_file_id': file_info['file_id'],
                        'pdfFiles': [{
                            'type': request.letterType,
                            'filename': filename,
                            'file_id': file_info['file_id'],
                            'web_view_link': file_info['web_view_link']
                        }]
                    })
        
        return {
            "id": letter_id,
            "message": "Letter generated and approved successfully" if is_director else "Letter request submitted successfully",
            **letter_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/letters/requests")
async def get_all_requests(current_user: dict = Depends(require_role("hr", "director"))):
    """Get all letter requests (HR and Director)"""
    try:
        # HR sees only their requests, Directors see all
        if current_user.get('role') == 'hr':
            requests = db.collection('letter_requests')\
                .where('requestedBy', '==', current_user.get('uid'))\
                .order_by('requestedOn', direction=firestore.Query.DESCENDING)\
                .stream()
        else:
            requests = db.collection('letter_requests')\
                .order_by('requestedOn', direction=firestore.Query.DESCENDING)\
                .stream()
        
        result = []
        for req in requests:
            data = req.to_dict()
            data['id'] = req.id
            result.append(data)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/letters/pending")
async def get_pending_requests(current_user: dict = Depends(require_role("director"))):
    """Get pending letter requests (Directors only)

    The query deliberately avoids an `order_by` clause to prevent the
    Firestore composite index requirement. Sorting is performed in Python.
    """
    try:
        query = db.collection('letter_requests').where('status', '==', 'pending')
        requests = query.stream()
        
        result = []
        for req in requests:
            data = req.to_dict()
            data['id'] = req.id
            result.append(data)
        
        # sort by requestedOn descending
        result.sort(key=lambda x: x.get('requestedOn', ''), reverse=True)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/letters/issued")
async def get_issued_letters(current_user: dict = Depends(require_role("hr", "director"))):
    """Get all approved/issued letters"""
    try:
        # We used to sort directly in the Firestore query, but that required creating
        # a composite index which was causing errors for some users (e.g. Directors).
        # To avoid index configuration, fetch the documents and sort in Python.
        letters = db.collection('letter_requests')\
            .where('status', '==', 'approved')\
            .stream()
        
        result = []
        for letter in letters:
            data = letter.to_dict()
            data['id'] = letter.id
            result.append(data)
        
        # sort by approvedOn descending; missing values are treated as oldest
        result.sort(
            key=lambda d: d.get('approvedOn') or 0,
            reverse=True
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/letters/approve/{letter_id}")
async def approve_letter_request(
    letter_id: str,
    approval: ApprovalRequest,
    current_user: dict = Depends(require_role("director"))
):
    """Approve letter request and generate PDF (Directors only)"""
    try:
        # Get letter request
        doc_ref = db.collection('letter_requests').document(letter_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Letter request not found")
        
        letter_data = doc.to_dict()
        
        if letter_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Letter request is not pending")
        
        # Add approver info to letter data for PDF generation
        letter_data['approverName'] = approval.approverName
        
        # Generate PDFs based on letter type and upload to Google Drive
        pdf_files = []
        drive_links = {}
        
        if letter_data['letterType'] in ['experience', 'both']:
            # Generate Experience Letter PDF
            exp_buffer = generate_letter_pdf(letter_data, 'experience')
            filename = f"experience_letter_{letter_data['employeeName'].replace(' ', '_')}_{letter_id}.pdf"
            
            # Upload to Google Drive
            drive_result = drive_service.upload_pdf(exp_buffer, filename)
            if drive_result:
                pdf_files.append({
                    'type': 'experience',
                    'filename': filename,
                    'file_id': drive_result['file_id'],
                    'web_view_link': drive_result['web_view_link'],
                    'download_link': drive_result.get('download_link')
                })
                drive_links['experience_letter_link'] = drive_result['web_view_link']
                drive_links['experience_file_id'] = drive_result['file_id']
        
        if letter_data['letterType'] in ['exit', 'both']:
            # Generate Exit Letter PDF
            exit_buffer = generate_letter_pdf(letter_data, 'exit')
            filename = f"exit_letter_{letter_data['employeeName'].replace(' ', '_')}_{letter_id}.pdf"
            
            # Upload to Google Drive
            drive_result = drive_service.upload_pdf(exit_buffer, filename)
            if drive_result:
                pdf_files.append({
                    'type': 'exit',
                    'filename': filename,
                    'file_id': drive_result['file_id'],
                    'web_view_link': drive_result['web_view_link'],
                    'download_link': drive_result.get('download_link')
                })
                drive_links['exit_letter_link'] = drive_result['web_view_link']
                drive_links['exit_file_id'] = drive_result['file_id']
        
        # Update request status with Google Drive links
        update_data = {
            "status": "approved",
            "approvedBy": approval.approvedBy,
            "approverName": approval.approverName,
            "approvedOn": datetime.now().isoformat(),
            "pdfFiles": pdf_files,
            **drive_links
        }
        
        doc_ref.update(update_data)
        
        # Return the updated data
        updated_doc = doc_ref.get()
        result = updated_doc.to_dict()
        result['id'] = letter_id
        
        return {
            "message": "Letter approved and PDF uploaded to Google Drive successfully",
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/letters/reject/{letter_id}")
async def reject_letter_request(
    letter_id: str,
    rejection: RejectionRequest,
    current_user: dict = Depends(require_role("director"))
):
    """Reject letter request (Directors only)"""
    try:
        # Get letter request
        doc_ref = db.collection('letter_requests').document(letter_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Letter request not found")
        
        letter_data = doc.to_dict()
        
        if letter_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Letter request is not pending")
        
        # Update request status
        update_data = {
            "status": "rejected",
            "rejectedBy": rejection.rejectedBy,
            "rejectionReason": rejection.rejectionReason,
            "rejectedOn": datetime.now().isoformat(),
        }
        
        doc_ref.update(update_data)
        
        # Return the updated data
        updated_doc = doc_ref.get()
        result = updated_doc.to_dict()
        result['id'] = letter_id
        
        return {
            "message": "Letter request rejected",
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/letters/download/{letter_id}")
async def download_letter_pdf(
    letter_id: str,
    letter_type: Optional[str] = None,  # 'exit' or 'experience', optional for 'both' type
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Download letter PDF from Google Drive"""
    try:
        # Get letter request
        doc_ref = db.collection('letter_requests').document(letter_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Letter not found")
        
        letter_data = doc.to_dict()
        
        if letter_data.get('status') != 'approved':
            raise HTTPException(status_code=400, detail="Letter is not approved yet")
        
        # Determine which file to download
        request_letter_type = letter_data['letterType']
        if not letter_type:
            # Default behavior:
            # - experience/both -> experience
            # - offer -> offer
            # - exit -> exit
            if request_letter_type in ['experience', 'both']:
                letter_type = 'experience'
            elif request_letter_type == 'offer':
                letter_type = 'offer'
            else:
                letter_type = 'exit'
        
        # Get file ID from letter data
        file_id_key = f"{letter_type}_file_id"
        file_id = letter_data.get(file_id_key)
        
        if not file_id:
            # If Drive upload didn't happen, regenerate the PDF on the fly
            pdf_buffer = generate_letter_pdf(letter_data, letter_type)
            filename = f"{letter_type}_letter_{letter_data['employeeName'].replace(' ', '_')}.pdf"
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        
        # Download from Google Drive
        pdf_buffer = drive_service.get_file(file_id)
        
        if not pdf_buffer:
            # Fallback: regenerate PDF if Google Drive download fails
            print(f"Failed to download from Drive, regenerating PDF for {letter_id}")
            pdf_buffer = generate_letter_pdf(letter_data, letter_type)
        
        # Return PDF as streaming response
        filename = f"{letter_type}_letter_{letter_data['employeeName'].replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/letters/{letter_id}")
async def get_letter_details(
    letter_id: str,
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Get letter request details"""
    try:
        doc_ref = db.collection('letter_requests').document(letter_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Letter not found")
        
        result = doc.to_dict()
        result['id'] = letter_id
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





