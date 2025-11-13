import firebase_admin
from firebase_admin import credentials, auth, firestore
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.config import get_settings

settings = get_settings()

# Initialize Firebase Admin SDK
cred = credentials.Certificate(settings.firebase_credentials_path)
firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()

# Security
security = HTTPBearer()


class FirebaseAuth:
    """Firebase authentication handler"""
    
    @staticmethod
    async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        """Verify Firebase ID token"""
        try:
            token = credentials.credentials
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def get_current_user(token_data: dict = Depends(verify_token)) -> dict:
        """Get current user from Firestore"""
        try:
            uid = token_data.get("uid")
            user_ref = db.collection("users").document(uid)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_data = user_doc.to_dict()
            user_data["uid"] = uid
            return user_data
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching user: {str(e)}"
            )


# Dependency functions
async def get_current_user(token_data: dict = Depends(FirebaseAuth.verify_token)) -> dict:
    """Get current authenticated user"""
    return await FirebaseAuth.get_current_user(token_data)


def require_role(*allowed_roles: str):
    """Decorator to require specific roles"""
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


def require_permission(*required_permissions: str):
    """Decorator to require specific permissions"""
    async def permission_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        
        # Get permissions for role
        perm_doc = db.collection("permissions").document(user_role).get()
        if not perm_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permissions defined for this role"
            )
        
        permissions = perm_doc.to_dict().get("permissions", [])
        
        # Check if user has required permissions
        for perm in required_permissions:
            if perm not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {perm}"
                )
        
        return current_user
    return permission_checker


# Export commonly used items
__all__ = [
    "db",
    "auth",
    "get_current_user",
    "require_role",
    "require_permission",
    "FirebaseAuth"
]
