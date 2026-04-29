import threading
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from app.dependencies import supabase


def log_audit_event(
    *,
    actor_id: str,
    actor_name: Optional[str],
    actor_email: Optional[str],
    module: Optional[str],
    action: str,
    description: Optional[str] = None,
    result: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None
) -> tuple[str, dict[str, Any]]:
    """Create an audit log entry asynchronously."""
    resolved_actor_id = actor_id
    try:
        lookup = supabase.table("users").select("id").eq("firebase_uid", actor_id).execute()
        if lookup.data and lookup.data[0].get("id"):
            resolved_actor_id = str(lookup.data[0]["id"])
    except Exception:
        pass

    doc_id = str(uuid4())
    audit_doc: dict[str, Any] = {
        "id": doc_id,
        "actor_id": resolved_actor_id,
        "actor_name": actor_name,
        "actor_email": actor_email,
        "module": module,
        "action": action,
        "description": description,
        "result": result,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }

    def _write():
        try:
            supabase.table("audit_logs").insert(audit_doc).execute()
        except Exception:
            pass

    threading.Thread(target=_write, daemon=True).start()
    return doc_id, audit_doc
