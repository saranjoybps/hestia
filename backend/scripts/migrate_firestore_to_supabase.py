"""
One-time migration: Firestore → Supabase
Migrates: users → attendance → leaves → tasks → performance_reviews

Run from the backend/ directory:
    python scripts/migrate_firestore_to_supabase.py

Safe to re-run: users are upserted on firebase_uid; all other tables are
only inserted if the matching Supabase user exists and no duplicate exists.
"""

import asyncio
import sys
import os
from datetime import datetime, date
from typing import Optional

# ── ensure backend package is importable ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import credentials, firestore as firebase_firestore

from app.dependencies import db, supabase  # noqa: E402  (initialises Firebase + Supabase)


# ── helpers ───────────────────────────────────────────────────────────────────

def _iso(value) -> Optional[str]:
    """Convert any datetime/date/string to an ISO string, or None."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value) or None


def _build_uid_to_row(rows: list) -> dict:
    """Return {firebase_uid: row} lookup from a list of Supabase user rows."""
    return {row["firebase_uid"]: row for row in rows if row.get("firebase_uid")}


def _build_uid_to_id(rows: list) -> dict:
    """Return {firebase_uid: supabase_uuid_str} lookup."""
    return {row["firebase_uid"]: str(row["id"]) for row in rows if row.get("firebase_uid")}


# ── Step 1: migrate users ─────────────────────────────────────────────────────

def migrate_users() -> dict:
    """
    Upsert every Firestore user into Supabase users table.
    Returns {firebase_uid: supabase_uuid_str} for use by subsequent steps.
    """
    print("\n── Migrating users ──────────────────────────────────────────────────")
    fs_docs = list(db.collection("users").stream())
    print(f"   Firestore docs: {len(fs_docs)}")

    upserted = skipped = errors = 0

    for doc in fs_docs:
        data = doc.to_dict() or {}
        firebase_uid = doc.id  # doc id IS the firebase uid

        payload = {
            "firebase_uid": firebase_uid,
            "email": data.get("email") or data.get("workEmail") or data.get("personalEmail"),
            "name": data.get("name") or "Unknown",
            "last_name": data.get("last_name"),
            "phone": data.get("phone") or None,
            "role": data.get("role") or "employee",
            "department": data.get("department"),
            "designation": data.get("designation"),
            "date_of_joining": _iso(data.get("dateOfJoining")),
            # manager_id / lead_id are still TEXT (firebase UIDs) at this point;
            # we keep them as TEXT here and update to UUIDs after the UUID migration
            # (supabase/migrate_manager_id_to_uuid.sql).
            "manager_id": data.get("manager_id"),
            "lead_id": data.get("lead_id"),
            "status": data.get("status") or "active",
            "created_at": _iso(data.get("created_at")) or datetime.utcnow().isoformat(),
            "updated_at": _iso(data.get("updated_at")),
            "created_by": data.get("created_by"),
        }

        if not payload["email"]:
            print(f"   ⚠  SKIP {firebase_uid}: no email")
            skipped += 1
            continue

        try:
            resp = supabase.table("users").upsert(
                payload, on_conflict="firebase_uid"
            ).execute()
            if resp.data:
                upserted += 1
            else:
                print(f"   ⚠  No data returned for {firebase_uid}")
                errors += 1
        except Exception as exc:
            print(f"   ✗  {firebase_uid}: {exc}")
            errors += 1

    print(f"   Done — upserted={upserted}  skipped={skipped}  errors={errors}")

    # Reload all rows so callers get fresh UUIDs
    rows = supabase.table("users").select("*").execute().data or []
    return _build_uid_to_id(rows)


# ── Step 2: migrate attendance ────────────────────────────────────────────────

def migrate_attendance(uid_to_id: dict) -> None:
    print("\n── Migrating attendance ─────────────────────────────────────────────")
    fs_docs = list(db.collection("attendance").stream())
    print(f"   Firestore docs: {len(fs_docs)}")

    inserted = skipped = errors = 0

    # Fetch existing (user_id, date) pairs to avoid UNIQUE violations
    existing_resp = supabase.table("attendance").select("user_id,date").execute()
    existing = {
        (str(r["user_id"]), str(r["date"])) for r in (existing_resp.data or [])
    }

    for doc in fs_docs:
        data = doc.to_dict() or {}
        fs_user_uid = data.get("user_id")
        user_supabase_id = uid_to_id.get(fs_user_uid)

        if not user_supabase_id:
            print(f"   ⚠  SKIP attendance {doc.id}: user {fs_user_uid} not in Supabase")
            skipped += 1
            continue

        day = str(data.get("date") or "")
        if not day:
            skipped += 1
            continue

        if (user_supabase_id, day) in existing:
            skipped += 1
            continue

        # map marked_by / corrected_by
        marked_by_id = uid_to_id.get(data.get("marked_by"))
        corrected_by_id = uid_to_id.get(data.get("corrected_by"))

        # Normalise status: Firestore uses frontend values, DB expects snake_case
        raw_status = data.get("status", "present")
        status_map = {"half-day": "half_day", "on-leave": "leave", "week-off": "leave", "comp-off": "leave"}
        db_status = status_map.get(raw_status, raw_status)

        # Build check_in/check_out datetimes from "HH:MM" strings + date
        def combine(day_str, time_str):
            if not time_str:
                return None
            try:
                t = datetime.strptime(time_str.strip()[:5], "%H:%M").time()
                d = datetime.strptime(day_str, "%Y-%m-%d").date()
                return datetime.combine(d, t).isoformat()
            except Exception:
                return None

        payload = {
            "user_id": user_supabase_id,
            "date": day,
            "status": db_status,
            "check_in_time": combine(day, data.get("check_in")),
            "check_out_time": combine(day, data.get("check_out")),
            "total_hours": data.get("total_hours"),
            "notes": data.get("notes") or "",
            "marked_by": marked_by_id,
            "corrected_by": corrected_by_id,
            "corrected_at": _iso(data.get("corrected_at")),
            "is_week_off": data.get("is_week_off") or False,
            "is_comp_off": data.get("is_comp_off") or False,
            "created_at": _iso(data.get("created_at")) or datetime.utcnow().isoformat(),
            "updated_at": _iso(data.get("updated_at")),
        }

        try:
            resp = supabase.table("attendance").insert(payload).execute()
            if resp.data:
                inserted += 1
                existing.add((user_supabase_id, day))
            else:
                errors += 1
        except Exception as exc:
            print(f"   ✗  attendance {doc.id}: {exc}")
            errors += 1

    print(f"   Done — inserted={inserted}  skipped={skipped}  errors={errors}")


# ── Step 3: migrate leaves ────────────────────────────────────────────────────

def migrate_leaves(uid_to_id: dict) -> None:
    print("\n── Migrating leaves ─────────────────────────────────────────────────")
    fs_docs = list(db.collection("leaves").stream())
    print(f"   Firestore docs: {len(fs_docs)}")

    inserted = skipped = errors = 0

    # Build set of (user_id, start_date, leave_type) already in Supabase
    existing_resp = supabase.table("leaves").select("user_id,start_date,leave_type").execute()
    existing = {
        (str(r["user_id"]), str(r["start_date"]), r["leave_type"])
        for r in (existing_resp.data or [])
    }

    for doc in fs_docs:
        data = doc.to_dict() or {}
        fs_user_uid = data.get("userId")
        user_supabase_id = uid_to_id.get(fs_user_uid)

        if not user_supabase_id:
            print(f"   ⚠  SKIP leave {doc.id}: user {fs_user_uid} not in Supabase")
            skipped += 1
            continue

        approved_by_id = uid_to_id.get(data.get("approvedBy"))

        payload = {
            "user_id": user_supabase_id,
            "leave_type": data.get("leaveType") or "sick",
            "start_date": str(data.get("startDate") or ""),
            "end_date": str(data.get("endDate") or ""),
            "number_of_days": data.get("totalDays"),
            "reason": data.get("reason") or "",
            "status": data.get("status") or "pending",
            "approved_by": approved_by_id,
            "approved_at": _iso(data.get("approvalDate")),
            "rejection_reason": data.get("rejectionReason"),
            "created_at": _iso(data.get("appliedDate")) or datetime.utcnow().isoformat(),
            "updated_at": _iso(data.get("appliedDate")) or datetime.utcnow().isoformat(),
        }

        if not payload["start_date"] or not payload["end_date"]:
            skipped += 1
            continue

        dedup_key = (user_supabase_id, payload["start_date"], payload["leave_type"])
        if dedup_key in existing:
            skipped += 1
            continue

        try:
            resp = supabase.table("leaves").insert(payload).execute()
            if resp.data:
                inserted += 1
                existing.add(dedup_key)
            else:
                errors += 1
        except Exception as exc:
            print(f"   ✗  leave {doc.id}: {exc}")
            errors += 1

    print(f"   Done — inserted={inserted}  skipped={skipped}  errors={errors}")


# ── Step 4: migrate tasks ─────────────────────────────────────────────────────

def migrate_tasks(uid_to_id: dict) -> None:
    print("\n── Migrating tasks ──────────────────────────────────────────────────")
    fs_docs = list(db.collection("tasks").stream())
    print(f"   Firestore docs: {len(fs_docs)}")

    inserted = skipped = errors = 0

    # Build set of (assigned_to, title, created_at) to avoid duplicates
    existing_resp = supabase.table("tasks").select("assigned_to,title,created_at").execute()
    existing = {
        (str(r["assigned_to"]), r["title"], str(r["created_at"])[:19])
        for r in (existing_resp.data or [])
    }

    for doc in fs_docs:
        data = doc.to_dict() or {}
        assignee_uid = data.get("assigneeId")
        creator_uid = data.get("createdBy")

        assigned_to_id = uid_to_id.get(assignee_uid)
        assigned_by_id = uid_to_id.get(creator_uid)

        if not assigned_to_id:
            print(f"   ⚠  SKIP task {doc.id}: assignee {assignee_uid} not in Supabase")
            skipped += 1
            continue

        payload = {
            "title": data.get("title") or "Untitled",
            "description": data.get("description"),
            "assigned_to": assigned_to_id,
            "assignee_name": data.get("assigneeName"),
            "assignee_email": data.get("assigneeEmail"),
            "assigned_by": assigned_by_id,
            "created_by_name": data.get("createdByName"),
            "status": data.get("status") or "open",
            "priority": data.get("priority") or "medium",
            "due_date": _iso(data.get("dueDate")),
            "attachments": data.get("attachments") or [],
            "completed_at": _iso(data.get("updatedAt")) if data.get("status") == "completed" else None,
            "created_at": _iso(data.get("createdAt")) or datetime.utcnow().isoformat(),
            "updated_at": _iso(data.get("updatedAt")),
        }

        dedup_key = (assigned_to_id, payload["title"], str(payload["created_at"])[:19])
        if dedup_key in existing:
            skipped += 1
            continue

        try:
            resp = supabase.table("tasks").insert(payload).execute()
            if resp.data:
                inserted += 1
                existing.add(dedup_key)
            else:
                errors += 1
        except Exception as exc:
            print(f"   ✗  task {doc.id}: {exc}")
            errors += 1

    print(f"   Done — inserted={inserted}  skipped={skipped}  errors={errors}")


# ── Step 5: migrate performance reviews ──────────────────────────────────────

def migrate_performance_reviews(uid_to_id: dict) -> None:
    print("\n── Migrating performance_reviews ────────────────────────────────────")
    fs_docs = list(db.collection("performance_reviews").stream())
    print(f"   Firestore docs: {len(fs_docs)}")

    inserted = skipped = errors = 0

    for doc in fs_docs:
        data = doc.to_dict() or {}
        subject_uid = data.get("userId")
        reviewer_uid = data.get("reviewerId")

        employee_id = uid_to_id.get(subject_uid)
        reviewer_id = uid_to_id.get(reviewer_uid)

        if not employee_id:
            print(f"   ⚠  SKIP review {doc.id}: subject {subject_uid} not in Supabase")
            skipped += 1
            continue

        payload = {
            "employee_id": employee_id,
            "reviewer_id": reviewer_id,
            "user_name": data.get("userName"),
            "user_email": data.get("userEmail"),
            "reviewer_name": data.get("reviewerName"),
            "reviewer_role": data.get("reviewerRole"),
            "review_type": data.get("reviewType"),
            "rating": data.get("rating"),
            "context": data.get("context"),
            "review_date": _iso(data.get("reviewDate")),
            "status": data.get("status") or "pending",
            "created_at": _iso(data.get("createdAt")) or datetime.utcnow().isoformat(),
            "updated_at": _iso(data.get("updatedAt")),
        }

        try:
            resp = supabase.table("performance_reviews").insert(payload).execute()
            if resp.data:
                inserted += 1
            else:
                errors += 1
        except Exception as exc:
            print(f"   ✗  review {doc.id}: {exc}")
            errors += 1

    print(f"   Done — inserted={inserted}  skipped={skipped}  errors={errors}")


# ── Step 6: print final counts ────────────────────────────────────────────────

def print_summary() -> None:
    print("\n── Final Supabase row counts ─────────────────────────────────────────")
    for table in ["users", "attendance", "leaves", "tasks", "performance_reviews", "departments"]:
        try:
            rows = supabase.table(table).select("id").execute()
            print(f"   {table}: {len(rows.data or [])} rows")
        except Exception as exc:
            print(f"   {table}: ERROR {exc}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  Firestore → Supabase migration")
    print("=" * 65)

    uid_to_id = migrate_users()
    print(f"\n   {len(uid_to_id)} users available for FK mapping")

    migrate_attendance(uid_to_id)
    migrate_leaves(uid_to_id)
    migrate_tasks(uid_to_id)
    migrate_performance_reviews(uid_to_id)
    print_summary()

    print("\n✅  Migration complete.\n")


if __name__ == "__main__":
    main()
