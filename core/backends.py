"""
Custom authentication backend for Diyetlenio.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows login with email instead of username.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('e_posta')
        
        if username is None or password is None:
            return None
        
        try:
            # Try to get user by email
            user = User.objects.get(
                Q(e_posta__iexact=username) | Q(e_posta=username)
            )
            
            # Check password and if user is active
            if user.check_password(password) and user.aktif_mi:
                return user
                
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            User().set_password(password)
            return None
        
        return None

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
            return user if user.aktif_mi else None
        except User.DoesNotExist:
            return None