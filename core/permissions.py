"""
Advanced role-based permission system for Diyetlenio
"""
from typing import Dict, List, Optional, Tuple, Any
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from enum import Enum
import logging

from .models import Kullanici, Rol, Diyetisyen, Randevu, OdemeHareketi

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User role constants"""
    ADMIN = 'admin'
    DIETITIAN = 'diyetisyen'
    PATIENT = 'danisan'


class Permission(Enum):
    """System permissions"""
    # User management
    VIEW_USERS = 'view_users'
    CREATE_USERS = 'create_users'
    EDIT_USERS = 'edit_users'
    DELETE_USERS = 'delete_users'
    
    # Appointment management
    VIEW_APPOINTMENTS = 'view_appointments'
    CREATE_APPOINTMENTS = 'create_appointments'
    EDIT_APPOINTMENTS = 'edit_appointments'
    CANCEL_APPOINTMENTS = 'cancel_appointments'
    APPROVE_APPOINTMENTS = 'approve_appointments'
    
    # Dietitian management
    VIEW_DIETITIANS = 'view_dietitians'
    APPROVE_DIETITIANS = 'approve_dietitians'
    REJECT_DIETITIANS = 'reject_dietitians'
    
    # Payment management
    VIEW_PAYMENTS = 'view_payments'
    PROCESS_PAYMENTS = 'process_payments'
    REFUND_PAYMENTS = 'refund_payments'
    
    # System administration
    VIEW_SYSTEM_LOGS = 'view_system_logs'
    MANAGE_SYSTEM_SETTINGS = 'manage_system_settings'
    SEND_BULK_NOTIFICATIONS = 'send_bulk_notifications'
    
    # Content management
    CREATE_ARTICLES = 'create_articles'
    EDIT_ARTICLES = 'edit_articles'
    PUBLISH_ARTICLES = 'publish_articles'
    DELETE_ARTICLES = 'delete_articles'


class RolePermissionMatrix:
    """Define permissions for each role"""
    
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: [
            # Full access to everything
            Permission.VIEW_USERS,
            Permission.CREATE_USERS,
            Permission.EDIT_USERS,
            Permission.DELETE_USERS,
            Permission.VIEW_APPOINTMENTS,
            Permission.CREATE_APPOINTMENTS,
            Permission.EDIT_APPOINTMENTS,
            Permission.CANCEL_APPOINTMENTS,
            Permission.APPROVE_APPOINTMENTS,
            Permission.VIEW_DIETITIANS,
            Permission.APPROVE_DIETITIANS,
            Permission.REJECT_DIETITIANS,
            Permission.VIEW_PAYMENTS,
            Permission.PROCESS_PAYMENTS,
            Permission.REFUND_PAYMENTS,
            Permission.VIEW_SYSTEM_LOGS,
            Permission.MANAGE_SYSTEM_SETTINGS,
            Permission.SEND_BULK_NOTIFICATIONS,
            Permission.CREATE_ARTICLES,
            Permission.EDIT_ARTICLES,
            Permission.PUBLISH_ARTICLES,
            Permission.DELETE_ARTICLES,
        ],
        
        UserRole.DIETITIAN: [
            # Dietitian-specific permissions
            Permission.VIEW_APPOINTMENTS,  # Only their own
            Permission.CREATE_APPOINTMENTS,  # For their patients
            Permission.EDIT_APPOINTMENTS,  # Only their own
            Permission.CANCEL_APPOINTMENTS,  # Only their own
            Permission.APPROVE_APPOINTMENTS,  # Only their own
            Permission.VIEW_PAYMENTS,  # Only their own
            Permission.CREATE_ARTICLES,
            Permission.EDIT_ARTICLES,  # Only their own
        ],
        
        UserRole.PATIENT: [
            # Patient-specific permissions
            Permission.VIEW_APPOINTMENTS,  # Only their own
            Permission.CREATE_APPOINTMENTS,  # Make appointments
            Permission.CANCEL_APPOINTMENTS,  # Only their own
            Permission.VIEW_PAYMENTS,  # Only their own
        ]
    }


class PermissionChecker:
    """Service for checking user permissions"""
    
    @staticmethod
    def has_permission(user: Kullanici, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        try:
            if not user or not user.is_authenticated:
                return False
            
            # Superuser has all permissions
            if user.is_superuser:
                return True
            
            # Get user role
            user_role = PermissionChecker.get_user_role(user)
            if not user_role:
                return False
            
            # Check role permissions
            role_permissions = RolePermissionMatrix.ROLE_PERMISSIONS.get(user_role, [])
            return permission in role_permissions
            
        except Exception as e:
            logger.error(f"Permission check failed for user {user.id}: {str(e)}")
            return False
    
    @staticmethod
    def get_user_role(user: Kullanici) -> Optional[UserRole]:
        """Get user role enum"""
        try:
            if not user or not hasattr(user, 'rol') or not user.rol:
                return None
            
            role_name = user.rol.rol_adi.lower()
            
            if role_name == 'admin':
                return UserRole.ADMIN
            elif role_name == 'diyetisyen':
                return UserRole.DIETITIAN
            elif role_name == 'danisan':
                return UserRole.PATIENT
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user role for user {user.id}: {str(e)}")
            return None
    
    @staticmethod
    def can_access_user_data(requesting_user: Kullanici, target_user: Kullanici) -> bool:
        """Check if requesting user can access target user's data"""
        try:
            # Users can always access their own data
            if requesting_user.id == target_user.id:
                return True
            
            # Admin can access anyone's data
            if PermissionChecker.has_permission(requesting_user, Permission.VIEW_USERS):
                return True
            
            # Dietitians can access their patients' data
            if PermissionChecker.get_user_role(requesting_user) == UserRole.DIETITIAN:
                return PermissionChecker._dietitian_can_access_patient(requesting_user, target_user)
            
            return False
            
        except Exception as e:
            logger.error(f"User data access check failed: {str(e)}")
            return False
    
    @staticmethod
    def can_access_appointment(user: Kullanici, randevu: Randevu) -> bool:
        """Check if user can access appointment data"""
        try:
            # Admin can access all appointments
            if PermissionChecker.has_permission(user, Permission.VIEW_APPOINTMENTS) and \
               PermissionChecker.get_user_role(user) == UserRole.ADMIN:
                return True
            
            # Users can access their own appointments
            if user.id == randevu.danisan.id:
                return True
            
            # Dietitians can access their appointments
            if hasattr(user, 'diyetisyen') and user.diyetisyen.id == randevu.diyetisyen.id:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Appointment access check failed: {str(e)}")
            return False
    
    @staticmethod
    def can_modify_appointment(user: Kullanici, randevu: Randevu) -> bool:
        """Check if user can modify appointment"""
        try:
            # Admin can modify all appointments
            if PermissionChecker.has_permission(user, Permission.EDIT_APPOINTMENTS) and \
               PermissionChecker.get_user_role(user) == UserRole.ADMIN:
                return True
            
            # Dietitians can modify their appointments
            if hasattr(user, 'diyetisyen') and user.diyetisyen.id == randevu.diyetisyen.id:
                return PermissionChecker.has_permission(user, Permission.EDIT_APPOINTMENTS)
            
            return False
            
        except Exception as e:
            logger.error(f"Appointment modify check failed: {str(e)}")
            return False
    
    @staticmethod
    def can_cancel_appointment(user: Kullanici, randevu: Randevu) -> bool:
        """Check if user can cancel appointment"""
        try:
            # Admin can cancel all appointments
            if PermissionChecker.has_permission(user, Permission.CANCEL_APPOINTMENTS) and \
               PermissionChecker.get_user_role(user) == UserRole.ADMIN:
                return True
            
            # Patients can cancel their own appointments
            if user.id == randevu.danisan.id:
                return PermissionChecker.has_permission(user, Permission.CANCEL_APPOINTMENTS)
            
            # Dietitians can cancel their appointments
            if hasattr(user, 'diyetisyen') and user.diyetisyen.id == randevu.diyetisyen.id:
                return PermissionChecker.has_permission(user, Permission.CANCEL_APPOINTMENTS)
            
            return False
            
        except Exception as e:
            logger.error(f"Appointment cancel check failed: {str(e)}")
            return False
    
    @staticmethod
    def can_access_payment_data(user: Kullanici, odeme: OdemeHareketi) -> bool:
        """Check if user can access payment data"""
        try:
            # Admin can access all payment data
            if PermissionChecker.has_permission(user, Permission.VIEW_PAYMENTS) and \
               PermissionChecker.get_user_role(user) == UserRole.ADMIN:
                return True
            
            # Patients can access their own payments
            if user.id == odeme.danisan.id:
                return True
            
            # Dietitians can access payments for their services
            if hasattr(user, 'diyetisyen') and user.diyetisyen.id == odeme.diyetisyen.id:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Payment access check failed: {str(e)}")
            return False
    
    @staticmethod
    def _dietitian_can_access_patient(dietitian_user: Kullanici, patient_user: Kullanici) -> bool:
        """Check if dietitian can access patient data (if they have active relationship)"""
        try:
            from .models import DanisanDiyetisyenEslesme
            
            if not hasattr(dietitian_user, 'diyetisyen'):
                return False
            
            # Check if there's an active relationship
            return DanisanDiyetisyenEslesme.objects.filter(
                diyetisyen=dietitian_user.diyetisyen,
                danisan=patient_user
            ).exists()
            
        except Exception:
            return False


# DRF Permission Classes
class IsAdminUser(BasePermission):
    """Permission class for admin-only access"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            PermissionChecker.get_user_role(request.user) == UserRole.ADMIN
        )


class IsDietitianUser(BasePermission):
    """Permission class for dietitian access"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            PermissionChecker.get_user_role(request.user) == UserRole.DIETITIAN
        )


class IsPatientUser(BasePermission):
    """Permission class for patient access"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            PermissionChecker.get_user_role(request.user) == UserRole.PATIENT
        )


class HasSpecificPermission(BasePermission):
    """Permission class that requires a specific permission"""
    
    required_permission = None
    
    def has_permission(self, request, view):
        if not self.required_permission:
            return False
        
        return (
            request.user and 
            request.user.is_authenticated and
            PermissionChecker.has_permission(request.user, self.required_permission)
        )


class CanAccessUserData(BasePermission):
    """Permission class for user data access"""
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Kullanici):
            return PermissionChecker.can_access_user_data(request.user, obj)
        return False


class CanAccessAppointment(BasePermission):
    """Permission class for appointment access"""
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Randevu):
            return PermissionChecker.can_access_appointment(request.user, obj)
        return False


class CanModifyAppointment(BasePermission):
    """Permission class for appointment modification"""
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Randevu):
            if request.method in ['PUT', 'PATCH']:
                return PermissionChecker.can_modify_appointment(request.user, obj)
            elif request.method == 'DELETE':
                return PermissionChecker.can_cancel_appointment(request.user, obj)
        return False


class CanAccessPaymentData(BasePermission):
    """Permission class for payment data access"""
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, OdemeHareketi):
            return PermissionChecker.can_access_payment_data(request.user, obj)
        return False


# Permission decorators for function-based views
def require_permission(permission: Permission):
    """Decorator to require specific permission for view access"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not PermissionChecker.has_permission(request.user, permission):
                from django.http import JsonResponse
                return JsonResponse({
                    'error': {
                        'message': 'Permission denied',
                        'code': 'PERMISSION_DENIED',
                        'required_permission': permission.value
                    }
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(required_role: UserRole):
    """Decorator to require specific role for view access"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            user_role = PermissionChecker.get_user_role(request.user)
            if user_role != required_role:
                from django.http import JsonResponse
                return JsonResponse({
                    'error': {
                        'message': 'Access denied for your role',
                        'code': 'ROLE_ACCESS_DENIED',
                        'required_role': required_role.value
                    }
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_object_permission(permission_func):
    """Decorator to require object-level permission"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # This would need to be customized based on how you pass objects to views
            # For now, it's a placeholder structure
            obj = kwargs.get('obj')  # You'd need to adapt this
            if obj and not permission_func(request.user, obj):
                from django.http import JsonResponse
                return JsonResponse({
                    'error': {
                        'message': 'Permission denied for this object',
                        'code': 'OBJECT_PERMISSION_DENIED'
                    }
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Utility functions
def get_user_permissions(user: Kullanici) -> List[Permission]:
    """Get all permissions for a user"""
    user_role = PermissionChecker.get_user_role(user)
    if not user_role:
        return []
    
    return RolePermissionMatrix.ROLE_PERMISSIONS.get(user_role, [])


def check_multiple_permissions(user: Kullanici, permissions: List[Permission], 
                              require_all: bool = True) -> bool:
    """Check multiple permissions for a user"""
    if require_all:
        return all(PermissionChecker.has_permission(user, perm) for perm in permissions)
    else:
        return any(PermissionChecker.has_permission(user, perm) for perm in permissions)