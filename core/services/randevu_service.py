from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from core.models import (
    Randevu, Musaitlik, DanisanDiyetisyenEslesme, 
    RandevuMudahaleTalebi, Kullanici
)


class RandevuService:
    
    @staticmethod
    def create_randevu(danisan, tarih, saat, randevu_turu='ONLINE', notlar=None):
        """Yeni randevu oluştur ve otomatik eşleştir"""
        
        with transaction.atomic():
            # Randevu oluştur
            randevu = Randevu.objects.create(
                danisan=danisan,
                tarih=tarih,
                saat=saat,
                randevu_turu=randevu_turu,
                durum='BEKLEMEDE',
                notlar=notlar
            )
            
            # Otomatik eşleştirme
            RandevuService._otomatik_eslestir(randevu)
            
            return randevu
    
    @staticmethod
    def _otomatik_eslestir(randevu):
        """Randevu için uygun diyetisyen bul ve eşleştir"""
        
        # Önce danışanın mevcut eşleşmesi var mı kontrol et
        existing_match = DanisanDiyetisyenEslesme.objects.filter(
            danisan=randevu.danisan,
            durum='AKTIF'
        ).first()
        
        if existing_match:
            # Mevcut diyetisyenin müsaitliğini kontrol et
            musaitlik = Musaitlik.objects.filter(
                diyetisyen=existing_match.diyetisyen,
                tarih=randevu.tarih,
                saat=randevu.saat,
                musait=True
            ).first()
            
            if musaitlik:
                randevu.diyetisyen = existing_match.diyetisyen
                randevu.durum = 'ONAYLANDI'
                randevu.save()
                
                # Müsaitliği güncelle
                musaitlik.musait = False
                musaitlik.save()
                return
        
        # Yeni diyetisyen ara
        available_dietitians = Musaitlik.objects.filter(
            tarih=randevu.tarih,
            saat=randevu.saat,
            musait=True
        ).select_related('diyetisyen')
        
        if available_dietitians.exists():
            # İlk uygun diyetisyeni seç
            selected_availability = available_dietitians.first()
            diyetisyen = selected_availability.diyetisyen
            
            # Randevuyu güncelle
            randevu.diyetisyen = diyetisyen
            randevu.durum = 'ONAYLANDI'
            randevu.save()
            
            # Müsaitliği güncelle
            selected_availability.musait = False
            selected_availability.save()
            
            # Eğer eşleşme yoksa oluştur
            if not DanisanDiyetisyenEslesme.objects.filter(
                danisan=randevu.danisan,
                diyetisyen=diyetisyen,
                durum='AKTIF'
            ).exists():
                DanisanDiyetisyenEslesme.objects.create(
                    danisan=randevu.danisan,
                    diyetisyen=diyetisyen,
                    durum='AKTIF'
                )
    
    @staticmethod
    def cancel_randevu(randevu, cancelled_by, reason=None):
        """Randevu iptal et"""
        
        with transaction.atomic():
            if randevu.durum in ['IPTAL', 'TAMAMLANDI']:
                raise ValidationError("Bu randevu zaten iptal edilmiş veya tamamlanmış.")
            
            # İptal durumunu güncelle
            randevu.durum = 'IPTAL'
            randevu.iptal_eden = cancelled_by
            randevu.iptal_tarihi = timezone.now()
            randevu.iptal_sebebi = reason
            randevu.save()
            
            # Müsaitliği geri aç
            if randevu.diyetisyen:
                Musaitlik.objects.filter(
                    diyetisyen=randevu.diyetisyen,
                    tarih=randevu.tarih,
                    saat=randevu.saat
                ).update(musait=True)
            
            # Eğer diyetisyen iptal ettiyse admin müdahale talebi oluştur
            if cancelled_by.rol.rol_adi == 'diyetisyen' and cancelled_by == randevu.diyetisyen:
                RandevuService._create_admin_mudahale(randevu, reason)
    
    @staticmethod
    def _create_admin_mudahale(randevu, reason):
        """Diyetisyen iptali için admin müdahale talebi oluştur"""
        
        # Son 7 gün içindeki iptal sayısını kontrol et
        week_ago = timezone.now() - timedelta(days=7)
        recent_cancellations = Randevu.objects.filter(
            diyetisyen=randevu.diyetisyen,
            durum='IPTAL',
            iptal_tarihi__gte=week_ago,
            iptal_eden=randevu.diyetisyen
        ).count()
        
        # Eğer 3 veya daha fazla iptal varsa müdahale talebi oluştur
        if recent_cancellations >= 3:
            RandevuMudahaleTalebi.objects.create(
                randevu=randevu,
                talep_eden=randevu.diyetisyen,
                aciklama=f"Diyetisyen son 7 günde {recent_cancellations} randevu iptal etti. Sebep: {reason}",
                durum='ACIK'
            )
    
    @staticmethod
    def reassign_randevu(randevu, new_diyetisyen, admin_user):
        """Randevuyu yeni diyetisyene ata (Admin işlemi)"""
        
        if admin_user.rol.rol_adi != 'admin':
            raise ValidationError("Bu işlem sadece admin kullanıcılar tarafından yapılabilir.")
        
        with transaction.atomic():
            # Eski diyetisyenin müsaitliğini geri aç
            if randevu.diyetisyen:
                Musaitlik.objects.filter(
                    diyetisyen=randevu.diyetisyen,
                    tarih=randevu.tarih,
                    saat=randevu.saat
                ).update(musait=True)
            
            # Yeni diyetisyenin müsaitliğini kontrol et
            new_availability = Musaitlik.objects.filter(
                diyetisyen=new_diyetisyen,
                tarih=randevu.tarih,
                saat=randevu.saat,
                musait=True
            ).first()
            
            if not new_availability:
                raise ValidationError("Seçilen diyetisyen bu saatte müsait değil.")
            
            # Randevuyu güncelle
            randevu.diyetisyen = new_diyetisyen
            randevu.durum = 'ONAYLANDI'
            randevu.save()
            
            # Yeni müsaitliği güncelle
            new_availability.musait = False
            new_availability.save()
            
            # Eşleşmeyi güncelle
            DanisanDiyetisyenEslesme.objects.update_or_create(
                danisan=randevu.danisan,
                defaults={'diyetisyen': new_diyetisyen, 'durum': 'AKTIF'}
            )
    
    @staticmethod
    def complete_randevu(randevu, completion_notes=None):
        """Randevuyu tamamla"""
        
        if randevu.durum != 'ONAYLANDI':
            raise ValidationError("Sadece onaylanmış randevular tamamlanabilir.")
        
        randevu.durum = 'TAMAMLANDI'
        randevu.tamamlanma_tarihi = timezone.now()
        if completion_notes:
            randevu.notlar = f"{randevu.notlar or ''}\n\nTamamlanma Notu: {completion_notes}"
        randevu.save()
        
        return randevu
    
    @staticmethod
    def get_user_randevular(user, status_filter=None):
        """Kullanıcının randevularını getir"""
        
        if user.rol.rol_adi == 'admin':
            queryset = Randevu.objects.all()
        elif user.rol.rol_adi == 'diyetisyen':
            # Get diyetisyen instance from user
            try:
                diyetisyen = user.diyetisyen
                queryset = Randevu.objects.filter(diyetisyen=diyetisyen)
            except:
                return Randevu.objects.none()
        elif user.rol.rol_adi == 'danisan':
            queryset = Randevu.objects.filter(danisan=user)
        else:
            return Randevu.objects.none()
        
        if status_filter:
            queryset = queryset.filter(durum=status_filter)
        
        return queryset.select_related('danisan', 'diyetisyen').order_by('-randevu_tarih_saat')
    
    @staticmethod
    def get_available_slots(tarih, diyetisyen=None):
        """Belirli bir tarih için müsait saatleri getir"""
        
        queryset = Musaitlik.objects.filter(
            tarih=tarih,
            musait=True
        ).select_related('diyetisyen')
        
        if diyetisyen:
            queryset = queryset.filter(diyetisyen=diyetisyen)
        
        return queryset.order_by('saat')