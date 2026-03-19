"""
Script to import employees from Employee_Basic.csv into Firebase Auth + Firestore.

Rules applied:
- Email: Personal Email (falls back to Work Email if empty)
- Password: 123456 (fixed)
- Role: "manager" for Employee #5 (Bavya), "employee" for all others
- Designation: "Customer Support" (fixed)
- Department: "Customer Support" (fixed)
- UID in Firestore = UID from Firebase Auth
"""
import sys
import os
import csv
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firebase_admin import auth as firebase_auth, credentials, firestore, initialize_app
import firebase_admin

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    initialize_app(cred)

db = firestore.client()

# Fixed values
DEFAULT_PASSWORD = "123456"
FIXED_DESIGNATION = "Customer Support"
FIXED_DEPARTMENT = "Customer Support"
MANAGER_EMP_NUMBER = "5"  # Bavya


def parse_date(date_str):
    """Parse date in DD-MM-YYYY format and return ISO string YYYY-MM-DD"""
    if not date_str or date_str.strip() == "":
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y").strftime("%Y-%m-%d")
    except Exception as e:
        print(f"   ⚠️  Could not parse date '{date_str}': {e}")
        return None


def import_employees(csv_file_path):
    """Import employees from CSV file into Firebase Auth and Firestore"""

    print(f"Starting employee import from: {csv_file_path}")
    print("=" * 80)

    successful = 0
    failed = 0
    skipped = 0

    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)

        for idx, row in enumerate(csv_reader, start=1):
            emp_number = row['Employee Number'].strip()
            first_name = row['First Name'].strip()
            last_name = row['Last Name'].strip()
            work_email = row['Work Email'].strip().lower()
            personal_email = row['Personal Email'].strip().lower()

            # Use personal email; fall back to work email if empty
            email = personal_email if personal_email else work_email

            full_name = f"{first_name} {last_name}".strip()

            print(f"\n[{idx}] Processing: {full_name} (Emp #{emp_number})")
            print(f"      Login email: {email}")

            # Check if user already exists in Firebase Auth
            try:
                existing_user = firebase_auth.get_user_by_email(email)
                print(f"   ⚠️  SKIPPED: Auth user already exists with email {email} (uid: {existing_user.uid})")
                skipped += 1
                continue
            except firebase_auth.UserNotFoundError:
                pass  # Good — proceed to create
            except Exception as e:
                print(f"   ❌ ERROR checking existing user: {e}")
                failed += 1
                continue

            try:
                # Determine role: manager only for Bavya (emp #5), else employee
                role = "manager" if emp_number == MANAGER_EMP_NUMBER else "employee"

                # Parse dates
                doj = parse_date(row['Date of Joining'])
                dob = parse_date(row['Date of Birth'])

                phone = row['Mobile Number'].strip() or None
                gender = row['Gender'].strip()

                # Address
                address = {
                    "line1": row['Personal AddressLine1'].strip(),
                    "line2": row['Personal AddressLine2'].strip(),
                    "city": row['Personal City'].strip(),
                    "state": row['Personal StateCode'].strip(),
                    "postalCode": row['Personal PostalCode'].strip(),
                    "country": row['Personal Country'].strip(),
                }

                # 1. Create user in Firebase Authentication
                firebase_user = firebase_auth.create_user(
                    email=email,
                    password=DEFAULT_PASSWORD,
                    display_name=full_name
                )
                uid = firebase_user.uid

                # 2. Save user document to Firestore (doc ID = UID)
                user_doc = {
                    "uid": uid,
                    "email": email,
                    "name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "role": role,
                    "department": FIXED_DEPARTMENT,
                    "designation": FIXED_DESIGNATION,
                    "dateOfJoining": doj,
                    "manager_id": None,
                    "lead_id": None,
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "updated_at": None,
                    "created_by": "system_import",

                    # Extra info
                    "employeeNumber": emp_number,
                    "gender": gender,
                    "dateOfBirth": dob,
                    "workEmail": work_email,
                    "personalEmail": email,
                    "fatherName": row['Father Name'].strip(),

                    # Address
                    "address": address,
                }

                db.collection("users").document(uid).set(user_doc)

                print(f"   ✅ SUCCESS: {full_name}")
                print(f"      UID:        {uid}")
                print(f"      Email:      {email}")
                print(f"      Password:   {DEFAULT_PASSWORD}")
                print(f"      Role:       {role}")
                print(f"      Department: {FIXED_DEPARTMENT}")
                print(f"      Designation:{FIXED_DESIGNATION}")

                successful += 1

            except firebase_auth.EmailAlreadyExistsError:
                print(f"   ⚠️  SKIPPED: Email {email} already exists in Auth")
                skipped += 1
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {successful}")
    print(f"⚠️  Skipped:    {skipped}")
    print(f"❌ Failed:     {failed}")
    print(f"📊 Total:      {successful + skipped + failed}")
    print("=" * 80)
    print(f"\nAll accounts created with password: {DEFAULT_PASSWORD}")
    print("Employees should change their password on first login.\n")


if __name__ == "__main__":
    # Path relative to the backend/ directory (where script is run from)
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Employee_Basic.csv")

    if not os.path.exists(csv_path):
        print(f"❌ ERROR: CSV file not found at {csv_path}")
        print(f"Current directory: {os.getcwd()}")
        sys.exit(1)

    import_employees(csv_path)
