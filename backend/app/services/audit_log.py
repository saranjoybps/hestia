from datetime import datetime
from typing import Optional, Any
from app.dependencies import db


def log_audit_event(
    *,
    actor_id: str,
    actor_name: Optional[str],
    actor_email: Optional[str],
    action: str,
    description: Optional[str] = None,
    result: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None
) -> tuple[str, dict[str, Any]]:
    """Create an audit log entry and return (id, document)."""
    audit_doc: dict[str, Any] = {
        "actor_id": actor_id,
        "actor_name": actor_name,
        "actor_email": actor_email,
        "action": action,
        "description": description,
        "result": result,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata,
        "created_at": datetime.utcnow().isoformat()
    }

    doc_ref = db.collection("audit_logs").document()
    doc_ref.set(audit_doc)
    return doc_ref.id, audit_doc
