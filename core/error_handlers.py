"""
Error handling utilities and decorators.
"""
import functools
import logging
from typing import Callable, Any, Optional, Type, Union
from django.http import JsonResponse
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

from .exceptions import DiyetlenioException, ServiceUnavailableException

logger = logging.getLogger(__name__)


def handle_service_errors(
    default_message: str = "Service error occurred",
    log_errors: bool = True,
    reraise_exceptions: Optional[tuple] = None
):
    """
    Decorator to handle service layer errors consistently.
    
    Args:
        default_message: Default error message if none provided
        log_errors: Whether to log errors
        reraise_exceptions: Tuple of exception types to reraise instead of handling
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                # Reraise specific exceptions if specified
                if reraise_exceptions and isinstance(e, reraise_exceptions):
                    raise
                
                # Log error if enabled
                if log_errors:
                    logger.error(
                        f"Service error in {func.__name__}: {str(e)}",
                        extra={
                            'function': func.__name__,
                            'args': args,
                            'kwargs': kwargs,
                            'exception_type': type(e).__name__
                        },
                        exc_info=True
                    )
                
                # Handle custom exceptions
                if isinstance(e, DiyetlenioException):
                    raise e
                
                # Convert other exceptions to service unavailable
                raise ServiceUnavailableException(default_message)
        
        return wrapper
    return decorator


def handle_api_errors(
    default_message: str = "API error occurred",
    success_status: int = status.HTTP_200_OK
):
    """
    Decorator to handle API view errors and return consistent responses.
    
    Args:
        default_message: Default error message
        success_status: HTTP status for successful responses
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                result = func(self, request, *args, **kwargs)
                
                # If result is already a Response, return as-is
                if isinstance(result, Response):
                    return result
                
                # Create success response
                return Response({
                    'success': True,
                    'data': result
                }, status=success_status)
                
            except DiyetlenioException as e:
                # Custom exceptions are handled by the exception handler
                raise e
            
            except Exception as e:
                logger.error(
                    f"API error in {func.__name__}: {str(e)}",
                    extra={
                        'function': func.__name__,
                        'path': request.path,
                        'method': request.method,
                        'user': str(request.user) if request.user.is_authenticated else 'Anonymous'
                    },
                    exc_info=True
                )
                
                # Return generic error response
                return Response({
                    'error': {
                        'message': default_message,
                        'code': 'API_ERROR'
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return wrapper
    return decorator


def handle_database_errors(
    default_message: str = "Database operation failed"
):
    """
    Decorator to handle database-related errors.
    
    Args:
        default_message: Default error message
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                from django.db import IntegrityError, DatabaseError
                
                if isinstance(e, IntegrityError):
                    logger.error(f"Database integrity error in {func.__name__}: {str(e)}")
                    raise DiyetlenioException(
                        message="Data integrity constraint violation",
                        code="INTEGRITY_ERROR",
                        status_code=status.HTTP_409_CONFLICT
                    )
                
                elif isinstance(e, DatabaseError):
                    logger.error(f"Database error in {func.__name__}: {str(e)}")
                    raise ServiceUnavailableException(default_message)
                
                else:
                    # Re-raise non-database exceptions
                    raise e
        
        return wrapper
    return decorator


class ErrorContext:
    """Context manager for error handling with additional context."""
    
    def __init__(self, operation: str, user_id: Optional[int] = None, 
                 additional_context: Optional[dict] = None):
        self.operation = operation
        self.user_id = user_id
        self.additional_context = additional_context or {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            context = {
                'operation': self.operation,
                'user_id': self.user_id,
                **self.additional_context
            }
            
            logger.error(
                f"Error in operation '{self.operation}': {str(exc_val)}",
                extra=context,
                exc_info=True
            )
        
        # Don't suppress the exception
        return False


def safe_execute(func: Callable, *args, default_return: Any = None, 
                log_errors: bool = True, **kwargs) -> Any:
    """
    Safely execute a function and return default value on error.
    
    Args:
        func: Function to execute
        args: Positional arguments
        default_return: Value to return on error
        log_errors: Whether to log errors
        kwargs: Keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(
                f"Safe execution failed for {func.__name__}: {str(e)}",
                exc_info=True
            )
        return default_return


def validate_and_handle_errors(validation_func: Callable, 
                              error_message: str = "Validation failed") -> Callable:
    """
    Decorator to validate input and handle validation errors.
    
    Args:
        validation_func: Function that takes the same arguments and returns (is_valid, errors)
        error_message: Base error message
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            is_valid, errors = validation_func(*args, **kwargs)
            
            if not is_valid:
                from .exceptions import ValidationException
                raise ValidationException(
                    message=error_message,
                    field_errors=errors
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global error tracking for monitoring
class ErrorTracker:
    """Simple error tracker for monitoring purposes."""
    
    def __init__(self):
        self._error_counts = {}
    
    def track_error(self, error_type: str, context: Optional[dict] = None):
        """Track an error occurrence."""
        if error_type not in self._error_counts:
            self._error_counts[error_type] = 0
        
        self._error_counts[error_type] += 1
        
        # Log for external monitoring systems
        logger.warning(
            f"Error tracked: {error_type}",
            extra={
                'error_type': error_type,
                'count': self._error_counts[error_type],
                'context': context or {}
            }
        )
    
    def get_error_counts(self) -> dict:
        """Get current error counts."""
        return self._error_counts.copy()
    
    def reset_counts(self):
        """Reset error counts."""
        self._error_counts.clear()


# Global error tracker instance
error_tracker = ErrorTracker()


# Django view error handler for non-DRF views
def handle_django_view_errors(view_func):
    """Decorator for Django views to handle errors consistently."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        
        except DiyetlenioException as e:
            error_tracker.track_error(e.code, {'status_code': e.status_code})
            
            return JsonResponse({
                'error': {
                    'message': e.message,
                    'code': e.code
                }
            }, status=e.status_code)
        
        except Exception as e:
            error_tracker.track_error('UNHANDLED_ERROR')
            
            logger.error(
                f"Unhandled error in view {view_func.__name__}: {str(e)}",
                extra={
                    'view': view_func.__name__,
                    'path': request.path,
                    'method': request.method
                },
                exc_info=True
            )
            
            if settings.DEBUG:
                raise  # Re-raise in debug mode
            
            return JsonResponse({
                'error': {
                    'message': 'Internal server error',
                    'code': 'INTERNAL_SERVER_ERROR'
                }
            }, status=500)
    
    return wrapper