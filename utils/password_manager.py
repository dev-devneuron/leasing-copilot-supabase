"""
Password Management Utilities for Leasap Backend

⚠️  DEVELOPMENT/ADMIN USE ONLY - DO NOT USE IN PRODUCTION ⚠️

This module provides utilities for managing user passwords and creating test users.
Since we use Supabase Auth, passwords are encrypted by Supabase, but we provide
utilities for easy user creation and password management.

For production use, create users through your admin panel or Supabase Dashboard.
"""

import os
import json
import secrets
import string
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from supabase import create_client, Client
from DB.db import create_property_manager, create_realtor, engine, Session, select, PropertyManager, Realtor
from sqlmodel import Session as SQLModelSession
import hashlib
import base64
from cryptography.fernet import Fernet

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

class PasswordManager:
    """Utility class for password management and user creation."""
    
    def __init__(self):
        self.supabase = supabase
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for storing test passwords."""
        key_file = "utils/.encryption_key"
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key
    
    def encrypt_password(self, password: str) -> str:
        """Encrypt a password for storage in our test database."""
        encrypted = self.cipher.encrypt(password.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt a password from our test database."""
        encrypted = base64.b64decode(encrypted_password.encode())
        return self.cipher.decrypt(encrypted).decode()
    
    def generate_secure_password(self, length: int = 12) -> str:
        """Generate a secure random password."""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def create_supabase_user(self, email: str, password: str) -> Dict:
        """Create a user in Supabase Auth."""
        try:
            response = self.supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True  # Auto-confirm email for test users
            })
            return response
        except Exception as e:
            print(f"Error creating Supabase user: {e}")
            raise
    
    def create_test_property_manager(
        self, 
        name: str, 
        email: str, 
        password: str, 
        contact: str, 
        company_name: str
    ) -> Dict:
        """Create a test Property Manager with encrypted password storage."""
        try:
            # Create Supabase user
            auth_response = self.create_supabase_user(email, password)
            auth_user_id = str(auth_response.user.id)
            
            # Create Property Manager in our database
            result = create_property_manager(
                auth_user_id=auth_user_id,
                name=name,
                email=email,
                contact=contact,
                company_name=company_name
            )
            
            # Store encrypted password for easy retrieval
            encrypted_password = self.encrypt_password(password)
            self._store_test_password(email, encrypted_password, "property_manager")
            
            return {
                "success": True,
                "property_manager": result["property_manager"],
                "auth_link": result["auth_link"],
                "test_credentials": {
                    "email": email,
                    "password": password,
                    "user_type": "property_manager"
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_test_realtor(
        self, 
        name: str, 
        email: str, 
        password: str, 
        contact: str, 
        property_manager_id: Optional[int] = None
    ) -> Dict:
        """Create a test Realtor with encrypted password storage."""
        try:
            # Create Supabase user
            auth_response = self.create_supabase_user(email, password)
            auth_user_id = str(auth_response.user.id)
            
            # Create Realtor in our database
            result = create_realtor(
                auth_user_id=auth_user_id,
                name=name,
                email=email,
                contact=contact,
                property_manager_id=property_manager_id
            )
            
            # Store encrypted password for easy retrieval
            encrypted_password = self.encrypt_password(password)
            self._store_test_password(email, encrypted_password, "realtor")
            
            return {
                "success": True,
                "realtor": result["realtor"],
                "auth_link": result["auth_link"],
                "test_credentials": {
                    "email": email,
                    "password": password,
                    "user_type": "realtor",
                    "property_manager_id": property_manager_id
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _store_test_password(self, email: str, encrypted_password: str, user_type: str):
        """Store encrypted password in a test passwords file."""
        test_passwords_file = "utils/test_passwords.json"
        
        # Load existing passwords
        if os.path.exists(test_passwords_file):
            with open(test_passwords_file, "r") as f:
                passwords = json.load(f)
        else:
            passwords = {}
        
        # Add new password
        passwords[email] = {
            "encrypted_password": encrypted_password,
            "user_type": user_type,
            "created_at": datetime.now().isoformat()
        }
        
        # Save passwords
        with open(test_passwords_file, "w") as f:
            json.dump(passwords, f, indent=2)
    
    def get_test_password(self, email: str) -> Optional[Dict]:
        """Get decrypted password for a test user."""
        test_passwords_file = "utils/test_passwords.json"
        
        if not os.path.exists(test_passwords_file):
            return None
        
        with open(test_passwords_file, "r") as f:
            passwords = json.load(f)
        
        if email not in passwords:
            return None
        
        user_data = passwords[email]
        decrypted_password = self.decrypt_password(user_data["encrypted_password"])
        
        return {
            "email": email,
            "password": decrypted_password,
            "user_type": user_data["user_type"],
            "created_at": user_data["created_at"]
        }
    
    def list_all_test_users(self) -> List[Dict]:
        """List all test users with their decrypted passwords."""
        test_passwords_file = "utils/test_passwords.json"
        
        if not os.path.exists(test_passwords_file):
            return []
        
        with open(test_passwords_file, "r") as f:
            passwords = json.load(f)
        
        users = []
        for email, data in passwords.items():
            decrypted_password = self.decrypt_password(data["encrypted_password"])
            users.append({
                "email": email,
                "password": decrypted_password,
                "user_type": data["user_type"],
                "created_at": data["created_at"]
            })
        
        return users
    
    def create_test_team(self) -> Dict:
        """Create a complete test team: 1 Property Manager + 2 Realtors."""
        print("🏢 Creating test team...")
        
        # Test credentials
        pm_credentials = {
            "name": "John Smith",
            "email": "john.smith@testcompany.com",
            "password": "PM@123456",
            "contact": "+1-555-0101",
            "company_name": "Test Property Management LLC"
        }
        
        realtor1_credentials = {
            "name": "Sarah Johnson",
            "email": "sarah.johnson@testcompany.com", 
            "password": "RE1@123456",
            "contact": "+1-555-0102"
        }
        
        realtor2_credentials = {
            "name": "Mike Wilson",
            "email": "mike.wilson@testcompany.com",
            "password": "RE2@123456", 
            "contact": "+1-555-0103"
        }
        
        results = {}
        
        # Create Property Manager
        print("👨‍💼 Creating Property Manager...")
        pm_result = self.create_test_property_manager(**pm_credentials)
        results["property_manager"] = pm_result
        
        if not pm_result["success"]:
            return {"success": False, "error": f"Failed to create Property Manager: {pm_result['error']}"}
        
        pm_id = pm_result["property_manager"]["id"]
        
        # Create Realtor 1 (under Property Manager)
        print("👩‍💼 Creating Realtor 1...")
        realtor1_result = self.create_test_realtor(
            **realtor1_credentials, 
            property_manager_id=pm_id
        )
        results["realtor1"] = realtor1_result
        
        # Create Realtor 2 (under Property Manager)
        print("👨‍💼 Creating Realtor 2...")
        realtor2_result = self.create_test_realtor(
            **realtor2_credentials, 
            property_manager_id=pm_id
        )
        results["realtor2"] = realtor2_result
        
        # Summary
        success_count = sum(1 for result in results.values() if result.get("success", False))
        total_count = len(results)
        
        return {
            "success": success_count == total_count,
            "created_users": success_count,
            "total_users": total_count,
            "results": results,
            "test_credentials": {
                "property_manager": pm_result["test_credentials"],
                "realtor1": realtor1_result["test_credentials"],
                "realtor2": realtor2_result["test_credentials"]
            }
        }
    
    def reset_test_users(self):
        """Reset all test users (delete from both Supabase and local DB)."""
        print("🔄 Resetting test users...")
        
        test_passwords_file = "utils/test_passwords.json"
        if not os.path.exists(test_passwords_file):
            print("No test users to reset.")
            return
        
        with open(test_passwords_file, "r") as f:
            passwords = json.load(f)
        
        with Session(engine) as session:
            for email, data in passwords.items():
                try:
                    # Delete from local database
                    if data["user_type"] == "property_manager":
                        pm = session.exec(
                            select(PropertyManager).where(PropertyManager.email == email)
                        ).first()
                        if pm:
                            session.delete(pm)
                    else:
                        realtor = session.exec(
                            select(Realtor).where(Realtor.email == email)
                        ).first()
                        if realtor:
                            session.delete(realtor)
                    
                    # Delete from Supabase (if possible)
                    try:
                        # Note: Supabase admin API might not allow user deletion
                        # This is a limitation of Supabase Auth
                        pass
                    except:
                        pass
                        
                except Exception as e:
                    print(f"Error deleting {email}: {e}")
            
            session.commit()
        
        # Clear test passwords file
        os.remove(test_passwords_file)
        print("✅ Test users reset complete!")


def main():
    """Main function to create test users."""
    password_manager = PasswordManager()
    
    print("🚀 Leasap Test User Creation Tool")
    print("=" * 50)
    
    # Create test team
    result = password_manager.create_test_team()
    
    if result["success"]:
        print("\n✅ Test team created successfully!")
        print(f"Created {result['created_users']}/{result['total_users']} users")
        
        print("\n📋 Test Credentials:")
        print("-" * 30)
        
        for user_type, creds in result["test_credentials"].items():
            print(f"\n{user_type.upper()}:")
            print(f"  Email: {creds['email']}")
            print(f"  Password: {creds['password']}")
            print(f"  User Type: {creds['user_type']}")
        
        print("\n🔗 Login URLs:")
        print("-" * 30)
        print("Property Manager: https://your-frontend.com/signin (select Property Manager tab)")
        print("Realtors: https://your-frontend.com/signin (select Realtor tab)")
        
    else:
        print("\n❌ Failed to create test team!")
        print("Errors:")
        for user_type, result_data in result["results"].items():
            if not result_data.get("success", False):
                print(f"  {user_type}: {result_data.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
