"""
Script to import employees from CSV file into Firebase
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

def parse_date(date_str):
    """Parse date in DD-MM-YYYY format"""
    if not date_str or date_str.strip() == "":
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y")
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
        return None

def generate_password(first_name, emp_number):
    """Generate default password: FirstName@EmpNumber"""
    return f"{first_name.strip()}@{emp_number}"

def map_department(dept_csv):
    """Map CSV department to system department"""
    dept_mapping = {
        "Client support": "Customer Support",
        "Tech support": "Technical Support",
        "HR": "Human Resources"
    }
    return dept_mapping.get(dept_csv.strip(), dept_csv.strip())

def determine_role(designation):
    """Determine role based on designation"""
    designation_lower = designation.lower().strip()
    if "manager" in designation_lower:
        return "manager"
    elif "lead" in designation_lower or "team lead" in designation_lower:
        return "lead"
    elif "hr" in designation_lower:
        return "hr"
    else:
        return "employee"

def import_employees(csv_file_path):
    """Import employees from CSV file"""
    
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
            email = row['Work Email'].strip().lower()
            
            print(f"\n[{idx}] Processing: {first_name} {last_name} (Emp #{emp_number})")
            
            # Check if user already exists
            try:
                existing_user = firebase_auth.get_user_by_email(email)
                print(f"   ⚠️  SKIPPED: User already exists with email {email}")
                skipped += 1
                continue
            except firebase_auth.UserNotFoundError:
                pass  # User doesn't exist, proceed with creation
            except Exception as e:
                print(f"   ❌ ERROR checking existing user: {e}")
                failed += 1
                continue
            
            try:
                # Generate password
                password = generate_password(first_name, emp_number)
                
                # Parse dates
                doj = parse_date(row['Date of Joining'])
                dob = parse_date(row['Date of Birth'])
                
                # Map fields
                full_name = f"{first_name} {last_name}"
                department = map_department(row['Department'])
                designation = row['Designation'].strip()
                role = determine_role(designation)
                gender = row['Gender'].strip()
                phone = row['Mobile Number'].strip() if row['Mobile Number'].strip() else None
                
                # Address fields
                address_line1 = row['Personal AddressLine1'].strip()
                address_line2 = row['Personal AddressLine2'].strip()
                city = row['Personal City'].strip()
                state = row['Personal StateCode'].strip()
                postal_code = row['Personal PostalCode'].strip()
                country = row['Personal Country'].strip()
                
                # Create user in Firebase Auth
                firebase_user = firebase_auth.create_user(
                    email=email,
                    password=password,
                    display_name=full_name
                )
                
                # Prepare user document for Firestore
                user_doc = {
                    "email": email,
                    "name": full_name,
                    "firstName": first_name,
                    "lastName": last_name,
                    "phone": phone,
                    "role": role,
                    "department": department,
                    "designation": designation,
                    "manager_id": None,  # To be updated later if needed
                    "lead_id": None,
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "updated_at": None,
                    "created_by": "system_import",
                    
                    # Additional employee details
                    "employeeNumber": emp_number,
                    "gender": gender,
                    "dateOfJoining": doj.isoformat() if doj else None,
                    "dateOfBirth": dob.isoformat() if dob else None,
                    "personalEmail": row['Personal Email'].strip(),
                    "fatherName": row['Father Name'].strip(),
                    "panNumber": row['PAN Number'].strip(),
                    
                    # Address
                    "address": {
                        "line1": address_line1,
                        "line2": address_line2,
                        "city": city,
                        "state": state,
                        "postalCode": postal_code,
                        "country": country
                    }
                }
                
                # Save to Firestore
                db.collection("users").document(firebase_user.uid).set(user_doc)
                
                print(f"   ✅ SUCCESS: Created user {full_name}")
                print(f"      Email: {email}")
                print(f"      Password: {password}")
                print(f"      Role: {role}")
                print(f"      Department: {department}")
                
                successful += 1
                
            except firebase_auth.EmailAlreadyExistsError:
                print(f"   ⚠️  SKIPPED: Email {email} already exists")
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
    
    if successful > 0:
        print("\n⚠️  IMPORTANT: Save the generated passwords!")
        print("Default password format: FirstName@EmployeeNumber")
        print("Example: Bavya@5\n")

if __name__ == "__main__":
    csv_path = "../Employee_Details.csv"
    
    if not os.path.exists(csv_path):
        print(f"❌ ERROR: CSV file not found at {csv_path}")
        print(f"Current directory: {os.getcwd()}")
        sys.exit(1)
    
    import_employees(csv_path)
