"""
Custom model managers for better query optimization and business logic
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class RandevuManager(models.Manager):
    """Randevu modeli için özel manager"""
    
    def get_queryset(self):
        """Base queryset with select_related for performance"""
        return super().get_queryset().select_related('diyetisyen__kullanici', 'danisan')
    
    def aktif_randevular(self):
        """Aktif randevuları getir (iptal edilmemiş)"""
        return self.filter(durum__in=['BEKLEMEDE', 'ONAYLANDI', 'TAMAMLANDI'])
    
    def bugun_randevular(self):
        """Bugünkü randevuları getir"""
        today = timezone.now().date()
        return self.filter(
            randevu_tarih_saat__date=today,
            durum__in=['ONAYLANDI', 'TAMAMLANDI']
        )
    
    def yaklasan_randevular(self, hours=24):
        """Yaklaşan randevuları getir"""
        now = timezone.now()
        return self.filter(
            randevu_tarih_saat__gte=now,
            randevu_tarih_saat__lte=now + timedelta(hours=hours),
            durum='ONAYLANDI'
        )
    
    def diyetisyen_randevulari(self, diyetisyen, tarih=None):
        """Belirli diyetisyenin randevularını getir"""
        queryset = self.filter(diyetisyen=diyetisyen)
        if tarih:
            queryset = queryset.filter(randevu_tarih_saat__date=tarih)
        return queryset.order_by('randevu_tarih_saat')


class OdemeHareketiManager(models.Manager):
    """Ödeme hareketi için özel manager"""
    
    def get_queryset(self):
        return super().get_queryset().select_related('diyetisyen__kullanici', 'danisan', 'randevu')
    
    def tamamlanan_odemeler(self):
        """Tamamlanan ödemeleri getir"""
        return self.filter(odeme_durumu='TAMAMLANDI')
    
    def bekleyen_odemeler(self):
        """Bekleyen ödemeleri getir"""
        return self.filter(odeme_durumu='BEKLEMEDE')
    
    def diyetisyen_kazanclari(self, diyetisyen, baslangic=None, bitis=None):
        """Diyetisyen kazançlarını hesapla"""
        queryset = self.filter(diyetisyen=diyetisyen, odeme_durumu='TAMAMLANDI')
        if baslangic:
            queryset = queryset.filter(odeme_tarihi__gte=baslangic)
        if bitis:
            queryset = queryset.filter(odeme_tarihi__lte=bitis)
        return queryset


class KullaniciManager(models.Manager):
    """Kullanıcı modeli için özel manager"""
    
    def get_queryset(self):
        return super().get_queryset().select_related('rol')
    
    def aktif_kullanicilar(self):
        """Aktif kullanıcıları getir"""
        return self.filter(aktif_mi=True)
    
    def diyetisyenler(self):
        """Diyetisyenleri getir"""
        return self.filter(rol__rol_adi='diyetisyen', aktif_mi=True)
    
    def danisanlar(self):
        """Danışanları getir"""
        return self.filter(rol__rol_adi='danisan', aktif_mi=True)
    
    def adminler(self):
        """Admin kullanıcıları getir"""
        return self.filter(rol__rol_adi='admin', aktif_mi=True)


class DiyetisyenManager(models.Manager):
    """Diyetisyen modeli için özel manager"""
    
    def get_queryset(self):
        return super().get_queryset().select_related('kullanici').prefetch_related('diyetisyenuzmanlikalani_set__uzmanlik_alani')
    
    def aktif_diyetisyenler(self):
        """Aktif diyetisyenleri getir"""
        return self.filter(kullanici__aktif_mi=True)
    
    def onay_bekleyenler(self):
        """Onay bekleyen diyetisyenleri getir"""
        return self.filter(kullanici__aktif_mi=False)


class SoftDeleteManager(models.Manager):
    """Soft delete desteği için manager"""
    
    def get_queryset(self):
        return super().get_queryset().filter(silindi=False)
    
    def silinmis_kayitlar(self):
        """Silinmiş kayıtları getir"""
        return super().get_queryset().filter(silindi=True)
    
    def tum_kayitlar(self):
        """Tüm kayıtları getir (silinmiş dahil)"""
        return super().get_queryset()