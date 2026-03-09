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
    
    ref_number = letter_data.get('referenceNumber', f"JOYRTS/HR/{datetime.now().strftime('%Y%m%d')}/{letter_data['employeeId']}")
    story.append(Paragraph(f"Ref: {ref_number}", right_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Letter Title and Content based on type
    if letter_type == 'offer':
        # Offer Letter
        letter_title = "OFFER OF EMPLOYMENT"
        story.append(Paragraph(letter_title, heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(f"{letter_data['employeeName']},", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("Congratulations!", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        start_date_formatted = datetime.fromisoformat(letter_data['startDate'].replace('Z', '+00:00')).strftime('%B %d, %Y')
        intro = f"""
        We are pleased to appoint you as <b>{letter_data['designation']}</b>, with effect from <b>{start_date_formatted}</b>, on the following terms and conditions:
        """
        story.append(Paragraph(intro, normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Terms and conditions
        probation = letter_data.get('probationPeriod', 'three months')
        notice = letter_data.get('noticePeriod', '45 days')
        
        terms = [
            f"1. You will be on probation for a period of <b>{probation}</b> from <b>{start_date_formatted}</b> and shall be confirmed after the said period subject to your meeting our performance standards.",
            f"2. Your total emoluments per annum including shift allowance and other related allowances would be <b>₹{letter_data['annualSalary']}</b>.",
            "3. Your salary is strictly confidential and we expect that you maintain the confidentiality of the same. We reiterate that your pay scale is a confidential matter between you and the Company and we reaffirm that the Company shall view any breach of confidentiality with utmost seriousness.",
            "4. You shall be responsible for all the activities related to responsibilities assigned to you and shall achieve all the targets set for you periodically.",
            "5. Your continuation in the organization shall be based purely on your performance and adhering to the organization's policies and procedures. You shall maintain proper discipline and dignity of your office and shall deal with all matters with sobriety.",
            "6. You will not engage in any other business or service or any other occupation either professional or honorary, or part time, during your period of employment with us.",
            "7. You will be representing the organization purely in connection with soliciting business from potential clients and will not indulge in any activity that would be harmful to the interests of the organization.",
            "8. You will not be eligible for any leave during the probation period else it consider as LOP.",
            "9. Should you remain absent from work, without reasonable explanation, for more than seven (7) consecutive days, it will be presumed that you are no longer interested in working and have abandoned its services, thereby terminating your contract of service. In such case, you will be required to return any company asset or property that you have been provided with at the time of your employment.",
            "10. During the employment period JOY RESEARCH AND TECHNOLOGY SERVICES PRIVATE LIMITED as an employer is at will to end the employment relationship at any time, with or without notice or cause for unsatisfactory performance.",
            f"11. The notice period after probation will be <b>{notice}</b> notice on the employee's side. You are not allowed to take leaves during notice period, if availed leave the notice period will be extended.",
            "12. You will be provided with complete training and stationary support from the organization as and when required.",
            "13. During the period of this appointment, you will not secure any other post without the previous consent of the management in writing.",
            "14. Your appointment will be subject to the verification of your service record and identification.",
            "15. You will observe working timings and holidays as applicable to customer's location and customer's place of work.",
            "16. You will forthwith inform the concern person in the organization of any change in your residential address.",
            "17. As a condition of your employment, you will be required to agree to Non-Compete with the Company. The purpose of this non-compete agreement is to protect the Company's legitimate business interests, including but not limited to its confidential information, trade secrets, client relationships, and intellectual property.",
        ]
        
        for term in terms:
            story.append(Paragraph(term, normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        story.append(Spacer(1, 0.2*inch))
        
        # Code of Conduct
        story.append(Paragraph("<b>Code of Conduct:</b>", normal_style))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("The work rules and code of conduct are very important, and the Company regards them seriously. All Employees are expected to follow these rules and maintain proper discipline, punctuality, ethical conduct, and professionalism at all times.", normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Closing
        story.append(Paragraph("You are requested to sign the duplicate and provide us the same in acceptance of the above offer.", normal_style))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Wishing you the very best and looking forward to a mutually beneficial relationship.", normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Signature section
        story.append(Paragraph("For JOY RESEARCH AND TECHNOLOGY SERVICES PRIVATE LIMITED,", normal_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"<b>{letter_data['approverName']}</b>", normal_style))
        story.append(Paragraph("Director", normal_style))
        story.append(Spacer(1, 0.5*inch))
        
        # Declaration section
        story.append(Paragraph("<b>Declaration:</b>", normal_style))
        story.append(Paragraph("I have read and understood the terms and conditions stated above and hereby signify my acceptance of the same.", normal_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("_______________________", normal_style))
        story.append(Paragraph("Employee's Signature", normal_style))
        
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
                
                # Update request with file info
                db.collection('letter_requests').document(letter_id).update({
                    'experience_letter_link': exp_file['web_view_link'],
                    'experience_file_id': exp_file['file_id'],
                    'exit_letter_link': exit_file['web_view_link'],
                    'exit_file_id': exit_file['file_id'],
                    'pdfFiles': [
                        {
                            'type': 'experience',
                            'filename': f"{request.employeeName.replace(' ', '_')}_experience_certificate.pdf",
                            'file_id': exp_file['file_id'],
                            'web_view_link': exp_file['web_view_link']
                        },
                        {
                            'type': 'exit',
                            'filename': f"{request.employeeName.replace(' ', '_')}_exit_letter.pdf",
                            'file_id': exit_file['file_id'],
                            'web_view_link': exit_file['web_view_link']
                        }
                    ]
                })
            else:
                # Generate single letter
                pdf_buffer = generate_letter_pdf(letter_data, request.letterType)
                
                letter_type_name = 'offer_letter' if request.letterType == 'offer' else f'{request.letterType}_letter'
                filename = f"{request.employeeName.replace(' ', '_')}_{letter_type_name}.pdf"
                
                # Upload to Google Drive
                file_info = drive_service.upload_pdf(pdf_buffer, filename)
                
                # Update request with file info
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
