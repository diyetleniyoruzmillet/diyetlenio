from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import Kullanici


class AuthService:
    
    @staticmethod
    def login_user(e_posta, password):
        """Kullanıcı girişi"""
        user = authenticate(username=e_posta, password=password)
        
        if not user:
            raise ValidationError("Geçersiz email veya şifre.")
        
        if not user.is_active:
            raise ValidationError("Kullanıcı hesabı deaktif durumda.")
        
        # JWT token oluştur
        refresh = RefreshToken.for_user(user)
        
        return {
            'user': user,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }
    
    @staticmethod
    def register_user(e_posta, password, ad, soyad, telefon=None, rol_adi='danisan'):
        """Yeni kullanıcı kaydı"""
        from core.models import Rol
        
        # Email kontrolü
        if Kullanici.objects.filter(e_posta=e_posta).exists():
            raise ValidationError("Bu email adresi zaten kayıtlı.")
        
        # Rol kontrolü
        if rol_adi not in ['danisan', 'diyetisyen']:
            raise ValidationError("Geçersiz rol.")
        
        # Rol nesnesini bul veya oluştur
        rol, created = Rol.objects.get_or_create(rol_adi=rol_adi)
        
        # Kullanıcı oluştur with proper name capitalization
        user = Kullanici.objects.create_user(
            e_posta=e_posta,
            password=password,
            ad=ad.title(),
            soyad=soyad.title(),
            telefon=telefon,
            rol=rol
        )
        
        # JWT token oluştur
        refresh = RefreshToken.for_user(user)
        
        return {
            'user': user,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }
    
    @staticmethod
    def change_password(user, old_password, new_password):
        """Şifre değiştirme"""
        if not user.check_password(old_password):
            raise ValidationError("Mevcut şifre hatalı.")
        
        user.set_password(new_password)
        user.save()
        
        return user
    
    @staticmethod
    def is_admin(user):
        """Kullanıcının admin olup olmadığını kontrol et"""
        return user.rol.rol_adi == 'admin' and user.is_active
    
    @staticmethod
    def is_diyetisyen(user):
        """Kullanıcının diyetisyen olup olmadığını kontrol et"""
        return user.rol.rol_adi == 'diyetisyen' and user.is_active
    
    @staticmethod
    def is_danisan(user):
        """Kullanıcının danışan olup olmadığını kontrol et"""
        return user.rol.rol_adi == 'danisan' and user.is_active
    
    @staticmethod
    def get_user_permissions(user):
        """Kullanıcının yetkilerini getir"""
        permissions = {
            'is_admin': AuthService.is_admin(user),
            'is_diyetisyen': AuthService.is_diyetisyen(user),
            'is_danisan': AuthService.is_danisan(user),
        }
        
        # Rol bazlı özel yetkiler
        if permissions['is_admin']:
            permissions.update({
                'can_manage_users': True,
                'can_view_all_appointments': True,
                'can_reassign_appointments': True,
                'can_access_analytics': True,
            })
        
        elif permissions['is_diyetisyen']:
            permissions.update({
                'can_manage_own_appointments': True,
                'can_view_assigned_clients': True,
                'can_create_diet_plans': True,
                'can_write_notes': True,
            })
        
        elif permissions['is_danisan']:
            permissions.update({
                'can_book_appointments': True,
                'can_view_own_appointments': True,
                'can_access_diet_plans': True,
                'can_provide_feedback': True,
            })
        
        return permissions