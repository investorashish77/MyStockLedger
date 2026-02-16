"""
Authentication Service
Handles user registration, login, and password management
"""

import hashlib
import re
from typing import Optional, Tuple
from database.db_manager import DatabaseManager

class AuthService:
    """Handles user authentication"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def validate_mobile_number(self, mobile: str) -> bool:
        """Validate mobile number format (10 digits)"""
        # Remove any spaces or special characters
        clean_mobile = re.sub(r'[^\d]', '', mobile)
        return len(clean_mobile) == 10
    
    def validate_password(self, password: str) -> Tuple[bool, str]:
        """
        Validate password strength
        Returns: (is_valid, error_message)
        """
        if len(password) < 6:
            return False, "Password must be at least 6 characters"
        
        return True, ""
    
    def register_user(self, mobile_number: str, name: str, password: str, 
                     email: str = None) -> Tuple[bool, str, Optional[int]]:
        """
        Register a new user
        Returns: (success, message, user_id)
        """
        # Validate mobile number
        if not self.validate_mobile_number(mobile_number):
            return False, "Invalid mobile number. Must be 10 digits.", None
        
        # Clean mobile number
        clean_mobile = re.sub(r'[^\d]', '', mobile_number)
        
        # Validate password
        is_valid, error_msg = self.validate_password(password)
        if not is_valid:
            return False, error_msg, None
        
        # Check if user already exists
        existing_user = self.db.get_user_by_mobile(clean_mobile)
        if existing_user:
            return False, "User with this mobile number already exists", None
        
        # Hash password
        password_hash = self.hash_password(password)
        
        try:
            # Create user
            user_id = self.db.create_user(clean_mobile, name, password_hash, email)
            return True, "Registration successful", user_id
        except Exception as e:
            return False, f"Registration failed: {str(e)}", None
    
    def login(self, mobile_number: str, password: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Login user
        Returns: (success, message, user_data)
        """
        # Clean mobile number
        clean_mobile = re.sub(r'[^\d]', '', mobile_number)
        
        # Get user from database
        user = self.db.get_user_by_mobile(clean_mobile)
        
        if not user:
            return False, "User not found", None
        
        # Verify password
        password_hash = self.hash_password(password)
        
        if password_hash != user['password_hash']:
            return False, "Incorrect password", None
        
        # Remove password hash from returned data
        user_data = {
            'user_id': user['user_id'],
            'mobile_number': user['mobile_number'],
            'name': user['name'],
            'email': user['email']
        }
        
        return True, "Login successful", user_data
