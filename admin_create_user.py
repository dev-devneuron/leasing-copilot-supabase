#!/usr/bin/env python3
"""
Admin User Creation Script for Production

This script allows admins to create users in production.
Use this instead of the development password_manager.py
"""

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client():
    """Get Supabase client with service role key."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    
    return create_client(url, key)

def create_user_in_supabase(email: str, password: str):
    """Create a user in Supabase Auth."""
    try:
        client = get_supabase_client()
        
        # Create user in Supabase Auth
        response = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # Auto-confirm for admin-created users
        })
        
        if response.user:
            return {
                "success": True,
                "user_id": response.user.id,
                "email": response.user.email
            }
        else:
            return {
                "success": False,
                "error": "Failed to create user in Supabase"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """Main function for admin user creation."""
    print("🔐 Leasap Admin User Creation")
    print("=" * 40)
    
    # Get user details
    print("\nEnter user details:")
    name = input("Full Name: ").strip()
    email = input("Email: ").strip()
    password = input("Password: ").strip()
    contact = input("Contact Number: ").strip()
    
    print("\nUser Type:")
    print("1. Property Manager")
    print("2. Realtor (Standalone)")
    print("3. Realtor (Under Property Manager)")
    
    user_type = input("Select type (1-3): ").strip()
    
    if user_type not in ["1", "2", "3"]:
        print("❌ Invalid selection")
        return
    
    # Create user in Supabase
    print(f"\n🚀 Creating user in Supabase...")
    result = create_user_in_supabase(email, password)
    
    if not result["success"]:
        print(f"❌ Failed to create user: {result['error']}")
        return
    
    print(f"✅ User created in Supabase: {result['email']}")
    print(f"   User ID: {result['user_id']}")
    
    # Now you need to create the user in your database
    print(f"\n📋 Next Steps:")
    print(f"1. Go to your Supabase Dashboard")
    print(f"2. Navigate to Authentication > Users")
    print(f"3. Find the user: {email}")
    print(f"4. Copy the User ID: {result['user_id']}")
    print(f"5. Use your admin panel to create the user record in your database")
    print(f"   with auth_user_id = '{result['user_id']}'")
    
    print(f"\n📝 User Details for Database:")
    print(f"   Name: {name}")
    print(f"   Email: {email}")
    print(f"   Contact: {contact}")
    print(f"   Auth User ID: {result['user_id']}")
    print(f"   User Type: {'Property Manager' if user_type == '1' else 'Realtor'}")

if __name__ == "__main__":
    main()
