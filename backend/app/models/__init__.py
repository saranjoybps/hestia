from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field


# User Models
class UserBase(BaseModel):
    """Base user model"""
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
    status: Literal["active", "inactive"] = "active"


class UserCreate(UserBase):
    """User creation model"""
    password: str


class UserUpdate(BaseModel):
    """User update model"""
    name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[Literal["employee", "lead", "manager", "hr", "director"]] = None
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
    status: Literal["present", "absent", "half_day", "leave", "holiday"] = "present"
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
    status: Optional[Literal["present", "absent", "half_day", "leave", "holiday"]] = None
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
    totalDays: float
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


# Shift Models
class ShiftBase(BaseModel):
    """Base shift model"""
    employee_id: str
    shift_type: Literal["morning", "afternoon", "evening", "night", "rotating"] = "morning"
    shift_date: str  # Format: YYYY-MM-DD
    start_time: str  # Format: HH:MM
    end_time: str  # Format: HH:MM
    notes: Optional[str] = None


class ShiftCreate(ShiftBase):
    """Shift creation model"""
    pass


class ShiftUpdate(BaseModel):
    """Shift update model"""
    shift_type: Optional[Literal["morning", "afternoon", "evening", "night", "rotating"]] = None
    shift_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    rejection_reason: Optional[str] = None


class ShiftResponse(ShiftBase):
    """Shift response model"""
    id: str
    name: Optional[str] = None
    status: Literal["pending", "approved", "rejected"]
    created_by: str
    created_by_name: Optional[str] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


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
