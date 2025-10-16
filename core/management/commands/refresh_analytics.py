from django.core.management.base import BaseCommand
from core.utils import RandevuAnalytics, CacheUtils


class Command(BaseCommand):
    help = 'Refresh all analytics data (equivalent to refresh_all_materialized_views)'

    def handle(self, *args, **options):
        self.stdout.write('Refreshing analytics data...')
        
        # Cache'i temizle
        CacheUtils.refresh_all_analytics()
        
        # Temel verileri yeniden hesapla ve cache'e koy
        try:
            # Son 7 gün iptal oranı
            iptal_orani = RandevuAnalytics.son7gun_iptal_orani()
            self.stdout.write(f'Son 7 gün iptal oranı: {iptal_orani["iptal_orani_yuzde"]}%')
            
            # Açık müdahale talepleri
            acik_talepler = RandevuAnalytics.acik_mudahale_talepleri()
            self.stdout.write(f'Açık müdahale talepleri: {acik_talepler.count()}')
            
            # Bekleme metrikleri
            bekleme_metrikleri = RandevuAnalytics.acik_mudahale_bekleme_metrikleri()
            self.stdout.write(f'Ortalama bekleme süresi: {bekleme_metrikleri["ort_bekleme_dk"]} dk')
            
            # En çok iptal eden diyetisyenler
            iptal_edenler = RandevuAnalytics.son7gun_en_cok_iptal_eden_diyetisyenler()
            self.stdout.write(f'En çok iptal eden diyetisyen sayısı: {iptal_edenler.count()}')
            
            self.stdout.write(
                self.style.SUCCESS('✅ Analytics data refreshed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error refreshing analytics: {str(e)}')
            )