"""
One-time migration script to copy Firestore departments into Supabase.

Run from the backend directory:
    .\\venv\\Scripts\\python.exe scripts\\migrate_departments.py
"""

import asyncio
from datetime import datetime
import sys
from pathlib import Path

# Make sure the backend app package is importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dependencies import db, supabase
from app.supabase_helper import SupabaseHelper


async def migrate_departments() -> None:
    firestore_docs = list(db.collection("departments").stream())
    if not firestore_docs:
        print("No Firestore departments found.")
        return

    migrated = 0
    skipped = 0

    for doc in firestore_docs:
        data = doc.to_dict() or {}
        name = data.get("name")
        if not name:
            skipped += 1
            continue

        head_id = data.get("head_id")
        mapped_head_id = None
        if head_id:
            head_row = await SupabaseHelper.get_user_row_by_firebase_uid(head_id)
            if head_row:
                mapped_head_id = str(head_row["id"])

        payload = {
            "name": name,
            "description": data.get("description"),
            "head_id": mapped_head_id,
            "created_at": data.get("created_at") or datetime.utcnow().isoformat(),
            "updated_at": data.get("updated_at") or datetime.utcnow().isoformat(),
        }

        supabase.table("departments").upsert(payload, on_conflict="name").execute()
        migrated += 1
        print(f"Migrated department: {name}")

    print(f"Done. Migrated={migrated}, skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(migrate_departments())
