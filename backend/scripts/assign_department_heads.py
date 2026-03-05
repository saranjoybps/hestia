"""
Script to assign department heads based on current employees
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

# Department head assignments based on imported employees
DEPARTMENT_HEADS = {
    "Customer Support": "bavya.mary87@gmail.com",  # Bavya Irudhaya Mary (Manager)
    "Human Resources": "jfedolin@gmail.com",       # Fedoline J (HR)
    # Technical Support and Management don't have heads yet
}

def assign_department_heads():
    """Assign department heads in Firestore"""
    
    print("Starting department head assignment...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    
    for dept_name, head_email in DEPARTMENT_HEADS.items():
        print(f"\nProcessing: {dept_name}")
        
        try:
            # Find department document
            dept_docs = db.collection('departments').where('name', '==', dept_name).limit(1).stream()
            dept_doc = None
            for doc in dept_docs:
                dept_doc = doc
                break
            
            if not dept_doc:
                print(f"   ⚠️  WARNING: Department '{dept_name}' not found")
                failed += 1
                continue
            
            # Find user by email
            user_docs = db.collection('users').where('email', '==', head_email).limit(1).stream()
            user_doc = None
            user_name = None
            for doc in user_docs:
                user_doc = doc
                user_name = doc.to_dict().get('name')
                break
            
            if not user_doc:
                print(f"   ⚠️  WARNING: User '{head_email}' not found")
                failed += 1
                continue
            
            # Update department with head_id
            db.collection('departments').document(dept_doc.id).update({
                'head_id': user_doc.id,
                'updated_at': datetime.utcnow().isoformat()
            })
            
            print(f"   ✅ SUCCESS: Assigned {user_name} as head of {dept_name}")
            print(f"      Email: {head_email}")
            print(f"      User ID: {user_doc.id}")
            successful += 1
            
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("DEPARTMENT HEAD ASSIGNMENT SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed:     {failed}")
    print(f"📊 Total:      {successful + failed}")
    print("=" * 80)
    
    if successful > 0:
        print("\n✅ Department heads have been assigned!")
        print("\n📋 Assigned Heads:")
        print("   • Customer Support: Bavya Irudhaya Mary (Manager)")
        print("   • Human Resources: Fedoline J (HR)")
        print("\n⚠️  Note: Technical Support and Management departments don't have heads yet.")
        print("   You can assign them later via the Departments page in the dashboard.")

if __name__ == "__main__":
    assign_department_heads()
