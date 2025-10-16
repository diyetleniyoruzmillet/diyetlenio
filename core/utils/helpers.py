"""
General helper utility functions.
"""
import random
import string
import hashlib
import uuid
from typing import Any, Dict, Optional
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils.text import slugify
from django.db.models import QuerySet


def generate_random_string(length: int = 8, include_numbers: bool = True, 
                          include_symbols: bool = False) -> str:
    """
    Generate a random string with specified parameters.
    
    Args:
        length: Length of the string
        include_numbers: Include numbers in the string
        include_symbols: Include symbols in the string
        
    Returns:
        Random string
    """
    characters = string.ascii_letters
    
    if include_numbers:
        characters += string.digits
    
    if include_symbols:
        characters += "!@#$%^&*"
    
    return ''.join(random.choice(characters) for _ in range(length))


def create_slug(text: str, max_length: int = 50) -> str:
    """
    Create a URL-friendly slug from text.
    
    Args:
        text: Text to convert to slug
        max_length: Maximum length of the slug
        
    Returns:
        URL-friendly slug
    """
    # Handle Turkish characters
    turkish_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    for turkish_char, english_char in turkish_map.items():
        text = text.replace(turkish_char, english_char)
    
    slug = slugify(text)
    
    if len(slug) > max_length:
        slug = slug[:max_length]
        # Don't cut in the middle of a word
        if ' ' in slug:
            slug = slug.rsplit(' ', 1)[0]
    
    return slug


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename while preserving the extension.
    
    Args:
        original_filename: Original filename
        
    Returns:
        Unique filename
    """
    name, extension = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, '')
    unique_id = str(uuid.uuid4().hex)[:8]
    timestamp = str(int(random.random() * 1000000))
    
    if extension:
        return f"{unique_id}_{timestamp}.{extension}"
    else:
        return f"{unique_id}_{timestamp}"


def paginate_queryset(queryset: QuerySet, page_number: int, per_page: int = 20) -> Dict[str, Any]:
    """
    Paginate a Django queryset.
    
    Args:
        queryset: Django queryset to paginate
        page_number: Page number to retrieve
        per_page: Number of items per page
        
    Returns:
        Dictionary with pagination info and results
    """
    paginator = Paginator(queryset, per_page)
    
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    
    return {
        'results': page.object_list,
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'current_page': page.number,
        'has_next': page.has_next(),
        'has_previous': page.has_previous(),
        'next_page_number': page.next_page_number() if page.has_next() else None,
        'previous_page_number': page.previous_page_number() if page.has_previous() else None,
    }


def get_client_ip(request) -> str:
    """
    Get client IP address from Django request.
    
    Args:
        request: Django request object
        
    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    
    return ip


def generate_hash(text: str, salt: Optional[str] = None) -> str:
    """
    Generate SHA256 hash of text with optional salt.
    
    Args:
        text: Text to hash
        salt: Optional salt to add to hash
        
    Returns:
        SHA256 hash string
    """
    if salt:
        text = f"{text}{salt}"
    
    return hashlib.sha256(text.encode()).hexdigest()


def format_currency(amount: float, currency: str = 'TL') -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Amount to format
        currency: Currency symbol
        
    Returns:
        Formatted currency string
    """
    return f"{amount:,.2f} {currency}"


def calculate_percentage(part: float, total: float) -> float:
    """
    Calculate percentage safely (handles division by zero).
    
    Args:
        part: Part value
        total: Total value
        
    Returns:
        Percentage value
    """
    if total == 0:
        return 0.0
    
    return round((part / total) * 100, 2)


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Truncate text to specified length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_dict_get(dictionary: Dict, key_path: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value using dot notation.
    
    Args:
        dictionary: Dictionary to search
        key_path: Dot-separated key path (e.g., 'user.profile.name')
        default: Default value if key not found
        
    Returns:
        Value at key path or default
    """
    keys = key_path.split('.')
    value = dictionary
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default