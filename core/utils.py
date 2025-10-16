from django.db.models import Count, Q, F, Sum, Avg, Max, DecimalField, Value
from django.db.models.functions import Concat
from django.utils import timezone
from datetime import timedelta
from .models import (
    RandevuMudahaleTalebi, Randevu, Kullanici, Diyetisyen,
    AnketOturum, DiyetisyenNot, Rol, Bildirim, AdminYonlendirme,
    DanisanDiyetisyenEslesme
)


class RandevuAnalytics:
    """
    SQL view'larının Django ORM equivalent'leri
    """
    
    @staticmethod
    def acik_mudahale_talepleri():
        """v_acik_mudahale_talepleri view equivalent"""
        return RandevuMudahaleTalebi.objects.select_related(
            'randevu__danisan', 'randevu__diyetisyen__kullanici'
        ).filter(durum='ACIK')
    
    @staticmethod
    def son7gun_iptal_orani():
        """v_son7gun_iptal_orani view equivalent"""
        yedi_gun_once = timezone.now() - timedelta(days=7)
        
        toplam = Randevu.objects.filter(randevu_tarih_saat__gte=yedi_gun_once).count()
        iptal = Randevu.objects.filter(
            durum='IPTAL_EDILDI',
            iptal_edilme_tarihi__gte=yedi_gun_once
        ).count()
        
        iptal_orani = (iptal * 100.0 / toplam) if toplam > 0 else 0
        
        return {
            'toplam_randevu': toplam,
            'iptal_sayisi': iptal,
            'iptal_orani_yuzde': round(iptal_orani, 2)
        }
    
    @staticmethod
    def son7gun_en_cok_iptal_eden_diyetisyenler():
        """v_son7gun_en_cok_iptal_eden_diyetisyenler view equivalent"""
        yedi_gun_once = timezone.now() - timedelta(days=7)
        
        return Randevu.objects.filter(
            durum='IPTAL_EDILDI',
            iptal_eden_tur='diyetisyen',
            iptal_edilme_tarihi__gte=yedi_gun_once
        ).values(
            'diyetisyen__kullanici_id',
            'diyetisyen__kullanici__ad',
            'diyetisyen__kullanici__soyad'
        ).annotate(
            iptal_sayisi=Count('id'),
            diyetisyen_adi=Concat(
                F('diyetisyen__kullanici__ad'),
                Value(' '),
                F('diyetisyen__kullanici__soyad')
            )
        ).order_by('-iptal_sayisi')
    
    @staticmethod
    def acik_mudahale_bekleme_metrikleri():
        """v_acik_mudahale_bekleme_metrikleri view equivalent"""
        acik_talepler = RandevuMudahaleTalebi.objects.filter(durum='ACIK')
        
        if not acik_talepler.exists():
            return {
                'acik_talep_sayisi': 0,
                'ort_bekleme_dk': 0,
                'medyan_bekleme_dk': 0,
                'p90_bekleme_dk': 0,
                'max_bekleme_dk': 0
            }
        
        # Bekleme sürelerini hesapla
        bekleme_sureleri = []
        for talep in acik_talepler:
            bekleme_dk = (timezone.now() - talep.olusma_tarihi).total_seconds() / 60
            bekleme_sureleri.append(bekleme_dk)
        
        bekleme_sureleri.sort()
        n = len(bekleme_sureleri)
        
        return {
            'acik_talep_sayisi': n,
            'ort_bekleme_dk': round(sum(bekleme_sureleri) / n, 2),
            'medyan_bekleme_dk': round(bekleme_sureleri[n // 2], 2) if n > 0 else 0,
            'p90_bekleme_dk': round(bekleme_sureleri[int(n * 0.9)], 2) if n > 0 else 0,
            'max_bekleme_dk': round(max(bekleme_sureleri), 2) if bekleme_sureleri else 0
        }
    
    @staticmethod
    def diyetisyen_iptal_orani_alltime():
        """v_diyetisyen_iptal_orani_alltime view equivalent"""
        return Diyetisyen.objects.select_related('kullanici').annotate(
            toplam_randevu=Count('randevu'),
            diyetisyen_iptal=Count(
                'randevu',
                filter=Q(randevu__durum='IPTAL_EDILDI', randevu__iptal_eden_tur='diyetisyen')
            )
        ).annotate(
            iptal_orani_yuzde=F('diyetisyen_iptal') * 100.0 / F('toplam_randevu')
        ).filter(toplam_randevu__gt=0)
    
    @staticmethod 
    def diyetisyen_iptal_orani_30g():
        """v_diyetisyen_iptal_orani_30g view equivalent"""
        otuz_gun_once = timezone.now() - timedelta(days=30)
        
        return Diyetisyen.objects.select_related('kullanici').annotate(
            toplam_randevu_30g=Count(
                'randevu',
                filter=Q(randevu__randevu_tarih_saat__gte=otuz_gun_once)
            ),
            diyetisyen_iptal_30g=Count(
                'randevu',
                filter=Q(
                    randevu__durum='IPTAL_EDILDI',
                    randevu__iptal_eden_tur='diyetisyen',
                    randevu__iptal_edilme_tarihi__gte=otuz_gun_once
                )
            )
        ).annotate(
            iptal_orani_yuzde_30g=F('diyetisyen_iptal_30g') * 100.0 / F('toplam_randevu_30g')
        ).filter(toplam_randevu_30g__gt=0)


class AdminUtils:
    """
    SQL fonksiyonlarının Django equivalent'leri
    """
    
    @staticmethod
    def is_admin(user_id):
        """fn_is_admin equivalent"""
        try:
            user = Kullanici.objects.get(id=user_id)
            return user.rol.rol_adi == 'admin'
        except Kullanici.DoesNotExist:
            return False
    
    @staticmethod
    def admin_randevu_yeniden_atama(admin_id, randevu_id, hedef_diyetisyen_id, neden=None):
        """admin_randevu_yeniden_atama function equivalent"""
        try:
            admin = Kullanici.objects.get(id=admin_id)
            if not AdminUtils.is_admin(admin_id):
                raise ValueError(f'Sadece admin atayabilir (admin_id={admin_id}).')
            
            randevu = Randevu.objects.select_for_update().get(id=randevu_id)
            hedef_diyetisyen = Diyetisyen.objects.get(kullanici_id=hedef_diyetisyen_id)
            
            eski_diyetisyen_id = randevu.diyetisyen.kullanici_id
            danisan_id = randevu.danisan.id
            
            # Randevuyu yeniden ata
            randevu.diyetisyen = hedef_diyetisyen
            randevu.admin_inceleme_gerekiyor = False
            randevu.save()
            
            # Eşleşme oluştur/güncelle
            eslesme, created = DanisanDiyetisyenEslesme.objects.get_or_create(
                diyetisyen=hedef_diyetisyen,
                danisan_id=danisan_id,
                defaults={
                    'on_gorusme_yapildi_mi': False,
                    'hasta_mi': True,
                    'eslesme_tarihi': timezone.now()
                }
            )
            if not created:
                eslesme.hasta_mi = True
                eslesme.save()
            
            # Admin yönlendirme kaydı
            AdminYonlendirme.objects.create(
                admin=admin,
                danisan_id=danisan_id,
                kaynak_diyetisyen_id=eski_diyetisyen_id,
                hedef_diyetisyen=hedef_diyetisyen,
                ilgili_randevu=randevu,
                neden=neden or 'Admin yeniden atama',
                durum='GERCEKLESTI'
            )
            
            # Müdahale taleplerini kapat
            RandevuMudahaleTalebi.objects.filter(
                randevu=randevu,
                durum='ACIK'
            ).update(
                durum='COZUMLENDI',
                kapama_tarihi=timezone.now(),
                kapatan_admin=admin,
                yapilan_islem=f'Randevu yeni diyetisyene atandı (id={hedef_diyetisyen_id}).'
            )
            
            # Admin'e başarı bildirimi
            Bildirim.objects.create(
                alici_kullanici=admin,
                mesaj=f'Randevu #{randevu_id} Diyetisyen #{hedef_diyetisyen_id} üzerine atandı.',
                tur='ADMIN_ATAMA_OK'
            )
            
            return True
            
        except Exception as e:
            raise ValueError(f'Yeniden atama hatası: {str(e)}')


class CacheUtils:
    """
    Materialized view'lar için cache sistemi
    """
    
    @staticmethod
    def refresh_all_analytics():
        """
        refresh_all_materialized_views function equivalent
        Tüm analitik verileri yeniler (cache temizleme)
        """
        from django.core.cache import cache
        
        # Cache key'lerini temizle
        cache_keys = [
            'son7gun_gunluk_iptal_trendi',
            'diyetisyen_iptal_orani_30g',
            'acik_mudahale_bekleme_metrikleri'
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        return True
    
    @staticmethod
    def get_cached_analytics(key, calculator_func, timeout=600):
        """
        Cache'li analitik veri getir
        """
        from django.core.cache import cache
        
        cached_data = cache.get(key)
        if cached_data is None:
            cached_data = calculator_func()
            cache.set(key, cached_data, timeout)
        
        return cached_data


class ViewUtils:
    """
    Kolay view'lar için utility fonksiyonlar
    """
    
    @staticmethod
    def kullanici_acik_anketleri():
        """v_kullanici_acik_anketleri view equivalent"""
        return AnketOturum.objects.select_related('kullanici', 'soru_seti').filter(
            durum='ACIK'
        )
    
    @staticmethod
    def diyetisyen_notlari_admin():
        """v_diyetisyen_notlari_admin view equivalent"""
        return DiyetisyenNot.objects.select_related(
            'diyetisyen__kullanici', 'danisan', 'olusturan'
        ).filter(silindi=False)