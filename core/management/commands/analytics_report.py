from django.core.management.base import BaseCommand
from core.utils import RandevuAnalytics, ViewUtils
from core.models import Randevu, Diyetisyen, Kullanici
from django.utils import timezone
import json


class Command(BaseCommand):
    help = 'Generate comprehensive analytics report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (text or json)'
        )

    def handle(self, *args, **options):
        output_format = options['format']
        
        # Veri toplama
        data = {
            'timestamp': timezone.now().isoformat(),
            'genel_istatistikler': {
                'toplam_kullanici': Kullanici.objects.count(),
                'toplam_diyetisyen': Diyetisyen.objects.count(),
                'toplam_randevu': Randevu.objects.count(),
                'aktif_kullanici': Kullanici.objects.filter(aktif_mi=True).count(),
            },
            'iptal_analizi': RandevuAnalytics.son7gun_iptal_orani(),
            'mudahale_talepleri': RandevuAnalytics.acik_mudahale_bekleme_metrikleri(),
            'acik_anketler': ViewUtils.kullanici_acik_anketleri().count(),
            'admin_notlari': ViewUtils.diyetisyen_notlari_admin().count(),
        }
        
        # En çok iptal eden diyetisyenler
        iptal_edenler = list(RandevuAnalytics.son7gun_en_cok_iptal_eden_diyetisyenler().values())
        data['en_cok_iptal_edenler'] = iptal_edenler[:5]  # İlk 5
        
        # Diyetisyen iptal oranları (30 gün)
        iptal_oranlari = list(RandevuAnalytics.diyetisyen_iptal_orani_30g().values(
            'kullanici__ad', 'kullanici__soyad', 'toplam_randevu_30g', 
            'diyetisyen_iptal_30g', 'iptal_orani_yuzde_30g'
        ))
        data['diyetisyen_iptal_oranlari_30g'] = iptal_oranlari
        
        if output_format == 'json':
            self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        else:
            self.print_text_report(data)

    def print_text_report(self, data):
        self.stdout.write("=" * 60)
        self.stdout.write("📊 DİYETLENİO ANALİTİK RAPORU")
        self.stdout.write("=" * 60)
        self.stdout.write(f"📅 Rapor Tarihi: {data['timestamp']}")
        self.stdout.write("")
        
        # Genel İstatistikler
        self.stdout.write("📈 GENEL İSTATİSTİKLER:")
        stats = data['genel_istatistikler']
        self.stdout.write(f"  • Toplam Kullanıcı: {stats['toplam_kullanici']}")
        self.stdout.write(f"  • Aktif Kullanıcı: {stats['aktif_kullanici']}")
        self.stdout.write(f"  • Toplam Diyetisyen: {stats['toplam_diyetisyen']}")
        self.stdout.write(f"  • Toplam Randevu: {stats['toplam_randevu']}")
        self.stdout.write("")
        
        # İptal Analizi
        self.stdout.write("❌ SON 7 GÜN İPTAL ANALİZİ:")
        iptal = data['iptal_analizi']
        self.stdout.write(f"  • Toplam Randevu: {iptal['toplam_randevu']}")
        self.stdout.write(f"  • İptal Sayısı: {iptal['iptal_sayisi']}")
        self.stdout.write(f"  • İptal Oranı: %{iptal['iptal_orani_yuzde']}")
        self.stdout.write("")
        
        # Müdahale Talepleri
        self.stdout.write("🚨 AÇIK MÜDAHALE TALEPLERİ:")
        mudahale = data['mudahale_talepleri']
        if mudahale['acik_talep_sayisi'] > 0:
            self.stdout.write(f"  • Açık Talep Sayısı: {mudahale['acik_talep_sayisi']}")
            self.stdout.write(f"  • Ortalama Bekleme: {mudahale['ort_bekleme_dk']} dk")
            self.stdout.write(f"  • Maksimum Bekleme: {mudahale['max_bekleme_dk']} dk")
        else:
            self.stdout.write("  • Açık müdahale talebi yok ✅")
        self.stdout.write("")
        
        # En Çok İptal Edenler
        if data['en_cok_iptal_edenler']:
            self.stdout.write("👤 EN ÇOK İPTAL EDEN DİYETİSYENLER (Son 7 Gün):")
            for i, diyetisyen in enumerate(data['en_cok_iptal_edenler'], 1):
                self.stdout.write(f"  {i}. {diyetisyen.get('diyetisyen_adi', 'N/A')} - {diyetisyen['iptal_sayisi']} iptal")
            self.stdout.write("")
        
        # Diğer Bilgiler
        self.stdout.write("📋 DİĞER BİLGİLER:")
        self.stdout.write(f"  • Açık Anket Sayısı: {data['acik_anketler']}")
        self.stdout.write(f"  • Admin Not Sayısı: {data['admin_notlari']}")
        
        self.stdout.write("=" * 60)
        
        # Uyarılar
        if data['mudahale_talepleri']['acik_talep_sayisi'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  DİKKAT: {data['mudahale_talepleri']['acik_talep_sayisi']} "
                    "açık müdahale talebi var!"
                )
            )
        
        if data['iptal_analizi']['iptal_orani_yuzde'] > 10:
            self.stdout.write(
                self.style.ERROR(
                    f"🚨 YÜKSEK İPTAL ORANI: %{data['iptal_analizi']['iptal_orani_yuzde']} "
                    "(Normal: <%10)"
                )
            )