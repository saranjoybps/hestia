"""
Supabase utility functions for database operations
"""

from app.dependencies import supabase
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any
from uuid import UUID


class SupabaseHelper:
    """Helper class for common Supabase operations"""

    @staticmethod
    def _public_user(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert a Supabase user row into the API shape used by the frontend."""
        if not row:
            return None

        public = dict(row)
        public["uid"] = public.pop("firebase_uid", None)
        if "date_of_joining" in public:
            public["dateOfJoining"] = public.pop("date_of_joining")
        return public

    @staticmethod
    def _public_users(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [u for u in (SupabaseHelper._public_user(row) for row in rows) if u]

    @staticmethod
    def _user_query_rows(rows: List[Dict[str, Any]], **filters: Any) -> List[Dict[str, Any]]:
        result = rows
        for key, value in filters.items():
            if value is None:
                continue
            result = [row for row in result if row.get(key) == value]
        return result

    @staticmethod
    async def get_user_row_by_firebase_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
        try:
            response = supabase.table("users").select("*").eq("firebase_uid", firebase_uid).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User not found: {str(e)}")

    @staticmethod
    async def get_public_user_by_firebase_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
        return SupabaseHelper._public_user(await SupabaseHelper.get_user_row_by_firebase_uid(firebase_uid))

    @staticmethod
    async def get_user_row_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = supabase.table("users").select("*").eq("id", str(user_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User not found: {str(e)}")

    @staticmethod
    async def get_public_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        return SupabaseHelper._public_user(await SupabaseHelper.get_user_row_by_id(user_id))

    @staticmethod
    async def get_all_user_rows() -> List[Dict[str, Any]]:
        try:
            response = supabase.table("users").select("*").execute()
            return response.data or []
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error fetching users: {str(e)}")

    @staticmethod
    async def get_all_public_users() -> List[Dict[str, Any]]:
        return SupabaseHelper._public_users(await SupabaseHelper.get_all_user_rows())

    @staticmethod
    async def get_public_user_map() -> Dict[str, Dict[str, Any]]:
        users = await SupabaseHelper.get_all_user_rows()
        mapped: Dict[str, Dict[str, Any]] = {}
        for row in users:
            public = SupabaseHelper._public_user(row)
            if public and row.get("id"):
                mapped[str(row["id"])] = public
        return mapped

    @staticmethod
    async def get_internal_user_id(firebase_uid: str) -> Optional[str]:
        row = await SupabaseHelper.get_user_row_by_firebase_uid(firebase_uid)
        return str(row["id"]) if row and row.get("id") else None

    @staticmethod
    async def get_reportees(firebase_uid: str) -> List[Dict[str, Any]]:
        internal_id = await SupabaseHelper.get_internal_user_id(firebase_uid)
        requester = await SupabaseHelper.get_public_user_by_firebase_uid(firebase_uid)
        if not internal_id and not requester:
            return []

        root_identifiers = {str(value) for value in [internal_id, firebase_uid, requester.get("uid") if requester else None, requester.get("id") if requester else None] if value}
        users = await SupabaseHelper.get_all_public_users()

        # Support both legacy TEXT hierarchy fields (Firebase UID) and migrated UUID hierarchy fields.
        result_by_key: Dict[str, Dict[str, Any]] = {}
        visited: set[str] = set()
        frontier = set(root_identifiers)
        for row in users:
            row_uid = str(row.get("uid") or "")
            row_internal_id = str(row.get("id") or "")
            row_identifiers = {identifier for identifier in [row_uid, row_internal_id] if identifier}
            if row_uid in root_identifiers or row_internal_id in root_identifiers:
                continue

            manager_id = str(row.get("manager_id") or "")
            lead_id = str(row.get("lead_id") or "")
            if manager_id in frontier or lead_id in frontier:
                result_by_key[row_uid or row_internal_id] = row
                visited.update(row_identifiers)
                frontier.update(row_identifiers)

        # Expand one more pass so the helper returns the full nested tree, not just direct reportees.
        changed = True
        while changed:
            changed = False
            for row in users:
                row_uid = str(row.get("uid") or "")
                row_internal_id = str(row.get("id") or "")
                row_identifiers = {identifier for identifier in [row_uid, row_internal_id] if identifier}
                if not row_identifiers or row_uid in visited or row_internal_id in visited:
                    continue

                manager_id = str(row.get("manager_id") or "")
                lead_id = str(row.get("lead_id") or "")
                if manager_id in frontier or lead_id in frontier:
                    result_by_key[row_uid or row_internal_id] = row
                    visited.update(row_identifiers)
                    frontier.update(row_identifiers)
                    changed = True
        return list(result_by_key.values())

    @staticmethod
    async def list_public_users(
        department: Optional[str] = None,
        status_filter: Optional[str] = None,
        roles: Optional[List[str]] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        users = await SupabaseHelper.get_all_public_users()

        if department:
            users = [u for u in users if u.get("department") == department]
        if status_filter:
            users = [u for u in users if u.get("status") == status_filter]
        if roles:
            users = [u for u in users if u.get("role") in roles]
        if search:
            needle = search.lower()
            def matches(u: Dict[str, Any]) -> bool:
                full_name = " ".join(part for part in [u.get("name"), u.get("last_name")] if part)
                return any(
                    needle in str(field or "").lower()
                    for field in [u.get("name"), u.get("last_name"), full_name, u.get("email")]
                )
            users = [u for u in users if matches(u)]

        total = len(users)
        start = (page - 1) * limit
        end = start + limit
        paginated = users[start:end]
        return {
            "users": paginated,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": (total + limit - 1) // limit if total > 0 else 1,
        }
    
    @staticmethod
    async def get_user_by_firebase_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
        """Get user from Supabase by Firebase UID"""
        try:
            response = supabase.table("users").select("*").eq(
                "firebase_uid", firebase_uid
            ).single().execute()
            return response.data if response.data else None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User not found: {str(e)}"
            )
    
    @staticmethod
    async def get_user_by_id(user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get user from Supabase by UUID"""
        try:
            response = supabase.table("users").select("*").eq(
                "id", str(user_id)
            ).single().execute()
            return response.data if response.data else None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User not found: {str(e)}"
            )
    
    @staticmethod
    async def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user in Supabase"""
        try:
            response = supabase.table("users").insert(user_data).execute()
            if response.data:
                return response.data[0]
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating user: {str(e)}"
            )
    
    @staticmethod
    async def update_user(user_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user in Supabase"""
        try:
            response = supabase.table("users").update(update_data).eq(
                "id", str(user_id)
            ).execute()
            if response.data:
                return response.data[0]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error updating user: {str(e)}"
            )
    
    @staticmethod
    async def get_user_permissions(role: str) -> Optional[List[str]]:
        """Get permissions for a role"""
        try:
            response = supabase.table("permissions").select("permissions").eq(
                "role", role
            ).single().execute()
            if response.data:
                return response.data.get("permissions", [])
            return []
        except Exception as e:
            return []
    
    @staticmethod
    async def check_user_permission(firebase_uid: str, required_permission: str) -> bool:
        """Check if user has a specific permission"""
        try:
            user = await SupabaseHelper.get_user_by_firebase_uid(firebase_uid)
            if not user:
                return False
            
            permissions = await SupabaseHelper.get_user_permissions(user.get("role"))
            return required_permission in permissions
        except Exception:
            return False
    
    @staticmethod
    async def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all users with pagination"""
        try:
            response = supabase.table("users").select("*").range(
                offset, offset + limit - 1
            ).execute()
            return response.data if response.data else []
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error fetching users: {str(e)}"
            )
    
    @staticmethod
    async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
        """Get all users by role"""
        try:
            response = supabase.table("users").select("*").eq(
                "role", role
            ).execute()
            return response.data if response.data else []
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error fetching users: {str(e)}"
            )
    
    @staticmethod
    async def create_audit_log(
        actor_id: Optional[str],
        actor_name: Optional[str],
        actor_email: Optional[str],
        module: str,
        action: str,
        description: str,
        result: str = "success",
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create audit log entry"""
        try:
            log_data = {
                "actor_id": actor_id,
                "actor_name": actor_name,
                "actor_email": actor_email,
                "module": module,
                "action": action,
                "description": description,
                "result": result,
                "target_type": target_type,
                "target_id": target_id,
                "metadata": metadata or {}
            }
            
            response = supabase.table("audit_logs").insert(log_data).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            print(f"Audit log error: {str(e)}")
            return {}
