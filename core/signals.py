"""
Django signals for handling model lifecycle events
"""
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

from .models import (
    Kullanici, Randevu, OdemeHareketi, DiyetisyenOdeme, 
    Bildirim, DanisanDiyetisyenEslesme
)


@receiver(post_save, sender=Kullanici)
def kullanici_olusturuldu(sender, instance, created, **kwargs):
    """Yeni kullanıcı oluşturulduğunda çalışır"""
    if created:
        # Cache'i temizle
        cache.delete('total_users')
        cache.delete(f'user_role_{instance.rol.rol_adi}_count')
        
        # Hoş geldin bildirimi oluştur
        Bildirim.objects.create(
            alici_kullanici=instance,
            mesaj=f"Hoş geldiniz {instance.ad}! Diyetlenio platformuna başarıyla kayıt oldunuz.",
            tur='HOSGELDIN'
        )


@receiver(post_save, sender=Randevu)
def randevu_durum_degisti(sender, instance, created, **kwargs):
    """Randevu durumu değiştiğinde çalışır"""
    if created:
        # Yeni randevu bildirimi
        Bildirim.objects.create(
            alici_kullanici=instance.diyetisyen.kullanici,
            mesaj=f"Yeni randevu talebi: {instance.danisan.ad} {instance.danisan.soyad}",
            tur='YENI_RANDEVU'
        )
    else:
        # Durum değişikliği bildirimi
        if instance.durum == 'ONAYLANDI':
            Bildirim.objects.create(
                alici_kullanici=instance.danisan,
                mesaj=f"Randevunuz onaylandı. Tarih: {instance.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M')}",
                tur='RANDEVU_ONAYLANDI'
            )
        elif instance.durum == 'IPTAL_EDILDI':
            # Hem danışana hem diyetisyene bildirim
            Bildirim.objects.create(
                alici_kullanici=instance.danisan,
                mesaj=f"Randevunuz iptal edildi. Neden: {instance.iptal_nedeni or 'Belirtilmedi'}",
                tur='RANDEVU_IPTAL'
            )
            Bildirim.objects.create(
                alici_kullanici=instance.diyetisyen.kullanici,
                mesaj=f"Randevu iptal edildi: {instance.danisan.ad} {instance.danisan.soyad}",
                tur='RANDEVU_IPTAL'
            )


@receiver(post_save, sender=OdemeHareketi)
def odeme_islendi(sender, instance, created, **kwargs):
    """Ödeme işlendiğinde çalışır"""
    if created and instance.odeme_durumu == 'TAMAMLANDI':
        # Ödeme onay bildirimi
        Bildirim.objects.create(
            alici_kullanici=instance.danisan,
            mesaj=f"Ödemeniz başarıyla işlendi. Tutar: {instance.toplam_ucret} TL",
            tur='ODEME_ONAY'
        )
        
        # Diyetisyene kazanç bildirimi
        Bildirim.objects.create(
            alici_kullanici=instance.diyetisyen.kullanici,
            mesaj=f"Yeni kazanç: {instance.diyetisyen_kazanci} TL",
            tur='KAZANC'
        )


@receiver(pre_delete, sender=Kullanici)
def kullanici_silinmeden_once(sender, instance, **kwargs):
    """Kullanıcı silinmeden önce çalışır"""
    # İlişkili kayıtları soft delete yap
    if hasattr(instance, 'diyetisyen'):
        # Diyetisyenin randevularını iptal et
        Randevu.objects.filter(
            diyetisyen=instance.diyetisyen, 
            durum__in=['BEKLEMEDE', 'ONAYLANDI']
        ).update(
            durum='IPTAL_EDILDI',
            iptal_nedeni='Diyetisyen hesabı silindi',
            iptal_edilme_tarihi=timezone.now(),
            iptal_eden_tur='SISTEM'
        )


@receiver(post_delete, sender=Kullanici)
def kullanici_silindi(sender, instance, **kwargs):
    """Kullanıcı silindikten sonra çalışır"""
    # Cache'i temizle
    cache.delete('total_users')
    cache.delete(f'user_role_{instance.rol.rol_adi}_count')


@receiver(post_save, sender=DanisanDiyetisyenEslesme)
def eslesme_olusturuldu(sender, instance, created, **kwargs):
    """Danışan-diyetisyen eşleşmesi oluşturulduğunda"""
    if created:
        # Eşleşme bildirimlerini oluştur
        Bildirim.objects.create(
            alici_kullanici=instance.diyetisyen.kullanici,
            mesaj=f"Yeni danışan eşleşmesi: {instance.danisan.ad} {instance.danisan.soyad}",
            tur='YENI_ESLESME'
        )
        
        Bildirim.objects.create(
            alici_kullanici=instance.danisan,
            mesaj=f"Diyetisyeniniz: Dyt. {instance.diyetisyen.kullanici.ad} {instance.diyetisyen.kullanici.soyad}",
            tur='DIYETISYEN_ATANDI'
        )


# Cache invalidation signals
@receiver([post_save, post_delete], sender=Randevu)
def randevu_cache_temizle(sender, **kwargs):
    """Randevu değişikliklerinde cache'i temizle"""
    cache.delete('total_appointments')
    cache.delete('monthly_appointments')
    cache.delete('appointment_stats')


@receiver([post_save, post_delete], sender=OdemeHareketi)
def odeme_cache_temizle(sender, **kwargs):
    """Ödeme değişikliklerinde cache'i temizle"""
    cache.delete('monthly_revenue')
    cache.delete('payment_stats')