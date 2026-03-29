from fastapi import APIRouter, Depends, HTTPException, Query, status
from firebase_admin import firestore
from typing import Optional
from app.dependencies import db, get_current_user, require_role
from app.models import AuditLogCreate, AuditLogResponse
from app.services.audit_log import log_audit_event

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.post("", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    payload: AuditLogCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create an audit log entry."""
    try:
        doc_id, audit_doc = log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module=payload.module,
            action=payload.action,
            description=payload.description,
            result=payload.result,
            target_type=payload.target_type,
            target_id=payload.target_id,
            metadata=payload.metadata
        )

        response_doc = audit_doc.copy()
        response_doc["id"] = doc_id
        return AuditLogResponse(**response_doc)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating audit log: {str(e)}"
        )


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
    current_user: dict = Depends(require_role("hr", "director"))
):
    """List audit logs with optional filters."""
    try:
        query = db.collection("audit_logs")

        if actor_id:
            query = query.where("actor_id", "==", actor_id)
        if action:
            query = query.where("action", "==", action)
        if result:
            query = query.where("result", "==", result)
        if target_type:
            query = query.where("target_type", "==", target_type)
        if target_id:
            query = query.where("target_id", "==", target_id)
        if from_date:
            query = query.where("created_at", ">=", from_date)
        if to_date:
            query = query.where("created_at", "<=", to_date)

        # Order by created_at (required when using range filters)
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)

        offset = (page - 1) * limit
        paginated_query = query.limit(limit).offset(offset)

        results: list[AuditLogResponse] = []
        for doc in paginated_query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(AuditLogResponse(**data))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching audit logs: {str(e)}"
        )
