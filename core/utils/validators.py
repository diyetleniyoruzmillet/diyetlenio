"""
Validation utility functions.
"""
import re
from typing import Optional, Tuple
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Turkish phone number format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return False, "Telefon numarası gereklidir"
    
    # Remove spaces and special characters
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Check Turkish mobile format
    if len(clean_phone) == 11 and clean_phone.startswith('0'):
        clean_phone = clean_phone[1:]
    
    if len(clean_phone) != 10:
        return False, "Telefon numarası 10 haneli olmalıdır"
    
    if not clean_phone.startswith(('50', '51', '52', '53', '54', '55', '56', '57', '58', '59')):
        return False, "Geçersiz telefon numarası formatı"
    
    return True, None


def validate_turkish_id(tc_no: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Turkish ID number (TC Kimlik No).
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not tc_no:
        return False, "TC Kimlik Numarası gereklidir"
    
    # Remove spaces and non-digits
    clean_tc = re.sub(r'[^\d]', '', tc_no)
    
    if len(clean_tc) != 11:
        return False, "TC Kimlik Numarası 11 haneli olmalıdır"
    
    if clean_tc[0] == '0':
        return False, "TC Kimlik Numarası 0 ile başlayamaz"
    
    # TC Kimlik validation algorithm
    try:
        digits = [int(d) for d in clean_tc]
        
        # Check sum of first 10 digits
        if sum(digits[:10]) % 10 != digits[10]:
            return False, "Geçersiz TC Kimlik Numarası"
        
        # Check algorithm for 10th digit
        odd_sum = sum(digits[i] for i in range(0, 9, 2))
        even_sum = sum(digits[i] for i in range(1, 8, 2))
        
        if (odd_sum * 7 - even_sum) % 10 != digits[9]:
            return False, "Geçersiz TC Kimlik Numarası"
            
        return True, None
        
    except (ValueError, IndexError):
        return False, "Geçersiz TC Kimlik Numarası formatı"


def validate_image_file(file) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded image file.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file:
        return False, "Dosya gereklidir"
    
    # Check file size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return False, "Dosya boyutu 5MB'dan büyük olamaz"
    
    # Check file extension
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
    
    if f'.{file_extension}' not in allowed_extensions:
        return False, f"Desteklenen formatlar: {', '.join(allowed_extensions)}"
    
    # Check MIME type
    allowed_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_mime_types:
        return False, "Geçersiz dosya tipi"
    
    return True, None


def validate_document_file(file) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded document file.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file:
        return False, "Dosya gereklidir"
    
    # Check file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        return False, "Dosya boyutu 10MB'dan büyük olamaz"
    
    # Check file extension
    allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png']
    file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
    
    if f'.{file_extension}' not in allowed_extensions:
        return False, f"Desteklenen formatlar: {', '.join(allowed_extensions)}"
    
    return True, None


def validate_email_format(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "E-posta adresi gereklidir"
    
    try:
        validate_email(email)
        return True, None
    except ValidationError:
        return False, "Geçersiz e-posta formatı"


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Şifre gereklidir"
    
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalıdır"
    
    if not re.search(r'[A-Z]', password):
        return False, "Şifre en az 1 büyük harf içermelidir"
    
    if not re.search(r'[a-z]', password):
        return False, "Şifre en az 1 küçük harf içermelidir"
    
    if not re.search(r'\d', password):
        return False, "Şifre en az 1 rakam içermelidir"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Şifre en az 1 özel karakter içermelidir"
    
    return True, None