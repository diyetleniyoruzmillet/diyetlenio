from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import Kullanici, Diyetisyen, DanisanSaglikVerisi, UzmanlikAlani
from .auth_service import AuthService


class UserService:
    
    @staticmethod
    def create_diyetisyen_profile(user, uzmanlik_alanlari=None, deneyim_yili=0, 
                                 egitim_bilgileri=None, sertifikalar=None):
        """Kullanıcı için diyetisyen profili oluştur"""
        
        if user.rol != 'diyetisyen':
            raise ValidationError("Sadece diyetisyen rolündeki kullanıcılar için profil oluşturulabilir.")
        
        with transaction.atomic():
            # Diyetisyen profili oluştur
            diyetisyen, created = Diyetisyen.objects.get_or_create(
                kullanici=user,
                defaults={
                    'deneyim_yili': deneyim_yili,
                    'egitim_bilgileri': egitim_bilgileri,
                    'sertifikalar': sertifikalar,
                    'onay_durumu': 'BEKLEMEDE',
                    'aktif': False
                }
            )
            
            # Uzmanlık alanları ekleme
            if uzmanlik_alanlari:
                for alan_adi in uzmanlik_alanlari:
                    uzmanlik_alani, _ = UzmanlikAlani.objects.get_or_create(
                        alan_adi=alan_adi
                    )
                    diyetisyen.uzmanlik_alanlari.add(uzmanlik_alani)
            
            return diyetisyen
    
    @staticmethod
    def approve_diyetisyen(diyetisyen_id, admin_user, onay_notlari=None):
        """Diyetisyen başvurusunu onayla"""
        
        if admin_user.rol != 'admin':
            raise ValidationError("Sadece admin kullanıcılar diyetisyen onaylayabilir.")
        
        try:
            diyetisyen = Diyetisyen.objects.get(kullanici_id=diyetisyen_id)
        except Diyetisyen.DoesNotExist:
            raise ValidationError("Diyetisyen bulunamadı.")
        
        diyetisyen.onay_durumu = 'ONAYLANDI'
        diyetisyen.onay_tarihi = timezone.now()
        diyetisyen.onaylayan_admin = admin_user
        diyetisyen.onay_notlari = onay_notlari
        diyetisyen.aktif = True
        diyetisyen.save()
        
        return diyetisyen
    
    @staticmethod
    def reject_diyetisyen(diyetisyen_id, admin_user, red_sebebi):
        """Diyetisyen başvurusunu reddet"""
        
        if admin_user.rol != 'admin':
            raise ValidationError("Sadece admin kullanıcılar diyetisyen reddedebilir.")
        
        try:
            diyetisyen = Diyetisyen.objects.get(kullanici_id=diyetisyen_id)
        except Diyetisyen.DoesNotExist:
            raise ValidationError("Diyetisyen bulunamadı.")
        
        diyetisyen.onay_durumu = 'REDDEDILDI'
        diyetisyen.onay_tarihi = timezone.now()
        diyetisyen.onaylayan_admin = admin_user
        diyetisyen.onay_notlari = red_sebebi
        diyetisyen.aktif = False
        diyetisyen.save()
        
        return diyetisyen
    
    @staticmethod
    def update_user_profile(user, **kwargs):
        """Kullanıcı profil bilgilerini güncelle"""
        
        allowed_fields = ['ad', 'soyad', 'telefon']
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        user.save()
        return user
    
    @staticmethod
    def deactivate_user(user_id, admin_user, reason=None):
        """Kullanıcıyı deaktif et"""
        
        if admin_user.rol != 'admin':
            raise ValidationError("Sadece admin kullanıcılar başka kullanıcıları deaktif edebilir.")
        
        try:
            user = Kullanici.objects.get(id=user_id)
        except Kullanici.DoesNotExist:
            raise ValidationError("Kullanıcı bulunamadı.")
        
        if user.rol == 'admin':
            raise ValidationError("Admin kullanıcılar deaktif edilemez.")
        
        user.is_active = False
        user.save()
        
        # Eğer diyetisyen ise profilini de deaktif et
        if user.rol == 'diyetisyen':
            try:
                diyetisyen = user.diyetisyen
                diyetisyen.aktif = False
                diyetisyen.save()
            except:
                pass
        
        return user
    
    @staticmethod
    def create_danisan_saglik_verisi(danisan, **saglik_bilgileri):
        """Danışan için sağlık verisi oluştur"""
        
        if danisan.rol != 'danisan':
            raise ValidationError("Sadece danışan kullanıcılar için sağlık verisi oluşturulabilir.")
        
        saglik_verisi = DanisanSaglikVerisi.objects.create(
            danisan=danisan,
            **saglik_bilgileri
        )
        
        return saglik_verisi
    
    @staticmethod
    def get_user_statistics():
        """Platform kullanıcı istatistiklerini getir"""
        
        stats = {
            'total_users': Kullanici.objects.count(),
            'active_users': Kullanici.objects.filter(is_active=True).count(),
            'danisan_count': Kullanici.objects.filter(rol='danisan').count(),
            'diyetisyen_count': Kullanici.objects.filter(rol='diyetisyen').count(),
            'admin_count': Kullanici.objects.filter(rol='admin').count(),
            'pending_diyetisyen': Diyetisyen.objects.filter(onay_durumu='BEKLEMEDE').count(),
            'approved_diyetisyen': Diyetisyen.objects.filter(onay_durumu='ONAYLANDI').count(),
        }
        
        return stats
    
    @staticmethod
    def search_users(query, user_type=None, admin_user=None):
        """Kullanıcı arama"""
        
        if admin_user and admin_user.rol != 'admin':
            raise ValidationError("Sadece admin kullanıcılar arama yapabilir.")
        
        queryset = Kullanici.objects.filter(
            models.Q(ad__icontains=query) |
            models.Q(soyad__icontains=query) |
            models.Q(e_posta__icontains=query)
        )
        
        if user_type:
            queryset = queryset.filter(rol=user_type)
        
        return queryset.order_by('ad', 'soyad')
    
    @staticmethod
    def get_diyetisyen_by_uzmanlik(uzmanlik_alan_adi):
        """Uzmanlık alanına göre diyetisyen ara"""
        
        return Diyetisyen.objects.filter(
            uzmanlik_alanlari__alan_adi__icontains=uzmanlik_alan_adi,
            onay_durumu='ONAYLANDI',
            aktif=True
        ).select_related('kullanici').distinct()
    
    @staticmethod
    def get_user_full_profile(user):
        """Kullanıcının tam profil bilgilerini getir"""
        
        profile = {
            'user': user,
            'permissions': AuthService.get_user_permissions(user)
        }
        
        # Diyetisyen ise diyetisyen bilgilerini ekle
        if user.rol == 'diyetisyen':
            try:
                profile['diyetisyen'] = user.diyetisyen
            except:
                profile['diyetisyen'] = None
        
        # Danışan ise sağlık verilerini ekle
        elif user.rol == 'danisan':
            profile['saglik_verileri'] = DanisanSaglikVerisi.objects.filter(
                danisan=user
            ).order_by('-kayit_tarihi')
        
        return profile