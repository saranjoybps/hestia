"""
Script to create a super admin user in Firebase
Run this after setting up Firebase credentials
"""

import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime
import sys

# Initialize Firebase Admin SDK
cred = credentials.Certificate("./firebase-credentials.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

def create_super_admin():
    """Create super admin user in Firebase Auth and Firestore"""
    
    # Admin details
    email = "admin@joyrts.com"
    password = "Admin@123456"  # Change this to a secure password
    name = "Super Administrator"
    
    print("Creating Super Admin User...")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print("-" * 50)
    
    try:
        # Check if user already exists
        try:
            existing_user = auth.get_user_by_email(email)
            print(f"✓ User already exists in Firebase Auth")
            print(f"  UID: {existing_user.uid}")
            user_uid = existing_user.uid
        except auth.UserNotFoundError:
            # Create user in Firebase Auth
            user = auth.create_user(
                email=email,
                password=password,
                display_name=name,
                email_verified=True
            )
            print(f"✓ Created user in Firebase Auth")
            print(f"  UID: {user.uid}")
            user_uid = user.uid
        
        # Create user document in Firestore
        user_doc = {
            "email": email,
            "name": name,
            "phone": "+1234567890",
            "role": "director",
            "department": "Management",
            "designation": "Director",
            "manager_id": None,
            "lead_id": None,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": None,
            "created_by": "system"
        }
        
        # Check if document already exists
        user_ref = db.collection("users").document(user_uid)
        if user_ref.get().exists:
            print(f"✓ User document already exists in Firestore")
        else:
            user_ref.set(user_doc)
            print(f"✓ Created user document in Firestore")
        
        print("-" * 50)
        print("✅ Super Admin Created Successfully!")
        print()
        print("Login Credentials:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print(f"  Role: Director (Full Access)")
        print()
        print("Next Steps:")
        print("  1. Go to http://localhost:3005/login")
        print("  2. Login with the credentials above")
        print("  3. Change the password from settings")
        print()
        print("⚠️  IMPORTANT: Change the default password after first login!")
        
    except Exception as e:
        print(f"✗ Error creating super admin: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        create_super_admin()
    except Exception as e:
        print(f"\n✗ Fatal Error: {str(e)}")
        print("\nMake sure:")
        print("1. firebase-credentials.json exists in the backend directory")
        print("2. You have proper permissions in Firebase")
        sys.exit(1)
