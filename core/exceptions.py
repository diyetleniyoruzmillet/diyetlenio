"""
Custom exceptions for the Diyetlenio application.
"""
from typing import Optional, Dict, Any
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


# Base Custom Exceptions
class DiyetlenioException(Exception):
    """Base exception for Diyetlenio application."""
    
    def __init__(self, message: str = "An error occurred", code: str = "GENERIC_ERROR", 
                 status_code: int = status.HTTP_400_BAD_REQUEST, details: Dict = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Business Logic Exceptions
class ValidationException(DiyetlenioException):
    """Validation error exception."""
    
    def __init__(self, message: str = "Validation failed", field_errors: Dict = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={'field_errors': field_errors or {}}
        )


class AuthenticationException(DiyetlenioException):
    """Authentication error exception."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationException(DiyetlenioException):
    """Authorization error exception."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN
        )


class ResourceNotFoundException(DiyetlenioException):
    """Resource not found exception."""
    
    def __init__(self, message: str = "Resource not found", resource_type: str = None):
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={'resource_type': resource_type}
        )


class BusinessLogicException(DiyetlenioException):
    """Business logic error exception."""
    
    def __init__(self, message: str = "Business logic error", business_code: str = None):
        super().__init__(
            message=message,
            code="BUSINESS_LOGIC_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={'business_code': business_code}
        )


class ConflictException(DiyetlenioException):
    """Resource conflict exception."""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT
        )


class RateLimitException(DiyetlenioException):
    """Rate limit exceeded exception."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={'retry_after': retry_after}
        )


class ServiceUnavailableException(DiyetlenioException):
    """Service unavailable exception."""
    
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# Domain-specific Exceptions
class AppointmentException(BusinessLogicException):
    """Appointment-related exception."""
    
    def __init__(self, message: str, appointment_code: str = None):
        super().__init__(message=message, business_code=appointment_code)


class PaymentException(BusinessLogicException):
    """Payment-related exception."""
    
    def __init__(self, message: str, payment_code: str = None):
        super().__init__(message=message, business_code=payment_code)


class UserException(BusinessLogicException):
    """User-related exception."""
    
    def __init__(self, message: str, user_code: str = None):
        super().__init__(message=message, business_code=user_code)


# Custom Exception Handler
def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that handles our custom exceptions
    and provides consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Handle our custom exceptions
    if isinstance(exc, DiyetlenioException):
        custom_response_data = {
            'error': {
                'message': exc.message,
                'code': exc.code,
                'timestamp': context['request'].META.get('HTTP_X_REQUEST_TIMESTAMP'),
                'details': exc.details
            }
        }
        
        # Log the exception
        logger.error(f"Custom exception: {exc.code} - {exc.message}", extra={
            'exception_code': exc.code,
            'status_code': exc.status_code,
            'details': exc.details,
            'path': context['request'].path,
            'method': context['request'].method,
            'user': str(context['request'].user) if context['request'].user.is_authenticated else 'Anonymous'
        })
        
        response = Response(custom_response_data, status=exc.status_code)
    
    # Handle other common Django/DRF exceptions with custom format
    elif response is not None:
        custom_response_data = {
            'error': {
                'message': 'Request failed',
                'code': 'REQUEST_ERROR',
                'timestamp': context['request'].META.get('HTTP_X_REQUEST_TIMESTAMP'),
                'details': response.data if response.data else {}
            }
        }
        
        # Specific handling for common DRF exceptions
        if response.status_code == status.HTTP_404_NOT_FOUND:
            custom_response_data['error']['message'] = 'Resource not found'
            custom_response_data['error']['code'] = 'RESOURCE_NOT_FOUND'
        
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            custom_response_data['error']['message'] = 'Authentication failed'
            custom_response_data['error']['code'] = 'AUTHENTICATION_ERROR'
        
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            custom_response_data['error']['message'] = 'Access denied'
            custom_response_data['error']['code'] = 'AUTHORIZATION_ERROR'
        
        elif response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            custom_response_data['error']['message'] = 'Method not allowed'
            custom_response_data['error']['code'] = 'METHOD_NOT_ALLOWED'
        
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            custom_response_data['error']['message'] = 'Bad request'
            custom_response_data['error']['code'] = 'BAD_REQUEST'
        
        response.data = custom_response_data
    
    # Handle unhandled exceptions
    else:
        logger.error(f"Unhandled exception: {str(exc)}", extra={
            'exception_type': type(exc).__name__,
            'path': context['request'].path,
            'method': context['request'].method,
            'user': str(context['request'].user) if context['request'].user.is_authenticated else 'Anonymous'
        })
        
        custom_response_data = {
            'error': {
                'message': 'Internal server error',
                'code': 'INTERNAL_SERVER_ERROR',
                'timestamp': context['request'].META.get('HTTP_X_REQUEST_TIMESTAMP'),
                'details': {}
            }
        }
        
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


# Error Response Helper Functions
def create_error_response(message: str, code: str, status_code: int = status.HTTP_400_BAD_REQUEST, 
                         details: Dict = None) -> Response:
    """Create a standardized error response."""
    response_data = {
        'error': {
            'message': message,
            'code': code,
            'details': details or {}
        }
    }
    return Response(response_data, status=status_code)


def create_validation_error_response(field_errors: Dict) -> Response:
    """Create a validation error response."""
    return create_error_response(
        message="Validation failed",
        code="VALIDATION_ERROR",
        status_code=status.HTTP_400_BAD_REQUEST,
        details={'field_errors': field_errors}
    )


def create_success_response(data: Any = None, message: str = "Success") -> Response:
    """Create a standardized success response."""
    response_data = {
        'success': True,
        'message': message,
        'data': data
    }
    return Response(response_data, status=status.HTTP_200_OK)