from django.db import models
from django.db.models import Count, Q, Case, When, DecimalField, F, Sum, Avg, Max
from django.utils import timezone
from datetime import timedelta
from .models import (
    RandevuMudahaleTalebi, Randevu, Kullanici, Diyetisyen,
    AnketOturum, SoruSeti, DiyetisyenNot
)


class RandevuQuerySet(models.QuerySet):
    """Custom QuerySet for Randevu model"""
    
    def acik_mudahale_talepleri(self):
        """
        v_acik_mudahale_talepleri view equivalent
        """
        return RandevuMudahaleTalebi.objects.select_related(
            'randevu__danisan', 'randevu__diyetisyen__kullanici'
        ).filter(
            durum='ACIK'
        ).annotate(
            talep_id=F('id'),
            randevu_durumu=F('randevu__durum'),
            danisan_adi=models.Concat(
                F('randevu__danisan__ad'), 
                models.Value(' '), 
                F('randevu__danisan__soyad')
            ),
            diyetisyen_adi=models.Concat(
                F('randevu__diyetisyen__kullanici__ad'),
                models.Value(' '),
                F('randevu__diyetisyen__kullanici__soyad')
            )
        )
    
    def son7gun_iptal_orani(self):
        """
        v_son7gun_iptal_orani view equivalent
        """
        yedi_gun_once = timezone.now() - timedelta(days=7)
        
        toplam = self.filter(randevu_tarih_saat__gte=yedi_gun_once).count()
        iptal = self.filter(
            durum='IPTAL_EDILDI',
            iptal_edilme_tarihi__gte=yedi_gun_once
        ).count()
        
        iptal_orani = (iptal * 100.0 / toplam) if toplam > 0 else 0
        
        return {
            'toplam_randevu': toplam,
            'iptal_sayisi': iptal,
            'iptal_orani_yuzde': round(iptal_orani, 2)
        }
    
    def son7gun_en_cok_iptal_eden_diyetisyenler(self):
        """
        v_son7gun_en_cok_iptal_eden_diyetisyenler view equivalent
        """
        yedi_gun_once = timezone.now() - timedelta(days=7)
        
        return self.filter(
            durum='IPTAL_EDILDI',
            iptal_eden_tur='diyetisyen',
            iptal_edilme_tarihi__gte=yedi_gun_once
        ).values(
            'diyetisyen__kullanici_id',
            'diyetisyen__kullanici__ad',
            'diyetisyen__kullanici__soyad'
        ).annotate(
            iptal_sayisi=Count('id')
        ).annotate(
            diyetisyen_adi=models.Concat(
                F('diyetisyen__kullanici__ad'),
                models.Value(' '),
                F('diyetisyen__kullanici__soyad')
            )
        )
    
    def son7gun_gunluk_iptal_trendi(self):
        """
        v_son7gun_gunluk_iptal_trendi view equivalent
        """
        yedi_gun_once = timezone.now() - timedelta(days=7)
        
        return self.filter(
            iptal_edilme_tarihi__gte=yedi_gun_once
        ).extra(
            select={'gun': "DATE(COALESCE(iptal_edilme_tarihi, randevu_tarih_saat))"}
        ).values('gun').annotate(
            toplam_iptal=Count('id', filter=Q(durum='IPTAL_EDILDI')),
            diyetisyen_iptal=Count('id', filter=Q(durum='IPTAL_EDILDI', iptal_eden_tur='diyetisyen')),
            danisan_iptal=Count('id', filter=Q(durum='IPTAL_EDILDI', iptal_eden_tur='danisan')),
            admin_iptal=Count('id', filter=Q(durum='IPTAL_EDILDI', iptal_eden_tur='admin')),
            sistem_iptal=Count('id', filter=Q(durum='IPTAL_EDILDI', iptal_eden_tur='SISTEM'))
        ).order_by('gun')
    
    def diyetisyen_iptal_orani_alltime(self):
        """
        v_diyetisyen_iptal_orani_alltime view equivalent
        """
        from django.db.models import Case, When, IntegerField
        
        return Diyetisyen.objects.select_related('kullanici').annotate(
            toplam_randevu=Count('randevu'),
            diyetisyen_iptal=Count(
                'randevu',
                filter=Q(randevu__durum='IPTAL_EDILDI', randevu__iptal_eden_tur='diyetisyen')
            ),
            iptal_orani_yuzde=Case(
                When(toplam_randevu=0, then=0),
                default=F('diyetisyen_iptal') * 100.0 / F('toplam_randevu'),
                output_field=DecimalField(max_digits=5, decimal_places=2)
            ),
            diyetisyen_adi=models.Concat(
                F('kullanici__ad'),
                models.Value(' '),
                F('kullanici__soyad')
            )
        )
    
    def diyetisyen_iptal_orani_30g(self):
        """
        v_diyetisyen_iptal_orani_30g view equivalent
        """
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
            ),
            iptal_orani_yuzde_30g=Case(
                When(toplam_randevu_30g=0, then=0),
                default=F('diyetisyen_iptal_30g') * 100.0 / F('toplam_randevu_30g'),
                output_field=DecimalField(max_digits=5, decimal_places=2)
            ),
            diyetisyen_adi=models.Concat(
                F('kullanici__ad'),
                models.Value(' '),
                F('kullanici__soyad')
            )
        )


class RandevuMudahaleTalebiQuerySet(models.QuerySet):
    """Custom QuerySet for RandevuMudahaleTalebi model"""
    
    def acik_mudahale_bekleme_detay(self):
        """
        v_acik_mudahale_bekleme_detay view equivalent
        """
        return self.select_related(
            'randevu__danisan', 'randevu__diyetisyen__kullanici'
        ).filter(
            durum='ACIK'
        ).annotate(
            bekleme_suresi_dakika=models.ExpressionWrapper(
                (timezone.now() - F('olusma_tarihi')).total_seconds() / 60,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            danisan_adi=models.Concat(
                F('randevu__danisan__ad'),
                models.Value(' '),
                F('randevu__danisan__soyad')
            ),
            diyetisyen_adi=models.Concat(
                F('randevu__diyetisyen__kullanici__ad'),
                models.Value(' '),
                F('randevu__diyetisyen__kullanici__soyad')
            )
        )
    
    def acik_mudahale_bekleme_metrikleri(self):
        """
        v_acik_mudahale_bekleme_metrikleri view equivalent
        """
        acik_talepler = self.filter(durum='ACIK')
        
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
            'medyan_bekleme_dk': round(bekleme_sureleri[n // 2], 2),
            'p90_bekleme_dk': round(bekleme_sureleri[int(n * 0.9)], 2),
            'max_bekleme_dk': round(max(bekleme_sureleri), 2)
        }


class AnketOturumQuerySet(models.QuerySet):
    """Custom QuerySet for AnketOturum model"""
    
    def kullanici_acik_anketleri(self):
        """
        v_kullanici_acik_anketleri view equivalent
        """
        return self.select_related('kullanici', 'soru_seti').filter(
            durum='ACIK'
        ).annotate(
            ad_soyad=models.Concat(
                F('kullanici__ad'),
                models.Value(' '),
                F('kullanici__soyad')
            )
        )


class DiyetisyenNotQuerySet(models.QuerySet):
    """Custom QuerySet for DiyetisyenNot model"""
    
    def admin_gorunum(self):
        """
        v_diyetisyen_notlari_admin view equivalent
        """
        return self.select_related(
            'diyetisyen__kullanici', 'danisan', 'olusturan'
        ).filter(
            silindi=False
        ).annotate(
            diyetisyen_adi=models.Concat(
                F('diyetisyen__kullanici__ad'),
                models.Value(' '),
                F('diyetisyen__kullanici__soyad')
            ),
            danisan_adi=models.Concat(
                F('danisan__ad'),
                models.Value(' '),
                F('danisan__soyad')
            )
        )


# Manager'ları modellere eklemek için custom manager'lar
class RandevuManager(models.Manager):
    def get_queryset(self):
        return RandevuQuerySet(self.model, using=self._db)
    
    def acik_mudahale_talepleri(self):
        return self.get_queryset().acik_mudahale_talepleri()
    
    def son7gun_iptal_orani(self):
        return self.get_queryset().son7gun_iptal_orani()
    
    def son7gun_en_cok_iptal_eden_diyetisyenler(self):
        return self.get_queryset().son7gun_en_cok_iptal_eden_diyetisyenler()


class RandevuMudahaleTalebiManager(models.Manager):
    def get_queryset(self):
        return RandevuMudahaleTalebiQuerySet(self.model, using=self._db)
    
    def acik_mudahale_bekleme_detay(self):
        return self.get_queryset().acik_mudahale_bekleme_detay()
    
    def acik_mudahale_bekleme_metrikleri(self):
        return self.get_queryset().acik_mudahale_bekleme_metrikleri()


class AnketOturumManager(models.Manager):
    def get_queryset(self):
        return AnketOturumQuerySet(self.model, using=self._db)
    
    def kullanici_acik_anketleri(self):
        return self.get_queryset().kullanici_acik_anketleri()


class DiyetisyenNotManager(models.Manager):
    def get_queryset(self):
        return DiyetisyenNotQuerySet(self.model, using=self._db)
    
    def admin_gorunum(self):
        return self.get_queryset().admin_gorunum()