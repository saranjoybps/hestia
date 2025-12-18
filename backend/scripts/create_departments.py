"""
Script to create departments in Firestore
"""
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firebase_admin import credentials, firestore, initialize_app
import firebase_admin

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    initialize_app(cred)

db = firestore.client()

# Departments to create
DEPARTMENTS = [
    {
        "name": "Customer Support",
        "description": "Customer service and support operations",
        "head_id": None  # Can be set later
    },
    {
        "name": "Technical Support",
        "description": "Technical assistance and troubleshooting",
        "head_id": None
    },
    {
        "name": "Management",
        "description": "Executive leadership and strategic planning",
        "head_id": None
    },
    {
        "name": "Human Resources",
        "description": "HR operations, recruitment, and employee management",
        "head_id": None
    }
]

def create_departments():
    """Create departments in Firestore"""
    
    print("Starting department creation...")
    print("=" * 80)
    
    successful = 0
    skipped = 0
    failed = 0
    
    for dept in DEPARTMENTS:
        dept_name = dept["name"]
        print(f"\nProcessing: {dept_name}")
        
        try:
            # Check if department already exists
            existing = db.collection('departments').where('name', '==', dept_name).limit(1).stream()
            exists = False
            for doc in existing:
                exists = True
                print(f"   ⚠️  SKIPPED: Department '{dept_name}' already exists (ID: {doc.id})")
                skipped += 1
                break
            
            if not exists:
                # Create department
                dept_data = {
                    "name": dept["name"],
                    "description": dept["description"],
                    "head_id": dept["head_id"],
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                doc_ref = db.collection('departments').document()
                doc_ref.set(dept_data)
                
                print(f"   ✅ SUCCESS: Created department '{dept_name}' (ID: {doc_ref.id})")
                print(f"      Description: {dept['description']}")
                successful += 1
                
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("DEPARTMENT CREATION SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {successful}")
    print(f"⚠️  Skipped:    {skipped}")
    print(f"❌ Failed:     {failed}")
    print(f"📊 Total:      {successful + skipped + failed}")
    print("=" * 80)
    
    if successful > 0 or skipped > 0:
        print("\n✅ All departments are now available in the system!")
        print("\n📋 Department List:")
        for dept in DEPARTMENTS:
            print(f"   • {dept['name']}")
        
        print("\n💡 Next Steps:")
        print("   1. Assign department heads via the Departments page")
        print("   2. Verify employee department assignments")
        print("   3. Update any additional department information")

if __name__ == "__main__":
    create_departments()
