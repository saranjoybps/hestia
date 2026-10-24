from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, require_role, supabase
from app.models import AuditLogCreate, AuditLogResponse
from app.services.audit_log import log_audit_event

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.post("", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    payload: AuditLogCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        doc_id, audit_doc = log_audit_event(
            actor_id=current_user.get("id") or current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module=payload.module,
            action=payload.action,
            description=payload.description,
            result=payload.result,
            target_type=payload.target_type,
            target_id=payload.target_id,
            metadata=payload.metadata,
        )

        response_doc = audit_doc.copy()
        response_doc["id"] = doc_id
        return AuditLogResponse(**response_doc)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating audit log: {str(e)}")


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(require_role("hr", "director", "super_admin")),
):
    try:
        query = supabase.table("audit_logs").select("*")
        if actor_id:
            query = query.eq("actor_id", actor_id)
        if action:
            query = query.eq("action", action)
        if result:
            query = query.eq("result", result)
        if target_type:
            query = query.eq("target_type", target_type)
        if target_id:
            query = query.eq("target_id", target_id)
        if from_date:
            query = query.gte("created_at", from_date)
        if to_date:
            query = query.lte("created_at", to_date)

        response = query.order("created_at", desc=True).execute()
        rows = response.data or []
        offset = (page - 1) * limit
        paginated = rows[offset : offset + limit]
        return [AuditLogResponse(**row) for row in paginated]

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching audit logs: {str(e)}")
