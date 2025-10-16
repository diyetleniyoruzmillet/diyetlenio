"""
Base service class for all business logic operations.
"""
from abc import ABC, abstractmethod
from django.db import transaction
from django.core.exceptions import ValidationError
from typing import Any, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class ServiceResult:
    """Service operation result wrapper."""
    
    def __init__(self, success: bool = True, data: Any = None, error: str = None, errors: Dict = None):
        self.success = success
        self.data = data
        self.error = error
        self.errors = errors or {}
    
    def __bool__(self):
        return self.success
    
    @classmethod
    def success_result(cls, data: Any = None):
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str, errors: Dict = None):
        return cls(success=False, error=error, errors=errors)


class BaseService(ABC):
    """Base class for all business logic services."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def log_operation(self, operation: str, **kwargs):
        """Log service operations."""
        self.logger.info(f"{operation}: {kwargs}")
    
    def log_error(self, operation: str, error: Exception, **kwargs):
        """Log service errors."""
        self.logger.error(f"{operation} failed: {str(error)}", extra=kwargs)
    
    @transaction.atomic
    def execute_with_transaction(self, operation_func, *args, **kwargs):
        """Execute operation within database transaction."""
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            self.log_error("Transaction operation", e)
            raise
    
    def validate_input(self, data: Dict, required_fields: List[str]) -> ServiceResult:
        """Validate required input fields."""
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return ServiceResult.error_result(
                error="Missing required fields",
                errors={field: "This field is required" for field in missing_fields}
            )
        
        return ServiceResult.success_result()