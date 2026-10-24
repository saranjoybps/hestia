"""
Script to initialize Firestore with default data
Run this after setting up Firebase credentials
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate("./firebase-credentials.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

def init_permissions():
    """Initialize role-based permissions"""
    permissions = [
        {
            "role": "director",
            "permissions": [
                "view_all_employees",
                "create_employee",
                "update_employee",
                "deactivate_employee",
                "approve_leaves",
                "manage_attendance",
                "generate_reports",
                "create_announcements",
                "manage_performance"
            ]
        },
        {
            "role": "hr",
            "permissions": [
                "view_all_employees",
                "create_employee",
                "update_employee",
                "approve_leaves",
                "generate_reports",
                "create_announcements"
            ]
        },
        {
            "role": "manager",
            "permissions": [
                "view_team_employees",
                "approve_leaves",
                "manage_attendance",
                "generate_reports",
                "manage_performance"
            ]
        },
        {
            "role": "lead",
            "permissions": [
                "view_reportees",
                "mark_attendance",
                "create_performance_review"
            ]
        },
        {
            "role": "employee",
            "permissions": [
                "view_own_data",
                "request_leave",
                "view_announcements"
            ]
        }
    ]
    
    for perm in permissions:
        db.collection("permissions").document(perm["role"]).set(perm)
        print(f"✓ Created permissions for {perm['role']}")


def init_departments():
    """Initialize default departments"""
    departments = [
        {
            "name": "Engineering",
            "description": "Software development and technical teams",
            "head_id": None,
            "created_at": datetime.utcnow()
        },
        {
            "name": "Human Resources",
            "description": "HR and employee management",
            "head_id": None,
            "created_at": datetime.utcnow()
        },
        {
            "name": "Finance",
            "description": "Financial management and accounting",
            "head_id": None,
            "created_at": datetime.utcnow()
        },
        {
            "name": "Marketing",
            "description": "Marketing and communications",
            "head_id": None,
            "created_at": datetime.utcnow()
        },
        {
            "name": "Operations",
            "description": "Business operations and support",
            "head_id": None,
            "created_at": datetime.utcnow()
        }
    ]
    
    for dept in departments:
        db.collection("departments").add(dept)
        print(f"✓ Created department: {dept['name']}")


def init_collections():
    """Ensure all required collections exist"""
    collections = [
        "users",
        "departments",
        "attendance",
        "leaves",
        "tasks",
        "performance_reviews",
        "announcements",
        "permissions",
        "audit_logs"
    ]
    
    print("\nRequired Firestore collections:")
    for col in collections:
        print(f"  - {col}")


if __name__ == "__main__":
    print("Initializing Hestia Firestore Database...\n")
    
    try:
        print("Setting up permissions...")
        init_permissions()
        
        print("\nSetting up departments...")
        init_departments()
        
        print("\n" + "="*50)
        init_collections()
        
        print("\n" + "="*50)
        print("✓ Firestore initialization completed successfully!")
        print("\nNext steps:")
        print("1. Create your first admin user in Firebase Authentication")
        print("2. Add user document to Firestore 'users' collection")
        print("3. Login to the application")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nMake sure:")
        print("1. firebase-credentials.json exists in the backend directory")
        print("2. You have proper permissions in Firebase")
