from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import db, get_current_user, require_role
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/departments", tags=["Departments"])


class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    head_id: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    head_id: Optional[str] = None


@router.post("/")
async def create_department(
    department: DepartmentCreate,
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Create a new department"""
    try:
        # Check if department already exists
        existing = db.collection('departments').where('name', '==', department.name).limit(1).stream()
        if any(existing):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department with this name already exists"
            )
        
        dept_data = department.dict()
        dept_data['created_at'] = datetime.utcnow().isoformat()
        dept_data['updated_at'] = datetime.utcnow().isoformat()
        
        doc_ref = db.collection('departments').document()
        doc_ref.set(dept_data)
        
        return {
            "id": doc_ref.id,
            **dept_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating department: {str(e)}"
        )


@router.get("/")
async def list_departments(
    current_user: dict = Depends(get_current_user)
):
    """Get all departments - optimized to reduce database queries"""
    try:
        # Fetch all departments
        docs = db.collection('departments').stream()
        departments_list = []
        
        for doc in docs:
            dept_data = doc.to_dict()
            dept_data['id'] = doc.id
            departments_list.append(dept_data)
        
        # Fetch all users in one query
        all_users = {}
        users_query = db.collection('users').stream()
        dept_employee_counts = {}
        
        for user in users_query:
            user_data = user.to_dict()
            user_id = user.id
            all_users[user_id] = user_data
            
            # Count employees per department
            dept_name = user_data.get('department')
            if dept_name:
                dept_employee_counts[dept_name] = dept_employee_counts.get(dept_name, 0) + 1
        
        # Enrich departments with head names and employee counts
        for dept in departments_list:
            # Get head name from cached users
            if dept.get('head_id') and dept['head_id'] in all_users:
                dept['headName'] = all_users[dept['head_id']].get('name', 'Unknown')
            
            # Get employee count from aggregated counts
            dept['employeeCount'] = dept_employee_counts.get(dept['name'], 0)
        
        return {
            "departments": departments_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching departments: {str(e)}"
        )


@router.get("/{department_id}")
async def get_department(
    department_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single department"""
    try:
        doc = db.collection('departments').document(department_id).get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        dept_data = doc.to_dict()
        dept_data['id'] = doc.id
        
        # Get head name if head_id exists
        if dept_data.get('head_id'):
            head_doc = db.collection('users').document(dept_data['head_id']).get()
            if head_doc.exists:
                dept_data['headName'] = head_doc.to_dict().get('name', 'Unknown')
        
        # Get employees in this department
        employees_docs = db.collection('users').where('department', '==', dept_data['name']).stream()
        employees = []
        for emp_doc in employees_docs:
            emp_data = emp_doc.to_dict()
            emp_data['uid'] = emp_doc.id
            employees.append(emp_data)
        
        dept_data['employees'] = employees
        dept_data['employeeCount'] = len(employees)
        
        return dept_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching department: {str(e)}"
        )


@router.put("/{department_id}")
async def update_department(
    department_id: str,
    department: DepartmentUpdate,
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Update a department"""
    try:
        doc_ref = db.collection('departments').document(department_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        # Check if new name conflicts with existing department
        if department.name:
            existing = db.collection('departments')\
                .where('name', '==', department.name)\
                .limit(1)\
                .stream()
            
            for existing_doc in existing:
                if existing_doc.id != department_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Department with this name already exists"
                    )
        
        # Update only provided fields
        update_data = {k: v for k, v in department.dict().items() if v is not None}
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        doc_ref.update(update_data)
        
        # Get updated document
        updated_doc = doc_ref.get()
        result = updated_doc.to_dict()
        result['id'] = department_id
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating department: {str(e)}"
        )


@router.delete("/{department_id}")
async def delete_department(
    department_id: str,
    current_user: dict = Depends(require_role("director"))
):
    """Delete a department - Directors only"""
    try:
        doc_ref = db.collection('departments').document(department_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        dept_data = doc.to_dict()
        
        # Check if department has employees
        employees = db.collection('users').where('department', '==', dept_data['name']).limit(1).stream()
        if any(employees):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete department with existing employees. Please reassign them first."
            )
        
        doc_ref.delete()
        
        return {"message": "Department deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting department: {str(e)}"
        )
