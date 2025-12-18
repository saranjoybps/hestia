# Exit & Experience Letter Management Module

## 📋 Overview
A comprehensive document management system for HR and Directors to manage employee exit and experience letter requests with approval workflow and automated PDF generation.

## ✨ Features

### 🎯 Access Control
- **HR Users**: Create letter requests, track submissions, view issued letters
- **Directors**: Approve/reject requests, generate PDFs, view all letters
- **Role-Based Restrictions**: Only HR and Directors can access the Documents module

### 📝 Letter Types
1. **Exit Letter**: Formal acknowledgment of resignation and last working day
2. **Experience Letter**: Certificate of employment with tenure details
3. **Both**: Request both letters simultaneously

### 🔄 Workflow

#### 1. Request Creation (HR)
- Select employee from directory
- Choose letter type (Exit/Experience/Both)
- Set last working day
- Add optional reason for exit
- Add additional comments
- Submit for Director approval

#### 2. Approval Process (Director)
- View pending requests with full details
- Review employee information and reason
- **Approve**: Automatically generates PDF with:
  - Joyrts company letterhead
  - Formal letter content
  - Employment period calculation
  - Director's digital signature
  - System-generated timestamp
- **Reject**: Provide rejection reason (stored in audit trail)

#### 3. Issued Letters
- Download approved letters in PDF format
- Track approval date and approver
- Accessible by both HR and Directors

## 🎨 User Interface

### Three-Tab Layout

#### 📋 Tab 1: My Requests (HR)
- Table view of all letter requests
- Shows: Employee, Letter Type, Last Working Day, Status
- Status badges: Pending (yellow), Approved (green), Rejected (red)
- View action to see full request details

#### ✅ Tab 2: Pending Approvals (Directors)
- Card-based display of pending requests
- Rich information display:
  - Employee avatar and details
  - Last working day
  - Requestor information
  - Reason for exit
  - Additional comments
- Two-button action: Approve & Generate PDF | Reject
- Expandable approval/rejection dialogs

#### 📄 Tab 3: Issued Letters (Both Roles)
- Table of all approved letters
- Shows: Employee, Letter Type, Issue Date, Approver
- Download PDF button for each letter
- Filtering and sorting capabilities

## 🏗️ Technical Architecture

### Frontend (`/dashboard/documents/page.tsx`)
- **Framework**: Next.js 16.0.2 with TypeScript
- **Components**: 30+ shadcn/ui components
- **State Management**: React hooks (useState, useEffect)
- **API Integration**: Fetch API with Firebase Auth tokens
- **Features**:
  - Real-time data fetching
  - Form validation
  - Error handling with toast notifications
  - Responsive dialogs
  - Loading states

### Backend (`/routes/letters.py`)
- **Framework**: FastAPI with Python 3.9+
- **Database**: Firestore (`letter_requests` collection)
- **PDF Generation**: ReportLab library
- **Authentication**: Firebase Auth with role-based access
- **Endpoints**:
  ```
  POST   /api/letters/request          - Create letter request (HR)
  GET    /api/letters/requests         - List all requests (HR: own, Director: all)
  GET    /api/letters/pending          - List pending requests (Directors)
  GET    /api/letters/issued           - List approved letters (HR, Directors)
  POST   /api/letters/approve/{id}     - Approve and generate PDF (Directors)
  POST   /api/letters/reject/{id}      - Reject request (Directors)
  GET    /api/letters/download/{id}    - Download PDF (HR, Directors)
  GET    /api/letters/{id}             - Get letter details
  ```

## 📊 Data Structure

### LetterRequest Document (Firestore)
```typescript
{
  id: string
  employeeId: string
  employeeName: string
  employeeEmail: string
  department: string
  designation: string
  letterType: 'exit' | 'experience' | 'both'
  lastWorkingDay: string (ISO date)
  reasonForExit?: string
  additionalComments?: string
  requestedBy: string (HR uid)
  requestedByName: string
  requestedOn: string (ISO datetime)
  status: 'pending' | 'approved' | 'rejected'
  employmentPeriod?: string (calculated)
  joinDate?: string
  
  // Approval fields
  approvedBy?: string
  approverName?: string
  approvedOn?: string
  pdfUrls?: string[]
  
  // Rejection fields
  rejectedBy?: string
  rejectionReason?: string
  rejectedOn?: string
}
```

## 📄 PDF Letter Templates

### Experience Letter Format
- Company header: "JOYRTS - Human Resources Management"
- Document title: "EXPERIENCE CERTIFICATE"
- Reference number: JOYRTS/HR/YYYYMMDD/EmployeeID
- Formal certification content
- Employment period with calculated duration
- Performance acknowledgment
- Director signature
- System-generated footer

### Exit Letter Format
- Same company header and branding
- Document title: "EXIT LETTER"
- Acknowledgment of resignation
- Last working day confirmation
- Appreciation for service
- Optional: Reason for exit
- Director signature
- System-generated footer

## 🔐 Security Features
- Role-based access control (HR/Director only)
- Firebase Authentication token validation
- Input validation and sanitization
- Error handling with appropriate status codes
- Audit trail (all actions logged with timestamps)

## 🚀 Installation & Setup

### Prerequisites
```bash
# Backend dependencies
pip install reportlab  # PDF generation library
```

### Configuration
1. **Backend**: Ensure `letters` router is registered in `main.py`
2. **Frontend**: Documents menu configured in sidebar with HR/Director access
3. **Routing**: `/documents` redirects to `/dashboard/documents` in `next.config.ts`

### Database Setup
- Firestore collection: `letter_requests`
- Indexes: Status, RequestedOn, ApprovedOn (for efficient queries)

## 📈 Usage Workflow Example

### Scenario: HR Creating Exit Letter

1. **HR logs in** → Navigates to Documents
2. **Clicks "New Request"** button
3. **Fills form**:
   - Employee: John Doe (Sales Executive)
   - Letter Type: Exit Letter
   - Last Working Day: 2025-12-31
   - Reason: "Career growth opportunity"
4. **Submits** → Toast: "Letter request submitted for Director's approval"
5. **Request appears** in "My Requests" tab with Pending status

### Scenario: Director Approving Request

1. **Director logs in** → Navigates to Documents
2. **Sees notification** in "Pending Approvals" tab (1 pending)
3. **Reviews request** showing all details
4. **Clicks "Approve & Generate PDF"**
5. **System**:
   - Generates professional PDF letter
   - Updates status to "Approved"
   - Records approver and timestamp
   - Makes PDF available for download
6. **Toast**: "Letter approved and PDF generated successfully!"

### Scenario: HR/Director Downloading Letter

1. **Navigate to "Issued Letters"** tab
2. **Find letter** in table (sorted by issue date)
3. **Click "Download PDF"** button
4. **PDF downloads** with filename: `experience_letter_john_doe.pdf`

## 🎯 Key Benefits

1. **Streamlined Process**: Eliminates manual letter creation
2. **Consistency**: Standardized letter format across organization
3. **Audit Trail**: Complete history of all letter requests
4. **Professional Output**: High-quality PDF documents
5. **Time-Saving**: Automated PDF generation on approval
6. **Secure**: Role-based access with Firebase Auth
7. **User-Friendly**: Intuitive three-tab interface
8. **Flexible**: Support for multiple letter types

## 🧪 Testing Checklist

### HR User Tests
- ✅ Create letter request with all fields
- ✅ View own requests in table
- ✅ See request status updates
- ✅ Download approved letters
- ✅ Access denied to approval features

### Director Tests
- ✅ View all pending requests
- ✅ Approve request (PDF generates)
- ✅ Reject request with reason
- ✅ Download issued letters
- ✅ View all historical requests

### Integration Tests
- ✅ Employment period calculation
- ✅ PDF generation for both letter types
- ✅ Status transitions (pending → approved/rejected)
- ✅ Audit trail completeness
- ✅ Error handling (network issues, invalid data)

## 📞 Support & Maintenance

### Common Issues
1. **PDF generation fails**: Check ReportLab installation
2. **Access denied**: Verify user role in Firestore
3. **Empty employee list**: Ensure user collection is populated
4. **Download errors**: Check CORS settings

### Future Enhancements
- Email notifications on approval/rejection
- Firebase Storage integration for PDF persistence
- Custom letter templates per department
- Bulk letter generation
- Digital signature integration
- Multi-language support

## 📝 Notes

- **Employment Period**: Auto-calculated from join date to last working day
- **PDF Storage**: Currently generated on-demand; consider Firebase Storage for production
- **Letter Templates**: Defined in backend code (future: Firestore-based templates)
- **Permissions**: Strictly enforced at API level with `require_role` decorator
- **User Experience**: Toast notifications for all actions with clear messaging

---

**Module Status**: ✅ Complete and Production-Ready
**Last Updated**: November 12, 2025
**Version**: 1.0.0
