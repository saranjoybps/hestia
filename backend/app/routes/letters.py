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
from google.cloud import firestore

router = APIRouter()

# Pydantic Models
class LetterRequest(BaseModel):
    employeeId: str
    employeeName: str
    employeeEmail: str
    department: str
    designation: str
    letterType: str  # 'exit', 'experience', 'both'
    lastWorkingDay: str
    reasonForExit: Optional[str] = None
    additionalComments: Optional[str] = None
    requestedBy: str
    requestedByName: str
    joinDate: Optional[str] = None

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
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=10
    )
    
    center_style = ParagraphStyle(
        'CustomCenter',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=8
    )
    
    right_style = ParagraphStyle(
        'CustomRight',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        spaceAfter=6
    )
    
    # Company Header
    story.append(Paragraph("JOYRTS", title_style))
    story.append(Paragraph("Human Resources Management", center_style))
    story.append(Paragraph("Building Innovation Together", center_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Date and Reference
    current_date = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Date: {current_date}", right_style))
    story.append(Paragraph(f"Ref: JOYRTS/HR/{datetime.now().strftime('%Y%m%d')}/{letter_data['employeeId']}", right_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Letter Title
    if letter_type == 'experience':
        letter_title = "EXPERIENCE CERTIFICATE"
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
        
    else:
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
    
    story.append(Spacer(1, 0.3*inch))
    
    # Closing
    story.append(Paragraph("Sincerely,", normal_style))
    story.append(Spacer(1, 0.5*inch))
    
    # Signature section
    story.append(Paragraph(f"<b>{letter_data['approverName']}</b>", normal_style))
    story.append(Paragraph("Director", normal_style))
    story.append(Paragraph("Joyrts", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        leading=10
    )
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("─" * 80, footer_style))
    story.append(Paragraph("This is a system-generated document from Joyrts HR Management App.", footer_style))
    story.append(Paragraph(f"Generated on {current_date}", footer_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Endpoints
@router.post("/letters/request")
async def create_letter_request(
    request: LetterRequest,
    current_user: dict = Depends(require_role("hr"))
):
    """Create a new letter request (HR only)"""
    try:
        # Calculate employment period
        employment_period = ""
        if request.joinDate:
            employment_period = calculate_employment_period(
                request.joinDate, 
                request.lastWorkingDay
            )
        
        # Create request document
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
            "status": "pending",
            "employmentPeriod": employment_period,
            "joinDate": request.joinDate,
        }
        
        # Add to Firestore
        doc_ref = db.collection('letter_requests').add(letter_data)
        letter_id = doc_ref[1].id
        
        return {
            "id": letter_id,
            "message": "Letter request submitted successfully",
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
    """Get pending letter requests (Directors only)"""
    try:
        requests = db.collection('letter_requests')\
            .where('status', '==', 'pending')\
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

@router.get("/letters/issued")
async def get_issued_letters(current_user: dict = Depends(require_role("hr", "director"))):
    """Get all approved/issued letters"""
    try:
        letters = db.collection('letter_requests')\
            .where('status', '==', 'approved')\
            .order_by('approvedOn', direction=firestore.Query.DESCENDING)\
            .stream()
        
        result = []
        for letter in letters:
            data = letter.to_dict()
            data['id'] = letter.id
            result.append(data)
        
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
            # Default behavior: download experience if available, else exit
            letter_type = 'experience' if request_letter_type in ['experience', 'both'] else 'exit'
        
        # Get file ID from letter data
        file_id_key = f"{letter_type}_file_id"
        file_id = letter_data.get(file_id_key)
        
        if not file_id:
            raise HTTPException(
                status_code=404, 
                detail=f"{letter_type.capitalize()} letter not found for this request"
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
