from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, model_validator


# User Models
class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: Literal["employee", "lead", "manager", "hr", "director", "super_admin"] = "employee"
    department: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[str] = None
    manager_id: Optional[str] = None
    lead_id: Optional[str] = None
    status: Literal["active", "inactive"] = "active"


class UserCreate(UserBase):
    """User creation model"""
    password: str


class UserUpdate(BaseModel):
    """User update model"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    role: Optional[Literal["employee", "lead", "manager", "hr", "director", "super_admin"]] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[str] = None
    manager_id: Optional[str] = None
    lead_id: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None


class UserResponse(UserBase):
    """User response model"""
    uid: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Department Models
class DepartmentBase(BaseModel):
    """Base department model"""
    name: str
    description: Optional[str] = None
    head_id: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    """Department creation model"""
    pass


class DepartmentResponse(DepartmentBase):
    """Department response model"""
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Attendance Models
class AttendanceBase(BaseModel):
    """Base attendance model"""
    user_id: str
    date: str  # Format: YYYY-MM-DD
    check_in: Optional[str] = None  # Format: HH:MM
    check_out: Optional[str] = None
    total_hours: Optional[float] = 0.0
    status: Literal["present", "absent", "half_day", "leave", "holiday", "week_off", "comp_off"] = "present"
    is_week_off: bool = False
    is_comp_off: bool = False
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    """Attendance creation model"""
    marked_by: str


class AttendanceUpdate(BaseModel):
    """Attendance update model"""
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    total_hours: Optional[float] = None
    status: Optional[Literal["present", "absent", "half_day", "leave", "holiday", "week_off", "comp_off"]] = None
    is_week_off: Optional[bool] = None
    is_comp_off: Optional[bool] = None
    notes: Optional[str] = None
    corrected_by: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    """Attendance response model"""
    id: str
    marked_by: str
    corrected_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Leave Models
class LeaveBase(BaseModel):
    """Base leave model"""
    userId: str
    leaveType: Literal["casual", "sick", "annual", "unpaid", "maternity", "paternity", "comp-off"]
    startDate: str
    endDate: str
    totalDays: float = 0
    reason: str


class LeaveCreate(LeaveBase):
    """Leave creation model"""
    cc: Optional[EmailStr] = None


class LeaveUpdate(BaseModel):
    """Leave update model"""
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    approvedBy: Optional[str] = None
    rejectionReason: Optional[str] = None


class LeaveResponse(BaseModel):
    """Leave response model"""
    id: str
    userId: str
    userName: Optional[str] = None
    userEmail: Optional[str] = None
    leaveType: str
    startDate: str
    endDate: str
    totalDays: float
    reason: str
    status: str
    approvedBy: Optional[str] = None
    approverName: Optional[str] = None
    rejectionReason: Optional[str] = None
    appliedDate: str
    approvalDate: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    
    class Config:
        from_attributes = True


# Task Models
class TaskBase(BaseModel):
    """Base task model"""
    title: str
    description: Optional[str] = ""
    assigneeId: str
    assigneeName: str
    assigneeEmail: str
    dueDate: Optional[str] = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["todo", "in_progress", "review", "completed"] = "todo"
    attachments: list[str] = []


class TaskCreate(TaskBase):
    """Task creation model"""
    createdBy: str
    createdByName: str


class TaskUpdate(BaseModel):
    """Task update model"""
    title: Optional[str] = None
    description: Optional[str] = None
    assigneeId: Optional[str] = None
    assigneeName: Optional[str] = None
    assigneeEmail: Optional[str] = None
    dueDate: Optional[str] = None
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = None
    status: Optional[Literal["todo", "in_progress", "review", "completed"]] = None
    attachments: Optional[list[str]] = None


class TaskResponse(BaseModel):
    """Task response model"""
    id: str
    title: str
    description: str
    assigneeId: str
    assigneeName: str
    assigneeEmail: str
    createdBy: str
    createdByName: str
    dueDate: Optional[str] = None
    priority: str
    status: str
    attachments: list[str]
    createdAt: str
    updatedAt: Optional[str] = None
    
    class Config:
        from_attributes = True


# Performance Models
class PerformanceReviewBase(BaseModel):
    """Base performance review model"""
    userId: str
    userName: str
    userEmail: str
    reviewerId: str
    reviewerName: str
    reviewerRole: str
    reviewType: Literal["positive", "negative"]
    rating: int = Field(ge=1, le=5)
    context: str
    reviewDate: str
    department: Optional[str] = None
    designation: Optional[str] = None


class PerformanceReviewCreate(PerformanceReviewBase):
    """Performance review creation model"""
    pass


class PerformanceReviewUpdate(BaseModel):
    """Performance review update model"""
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    approvedBy: Optional[str] = None
    approverName: Optional[str] = None


class PerformanceReviewResponse(PerformanceReviewBase):
    """Performance review response model"""
    id: str
    status: Literal["pending", "approved", "rejected"]
    approvedBy: Optional[str] = None
    approverName: Optional[str] = None
    approvalDate: Optional[str] = None
    createdAt: str
    updatedAt: Optional[str] = None
    
    class Config:
        from_attributes = True


# Announcement Models
class AnnouncementBase(BaseModel):
    """Base announcement model"""
    title: str
    description: str
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    targetAudience: list[str] = []
    expiryDate: Optional[str] = None
    status: Literal["draft", "published"] = "draft"
    isPinned: bool = False


class AnnouncementCreate(AnnouncementBase):
    """Announcement creation model"""
    createdBy: str
    createdByName: str


class AnnouncementUpdate(BaseModel):
    """Announcement update model"""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = None
    targetAudience: Optional[list[str]] = None
    expiryDate: Optional[str] = None
    status: Optional[Literal["draft", "published"]] = None
    isPinned: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    """Announcement response model"""
    id: str
    title: str
    description: str
    priority: str
    targetAudience: list[str]
    expiryDate: Optional[str] = None
    status: str
    isPinned: bool
    createdBy: str
    createdByName: str
    createdAt: str
    updatedAt: Optional[str] = None
    
    class Config:
        from_attributes = True


# Employee Onboarding Request Models
class OnboardingRequestCreate(BaseModel):
    """Create employee onboarding request"""
    email: EmailStr
    name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: Literal["employee", "lead", "manager", "hr", "director"] = "employee"
    department: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[str] = None
    manager_id: Optional[str] = None
    lead_id: Optional[str] = None
    notes: Optional[str] = None


class OnboardingRequestUpdate(BaseModel):
    """Update onboarding request"""
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    rejection_reason: Optional[str] = None


class OnboardingRequestResponse(BaseModel):
    """Onboarding request response"""
    id: str
    email: EmailStr
    name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    department: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[str] = None
    manager_id: Optional[str] = None
    lead_id: Optional[str] = None
    notes: Optional[str] = None
    status: Literal["pending", "approved", "rejected"]
    requested_by: str
    requested_by_name: str
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Shift templates and employee allocations
class ShiftTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_shift_times(self):
        if self.start_time == self.end_time:
            raise ValueError("Start and end times must be different")
        return self


class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    start_time: Optional[str] = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: Optional[str] = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_shift_times(self):
        if self.start_time is not None and self.end_time is not None and self.start_time == self.end_time:
            raise ValueError("Start and end times must be different")
        return self


class ShiftAllocationCreate(BaseModel):
    employee_id: str = Field(min_length=1)
    shift_template_id: str = Field(min_length=1)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ShiftAllocationUpdate(BaseModel):
    employee_id: Optional[str] = Field(default=None, min_length=1)
    shift_template_id: Optional[str] = Field(default=None, min_length=1)
    notes: Optional[str] = Field(default=None, max_length=1000)


# Candidate recruitment models
class CandidateCreate(BaseModel):
    firstName: str = Field(min_length=1, max_length=100)
    lastName: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=40)
    department: Optional[str] = Field(default=None, max_length=120)
    designation: str = Field(min_length=1, max_length=120)
    source: Optional[str] = Field(default=None, max_length=80)
    currentCompany: Optional[str] = Field(default=None, max_length=160)
    currentDesignation: Optional[str] = Field(default=None, max_length=120)
    experienceYears: Optional[float] = Field(default=None, ge=0, le=80)
    noticePeriodDays: Optional[int] = Field(default=None, ge=0, le=730)
    expectedSalary: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = Field(default=None, max_length=160)


class CandidateUpdate(BaseModel):
    firstName: Optional[str] = Field(default=None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    department: Optional[str] = Field(default=None, max_length=120)
    designation: Optional[str] = Field(default=None, min_length=1, max_length=120)
    source: Optional[str] = Field(default=None, max_length=80)
    currentCompany: Optional[str] = Field(default=None, max_length=160)
    currentDesignation: Optional[str] = Field(default=None, max_length=120)
    experienceYears: Optional[float] = Field(default=None, ge=0, le=80)
    noticePeriodDays: Optional[int] = Field(default=None, ge=0, le=730)
    expectedSalary: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = Field(default=None, max_length=160)
    status: Optional[Literal["new", "screening", "shortlisted", "interview_scheduled", "interview_completed", "selected", "offer_sent", "rejected", "withdrawn"]] = None


class CandidateActivityCreate(BaseModel):
    type: Literal["note", "interview", "meeting"]
    title: str = Field(min_length=2, max_length=160)
    body: Optional[str] = Field(default=None, max_length=10000)
    startsAt: Optional[datetime] = None
    endsAt: Optional[datetime] = None
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    meetingUrl: Optional[str] = Field(default=None, max_length=1000)
    location: Optional[str] = Field(default=None, max_length=240)
    interviewerIds: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_scheduled_activity(self):
        if self.type in {"interview", "meeting"}:
            if not self.startsAt or not self.endsAt:
                raise ValueError("Scheduled interviews and meetings need a start and end time")
            if self.endsAt <= self.startsAt:
                raise ValueError("The end time must be after the start time")
        if self.type == "interview" and not self.interviewerIds:
            raise ValueError("Assign at least one interviewer")
        return self


class CandidateActivityUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=160)
    body: Optional[str] = Field(default=None, max_length=10000)
    startsAt: Optional[datetime] = None
    endsAt: Optional[datetime] = None
    timezone: Optional[str] = Field(default=None, max_length=80)
    meetingUrl: Optional[str] = Field(default=None, max_length=1000)
    location: Optional[str] = Field(default=None, max_length=240)
    status: Optional[Literal["scheduled", "completed", "cancelled"]] = None
    interviewerIds: Optional[list[str]] = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_activity_times(self):
        if self.startsAt and self.endsAt and self.endsAt <= self.startsAt:
            raise ValueError("The end time must be after the start time")
        return self


class CandidateConversion(BaseModel):
    department: str = Field(min_length=1, max_length=120)
    designation: str = Field(min_length=1, max_length=120)
    role: Literal["employee", "lead", "manager", "hr", "director"] = "employee"
    managerId: Optional[str] = None
    dateOfJoining: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_reporting_person(self):
        if self.role in {"employee", "lead", "manager"} and not self.managerId:
            raise ValueError("Choose a reporting manager for this employee role")
        if self.role == "director" and self.managerId:
            raise ValueError("Directors cannot have a reporting manager")
        return self


# Asset inventory and custody models
class AssetCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    requiresReturn: bool = True


class AssetCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    requiresReturn: Optional[bool] = None
    active: Optional[bool] = None


class AssetCatalogCreate(BaseModel):
    categoryId: str = Field(min_length=1)
    name: str = Field(min_length=2, max_length=160)
    manufacturer: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=120)
    trackingMode: Literal["serialized", "bulk"] = "serialized"
    notes: Optional[str] = Field(default=None, max_length=1000)


class AssetCatalogUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    manufacturer: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=1000)
    active: Optional[bool] = None


class AssetItemCreate(BaseModel):
    catalogId: str = Field(min_length=1)
    assetTag: str = Field(min_length=2, max_length=100)
    serialNumber: Optional[str] = Field(default=None, max_length=160)
    department: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=160)
    purchaseDate: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    purchaseCost: Optional[float] = Field(default=None, ge=0)
    warrantyExpiresAt: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    condition: Literal["new", "good", "fair", "damaged"] = "new"
    notes: Optional[str] = Field(default=None, max_length=2000)


class AssetItemUpdate(BaseModel):
    department: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=160)
    condition: Optional[Literal["new", "good", "fair", "damaged"]] = None
    status: Optional[Literal["maintenance", "lost", "retired"]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class AssetStockReceive(BaseModel):
    catalogId: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=100000)
    reference: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=1000)


class AssetIssueLine(BaseModel):
    employeeId: str = Field(min_length=1)
    catalogId: str = Field(min_length=1)
    assetItemId: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=10000)


class AssetIssueBatch(BaseModel):
    lines: list[AssetIssueLine] = Field(min_length=1, max_length=200)
    issueDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    dueDate: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: Optional[str] = Field(default=None, max_length=2000)
    requestId: Optional[str] = None

    @model_validator(mode="after")
    def validate_issue_dates(self):
        if self.dueDate and self.dueDate < self.issueDate:
            raise ValueError("Due date cannot be earlier than the issue date")
        return self


class AssetRequestLine(BaseModel):
    catalogId: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=10000)
    notes: Optional[str] = Field(default=None, max_length=500)


class AssetRequestCreate(BaseModel):
    employeeId: Optional[str] = None
    lines: list[AssetRequestLine] = Field(min_length=1, max_length=50)
    reason: Optional[str] = Field(default=None, max_length=2000)


class AssetRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    decisionNote: Optional[str] = Field(default=None, max_length=1000)


class AssetReturnRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


class AssetReturnComplete(BaseModel):
    quantity: int = Field(ge=1, le=10000)
    condition: Literal["new", "good", "fair", "damaged", "lost"] = "good"
    notes: Optional[str] = Field(default=None, max_length=1000)


# Permission Models
class PermissionBase(BaseModel):
    """Base permission model"""
    role: str
    permissions: list[str]


class PermissionResponse(PermissionBase):
    """Permission response model"""
    id: str
    
    class Config:
        from_attributes = True


# Audit Log Models
class AuditLogBase(BaseModel):
    """Base audit log model"""
    actor_id: str
    actor_name: Optional[str] = None
    actor_email: Optional[EmailStr] = None
    module: Optional[str] = None
    action: str
    description: Optional[str] = None
    result: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    metadata: Optional[dict] = None


class AuditLogCreate(BaseModel):
    """Audit log creation model"""
    module: Optional[str] = None
    action: str
    description: Optional[str] = None
    result: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    metadata: Optional[dict] = None


class AuditLogResponse(AuditLogBase):
    """Audit log response model"""
    id: str
    created_at: str
    
    class Config:
        from_attributes = True
