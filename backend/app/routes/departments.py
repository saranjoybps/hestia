from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user, supabase, require_role
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/departments", tags=["Departments"])


class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    head_id: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    head_id: Optional[str] = None


async def _department_to_public(row: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    head_id = row.get("head_id")
    head_name = None
    if head_id:
        head_user = user_map.get(str(head_id))
        if head_user:
            head_name = head_user.get("name")
            head_id = head_user.get("uid")

    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "description": row.get("description"),
        "head_id": head_id,
        "headName": head_name,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.post("/")
async def create_department(
    department: DepartmentCreate,
    current_user: dict = Depends(require_role("hr", "director")),
):
    try:
        existing = supabase.table("departments").select("id").eq("name", department.name).limit(1).execute()
        if existing.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department with this name already exists")

        head_internal_id = None
        if department.head_id:
            head_row = await SupabaseHelper.get_user_row_by_firebase_uid(department.head_id)
            if not head_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Head user not found")
            head_internal_id = str(head_row["id"])

        dept_data = {
            "name": department.name,
            "description": department.description,
            "head_id": head_internal_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = supabase.table("departments").insert(dept_data).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create department")

        user_map = await SupabaseHelper.get_public_user_map()
        dept_public = await _department_to_public(inserted, user_map)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="organization",
            action="department_created",
            description=f"{current_user.get('name', 'Someone')} created department \"{dept_public.get('name')}\".",
            result="success",
            target_type="department",
            target_id=dept_public["id"],
            metadata={
                "name": dept_public.get("name"),
                "head_id": dept_public.get("head_id"),
                "description": dept_public.get("description"),
            },
        )

        return dept_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating department: {str(e)}")


@router.get("/")
async def list_departments(current_user: dict = Depends(get_current_user)):
    try:
        dept_resp = supabase.table("departments").select("*").order("name").execute()
        departments_list = dept_resp.data or []

        users_resp = supabase.table("users").select("id, firebase_uid, name, department").execute()
        user_rows = users_resp.data or []
        user_map = await SupabaseHelper.get_public_user_map()

        dept_employee_counts: Dict[str, int] = {}
        for user in user_rows:
            dept_name = user.get("department")
            if dept_name:
                dept_employee_counts[dept_name] = dept_employee_counts.get(dept_name, 0) + 1

        public_departments = []
        for dept in departments_list:
            public_dept = await _department_to_public(dept, user_map)
            public_dept["employeeCount"] = dept_employee_counts.get(public_dept.get("name"), 0)
            public_departments.append(public_dept)

        return {"departments": public_departments}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching departments: {str(e)}")


@router.get("/{department_id}")
async def get_department(department_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = supabase.table("departments").select("*").eq("id", department_id).single().execute()
        dept_data = doc.data if doc.data else None
        if not dept_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        user_map = await SupabaseHelper.get_public_user_map()
        dept_public = await _department_to_public(dept_data, user_map)

        users_resp = supabase.table("users").select("*").execute()
        employees = []
        for user in users_resp.data or []:
            if user.get("department") == dept_public.get("name"):
                public_user = await SupabaseHelper.get_public_user_by_id(user.get("id"))
                if public_user:
                    employees.append(public_user)
        dept_public["employees"] = employees
        dept_public["employeeCount"] = len(employees)
        return dept_public
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching department: {str(e)}")


@router.put("/{department_id}")
async def update_department(
    department_id: str,
    department: DepartmentUpdate,
    current_user: dict = Depends(require_role("hr", "director")),
):
    try:
        existing_resp = supabase.table("departments").select("*").eq("id", department_id).execute()
        if not existing_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        if department.name:
            existing = supabase.table("departments").select("id").eq("name", department.name).limit(1).execute()
            for row in existing.data or []:
                if str(row.get("id")) != department_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department with this name already exists")

        update_data = {k: v for k, v in department.model_dump().items() if v is not None}
        if "head_id" in update_data and update_data["head_id"]:
            head_row = await SupabaseHelper.get_user_row_by_firebase_uid(update_data["head_id"])
            if not head_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Head user not found")
            update_data["head_id"] = str(head_row["id"])
        update_data["updated_at"] = datetime.utcnow().isoformat()

        response = supabase.table("departments").update(update_data).eq("id", department_id).execute()
        updated = response.data[0] if response.data else None
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update department")

        user_map = await SupabaseHelper.get_public_user_map()
        result = await _department_to_public(updated, user_map)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="organization",
            action="department_updated",
            description=f"{current_user.get('name', 'Someone')} updated department \"{result.get('name')}\".",
            result="success",
            target_type="department",
            target_id=department_id,
            metadata={"updated_fields": list(update_data.keys()), "name": result.get("name"), "head_id": result.get("head_id")},
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating department: {str(e)}")


@router.delete("/{department_id}")
async def delete_department(
    department_id: str,
    current_user: dict = Depends(require_role("hr", "director")),
):
    try:
        existing_resp = supabase.table("departments").select("*").eq("id", department_id).execute()
        if not existing_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        dept_data = existing_resp.data[0]
        supabase.table("departments").delete().eq("id", department_id).execute()

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="organization",
            action="department_deleted",
            description=f"{current_user.get('name', 'Someone')} deleted department \"{dept_data.get('name')}\".",
            result="success",
            target_type="department",
            target_id=department_id,
            metadata={"name": dept_data.get("name"), "head_id": dept_data.get("head_id")},
        )

        return {"message": "Department deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting department: {str(e)}")
