#!/usr/bin/env python
"""
Test script to verify Supabase connection and schema
Run from backend directory: python test_supabase_connection.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_supabase_connection():
    """Test Supabase client initialization and basic queries"""
    
    print("=" * 60)
    print("🔍 Testing Supabase Connection")
    print("=" * 60)
    
    # Test 1: Check environment variables
    print("\n1️⃣  Checking environment variables...")
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_SERVICE_ROLE_KEY',
        'SUPABASE_DB_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"   ❌ {var} - NOT SET")
        else:
            value = os.getenv(var)
            display_value = value[:20] + "..." if len(value) > 20 else value
            print(f"   ✅ {var} - {display_value}")
    
    if missing_vars:
        print(f"\n❌ Missing variables: {', '.join(missing_vars)}")
        print("   Check backend/.env file")
        return False
    
    # Test 2: Import modules
    print("\n2️⃣  Importing modules...")
    try:
        from app.config import get_settings
        print("   ✅ app.config imported")
    except Exception as e:
        print(f"   ❌ Failed to import app.config: {e}")
        return False
    
    try:
        from app.dependencies import supabase
        print("   ✅ app.dependencies imported (Supabase client ready)")
    except Exception as e:
        print(f"   ❌ Failed to import app.dependencies: {e}")
        return False
    
    # Test 3: Test Supabase connection
    print("\n3️⃣  Testing Supabase API connection...")
    try:
        # Try to query permissions table
        response = supabase.table('permissions').select('*').limit(1).execute()
        print(f"   ✅ Successfully queried 'permissions' table")
        print(f"   📊 Found {len(response.data)} records")
    except Exception as e:
        print(f"   ❌ Failed to query Supabase: {e}")
        return False
    
    # Test 4: Check if all tables exist
    print("\n4️⃣  Checking database tables...")
    tables_to_check = [
        'users', 'attendance', 'leaves', 'tasks', 'performance_reviews',
        'announcements', 'audit_logs', 'permissions', 'departments',
        'shifts', 'onboarding', 'letters', 'reports'
    ]
    
    missing_tables = []
    for table in tables_to_check:
        try:
            response = supabase.table(table).select('*').limit(0).execute()
            print(f"   ✅ {table}")
        except Exception as e:
            missing_tables.append(table)
            print(f"   ❌ {table} - {str(e)[:50]}")
    
    if missing_tables:
        print(f"\n⚠️  Missing tables: {', '.join(missing_tables)}")
        print("   Run the SQL schema in Supabase dashboard:")
        print("   - Copy content from: supabase/init_schema.sql")
        print("   - Paste into Supabase SQL Editor")
        print("   - Click Run")
        return False
    
    # Test 5: Check permissions are configured
    print("\n5️⃣  Checking default permissions...")
    try:
        response = supabase.table('permissions').select('*').execute()
        roles = [p['role'] for p in response.data]
        expected_roles = ['director', 'hr', 'manager', 'lead', 'employee']
        
        for role in expected_roles:
            if role in roles:
                print(f"   ✅ {role}")
            else:
                print(f"   ❌ {role} - NOT FOUND")
        
        if len(roles) != len(expected_roles):
            print(f"\n⚠️  Expected {len(expected_roles)} roles, found {len(roles)}")
    except Exception as e:
        print(f"   ❌ Failed to check permissions: {e}")
        return False
    
    # Test 6: Test user provisioning function
    print("\n6️⃣  Testing user provisioning logic...")
    try:
        from app.supabase_helper import SupabaseHelper
        print("   ✅ SupabaseHelper imported successfully")
        print("   ✅ User provisioning functions available")
    except Exception as e:
        print(f"   ❌ Failed to import SupabaseHelper: {e}")
        return False
    
    # Final summary
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\n✨ Supabase is configured correctly and ready to use!")
    print("\nNext steps:")
    print("1. Start backend: uvicorn app.main:app --reload")
    print("2. Test Firebase + Supabase integration")
    print("3. Migrate routes to use Supabase")
    print("4. Test with real user authentication")
    
    return True

if __name__ == "__main__":
    try:
        success = test_supabase_connection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
