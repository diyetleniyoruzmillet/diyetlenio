from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from datetime import timedelta, datetime
from drf_spectacular.utils import extend_schema

from core.models import (
    Kullanici, Randevu, OdemeHareketi, Diyetisyen, RandevuMudahaleTalebi,
    DanisanDiyetisyenEslesme, UzmanlikAlani, DiyetisyenUzmanlikAlani
)
from core.services.auth_service import AuthService
# from core.utils import RandevuAnalytics  # Temporarily disabled
from .serializers import (
    PlatformStatsSerializer, RandevuTrendiSerializer, DiyetisyenPerformansSerializer,
    UzmanlikAlaniStatsSerializer, AylikRaporSerializer, IptalAnaliziSerializer,
    MudahaleRaporuSerializer, CustomDateRangeSerializer
)


@extend_schema(
    summary="Platform İstatistikleri",
    description="Genel platform istatistiklerini görüntüler (Admin)",
    responses={200: PlatformStatsSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def platform_statistics(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Tarih aralıkları
        today = timezone.now().date()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=today.weekday())
        
        # Kullanıcı istatistikleri
        toplam_kullanici = Kullanici.objects.count()
        aktif_kullanici = Kullanici.objects.filter(is_active=True).count()
        yeni_kullanici_bu_ay = Kullanici.objects.filter(date_joined__gte=month_start).count()
        danisan_sayisi = Kullanici.objects.filter(rol__rol_adi='danisan').count()
        diyetisyen_sayisi = Kullanici.objects.filter(rol__rol_adi='diyetisyen').count()
        
        # Randevu istatistikleri
        toplam_randevu = Randevu.objects.count()
        bu_ay_randevu = Randevu.objects.filter(tarih__gte=month_start).count()
        bu_hafta_randevu = Randevu.objects.filter(tarih__gte=week_start).count()
        bugun_randevu = Randevu.objects.filter(tarih=today).count()
        tamamlanan_randevu = Randevu.objects.filter(durum='TAMAMLANDI').count()
        iptal_edilen_randevu = Randevu.objects.filter(durum='IPTAL').count()
        iptal_orani = (iptal_edilen_randevu / toplam_randevu * 100) if toplam_randevu > 0 else 0
        
        # Finansal istatistikler
        bu_ay_odemeler = OdemeHareketi.objects.filter(odeme_tarihi__gte=month_start)
        bu_ay_toplam_gelir = bu_ay_odemeler.aggregate(toplam=Sum('toplam_ucret'))['toplam'] or 0
        toplam_komisyon = bu_ay_odemeler.aggregate(toplam=Sum('komisyon_miktari'))['toplam'] or 0
        ortalama_randevu_ucreti = bu_ay_odemeler.aggregate(ortalama=Avg('toplam_ucret'))['ortalama'] or 0
        
        stats = {
            'toplam_kullanici': toplam_kullanici,
            'aktif_kullanici': aktif_kullanici,
            'yeni_kullanici_bu_ay': yeni_kullanici_bu_ay,
            'danisan_sayisi': danisan_sayisi,
            'diyetisyen_sayisi': diyetisyen_sayisi,
            'toplam_randevu': toplam_randevu,
            'bu_ay_randevu': bu_ay_randevu,
            'bu_hafta_randevu': bu_hafta_randevu,
            'bugun_randevu': bugun_randevu,
            'tamamlanan_randevu': tamamlanan_randevu,
            'iptal_edilen_randevu': iptal_edilen_randevu,
            'iptal_orani': round(iptal_orani, 2),
            'bu_ay_toplam_gelir': bu_ay_toplam_gelir,
            'toplam_komisyon': toplam_komisyon,
            'ortalama_randevu_ucreti': round(float(ortalama_randevu_ucreti), 2)
        }
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Randevu Trendi",
    description="Son 30 günün randevu trendini görüntüler (Admin)",
    parameters=[
        {
            'name': 'days',
            'in': 'query',
            'description': 'Gün sayısı (varsayılan: 30)',
            'required': False,
            'schema': {'type': 'integer'}
        }
    ],
    responses={200: RandevuTrendiSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def randevu_trend(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Günlük randevu trendini hesapla
        daily_stats = []
        current_date = start_date
        
        while current_date <= end_date:
            day_randevular = Randevu.objects.filter(tarih=current_date)
            
            daily_stat = {
                'tarih': current_date,
                'toplam_randevu': day_randevular.count(),
                'tamamlanan': day_randevular.filter(durum='TAMAMLANDI').count(),
                'iptal_edilen': day_randevular.filter(durum='IPTAL').count()
            }
            daily_stats.append(daily_stat)
            current_date += timedelta(days=1)
        
        return Response(daily_stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Diyetisyen Performans Raporu",
    description="Diyetisyenlerin performans analizi (Admin)",
    responses={200: DiyetisyenPerformansSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def diyetisyen_performance(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        diyetisyenler = Diyetisyen.objects.filter(
            kullanici__is_active=True
        ).select_related('kullanici')
        
        performance_data = []
        
        for diyetisyen in diyetisyenler:
            randevular = Randevu.objects.filter(diyetisyen=diyetisyen.kullanici)
            tamamlanan = randevular.filter(durum='TAMAMLANDI').count()
            iptal_edilen = randevular.filter(durum='IPTAL').count()
            toplam = randevular.count()
            
            # Kazanç hesaplama
            kazanc = OdemeHareketi.objects.filter(
                diyetisyen=diyetisyen
            ).aggregate(toplam=Sum('diyetisyen_kazanci'))['toplam'] or 0
            
            # Aktif danışan sayısı
            aktif_danisan = DanisanDiyetisyenEslesme.objects.filter(
                diyetisyen=diyetisyen,
                durum='AKTIF'
            ).count()
            
            iptal_orani = (iptal_edilen / toplam * 100) if toplam > 0 else 0
            
            performance_data.append({
                'diyetisyen_id': diyetisyen.kullanici.id,
                'diyetisyen_adi': f"{diyetisyen.kullanici.ad} {diyetisyen.kullanici.soyad}",
                'toplam_randevu': toplam,
                'tamamlanan_randevu': tamamlanan,
                'iptal_edilen_randevu': iptal_edilen,
                'iptal_orani': round(iptal_orani, 2),
                'toplam_kazanc': kazanc,
                'ortalama_puan': 4.5,  # Değerlendirme sistemi eklendikten sonra gerçek puan
                'aktif_danisan_sayisi': aktif_danisan
            })
        
        # Performansa göre sırala
        performance_data.sort(key=lambda x: x['tamamlanan_randevu'], reverse=True)
        
        return Response(performance_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Uzmanlık Alanı İstatistikleri",
    description="Uzmanlık alanlarına göre talep analizi",
    responses={200: UzmanlikAlaniStatsSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def specialty_statistics(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        uzmanlik_alanlari = UzmanlikAlani.objects.all()
        toplam_randevu = Randevu.objects.count()
        
        stats = []
        
        for alan in uzmanlik_alanlari:
            # Bu uzmanlık alanındaki diyetisyen sayısı
            diyetisyen_sayisi = DiyetisyenUzmanlikAlani.objects.filter(
                uzmanlik_alani=alan
            ).count()
            
            # Bu uzmanlık alanındaki diyetisyenlerin randevu sayısı
            diyetisyenler = DiyetisyenUzmanlikAlani.objects.filter(
                uzmanlik_alani=alan
            ).values_list('diyetisyen__kullanici', flat=True)
            
            randevu_sayisi = Randevu.objects.filter(
                diyetisyen__in=diyetisyenler
            ).count()
            
            talep_orani = (randevu_sayisi / toplam_randevu * 100) if toplam_randevu > 0 else 0
            
            stats.append({
                'uzmanlik_alani': alan.alan_adi,
                'diyetisyen_sayisi': diyetisyen_sayisi,
                'randevu_sayisi': randevu_sayisi,
                'talep_orani': round(talep_orani, 2)
            })
        
        # Talep oranına göre sırala
        stats.sort(key=lambda x: x['talep_orani'], reverse=True)
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="İptal Analizi",
    description="Yüksek iptal oranına sahip diyetisyenlerin analizi",
    responses={200: IptalAnaliziSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cancellation_analysis(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # RandevuAnalytics'ten mevcut fonksiyonları kullan
        iptal_analizi = RandevuAnalytics.diyetisyen_iptal_orani_30g()
        
        results = []
        for analiz in iptal_analizi:
            # Risk seviyesi belirleme
            iptal_orani = analiz.get('iptal_orani', 0)
            if iptal_orani >= 30:
                risk_seviyesi = 'YUKSEK'
            elif iptal_orani >= 15:
                risk_seviyesi = 'ORTA'
            else:
                risk_seviyesi = 'DUSUK'
            
            results.append({
                'diyetisyen_id': analiz.get('diyetisyen_id'),
                'diyetisyen_adi': analiz.get('diyetisyen_adi', ''),
                'son_7gun_iptal': analiz.get('son_7gun_iptal', 0),
                'son_30gun_iptal': analiz.get('son_30gun_iptal', 0),
                'toplam_randevu': analiz.get('toplam_randevu', 0),
                'iptal_orani': iptal_orani,
                'risk_seviyesi': risk_seviyesi
            })
        
        # Risk seviyesine göre sırala
        risk_order = {'YUKSEK': 0, 'ORTA': 1, 'DUSUK': 2}
        results.sort(key=lambda x: risk_order[x['risk_seviyesi']])
        
        return Response(results)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Müdahale Raporu",
    description="Admin müdahale taleplerinin analizi",
    responses={200: MudahaleRaporuSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def intervention_report(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Müdahale talepleri
        toplam_talepler = RandevuMudahaleTalebi.objects.count()
        acik_talepler = RandevuMudahaleTalebi.objects.filter(durum='ACIK').count()
        cozumlenen_talepler = RandevuMudahaleTalebi.objects.filter(durum='COZULDU').count()
        
        # Ortalama çözüm süresi hesaplama (saat cinsinden)
        cozumlenen_talep_objeleri = RandevuMudahaleTalebi.objects.filter(
            durum='COZULDU',
            cozum_tarihi__isnull=False
        )
        
        ortalama_cozum_suresi = 0
        if cozumlenen_talep_objeleri.exists():
            toplam_sure = sum([
                (talep.cozum_tarihi - talep.talep_tarihi).total_seconds() / 3600
                for talep in cozumlenen_talep_objeleri
            ])
            ortalama_cozum_suresi = toplam_sure / cozumlenen_talep_objeleri.count()
        
        # En çok müdahale gereken diyetisyenler
        problem_diyetisyenler = RandevuMudahaleTalebi.objects.filter(
            durum='ACIK'
        ).values(
            'randevu__diyetisyen'
        ).annotate(
            talep_sayisi=Count('id')
        ).order_by('-talep_sayisi')[:10]
        
        en_cok_mudahale_gereken = []
        for item in problem_diyetisyenler:
            if item['randevu__diyetisyen']:
                try:
                    diyetisyen = Kullanici.objects.get(id=item['randevu__diyetisyen'])
                    en_cok_mudahale_gereken.append({
                        'diyetisyen_id': diyetisyen.id,
                        'diyetisyen_adi': f"{diyetisyen.ad} {diyetisyen.soyad}",
                        'toplam_randevu': 0,  # Detaylı hesaplama gerekli
                        'tamamlanan_randevu': 0,
                        'iptal_edilen_randevu': 0,
                        'iptal_orani': 0,
                        'toplam_kazanc': 0,
                        'ortalama_puan': 0,
                        'aktif_danisan_sayisi': 0
                    })
                except Kullanici.DoesNotExist:
                    continue
        
        rapor = {
            'toplam_mudahale_talepleri': toplam_talepler,
            'acik_talepler': acik_talepler,
            'cozumlenen_talepler': cozumlenen_talepler,
            'ortalama_cozum_suresi': round(ortalama_cozum_suresi, 2),
            'en_cok_mudahale_gereken_diyetisyenler': en_cok_mudahale_gereken
        }
        
        return Response(rapor)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)