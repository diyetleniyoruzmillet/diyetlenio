from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import timedelta
from drf_spectacular.utils import extend_schema

from core.models import (
    Diyetisyen, Musaitlik, DanisanDiyetisyenEslesme, 
    DiyetisyenNot, Randevu, OdemeHareketi
)
from core.services.auth_service import AuthService
from .serializers import (
    DiyetisyenProfileSerializer, DiyetisyenProfileUpdateSerializer,
    MusaitlikSerializer, MusaitlikBulkCreateSerializer, AssignedClientSerializer,
    DiyetisyenNotCreateSerializer, DiyetisyenNotSerializer, 
    DiyetisyenEarningsSerializer, DiyetisyenStatsSerializer
)


class DiyetisyenRequiredMixin:
    """Diyetisyen yetkisi gereken view'lar için mixin"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Kimlik doğrulama gerekli.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not AuthService.is_diyetisyen(request.user):
            return Response({'error': 'Bu işlem için diyetisyen yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
        
        return super().dispatch(request, *args, **kwargs)


class DiyetisyenProfileView(DiyetisyenRequiredMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return DiyetisyenProfileSerializer
        return DiyetisyenProfileUpdateSerializer
    
    def get_object(self):
        return self.request.user.diyetisyen
    
    @extend_schema(
        summary="Diyetisyen Profil Görüntüleme",
        description="Diyetisyen kendi profil bilgilerini görüntüler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Diyetisyen Profil Güncelleme",
        description="Diyetisyen kendi profil bilgilerini günceller",
        request=DiyetisyenProfileUpdateSerializer
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class MusaitlikListCreateView(DiyetisyenRequiredMixin, generics.ListCreateAPIView):
    serializer_class = MusaitlikSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        diyetisyen = self.request.user.diyetisyen
        # Son 30 gün ve gelecek 90 gün arasındaki müsaitlikleri getir
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date() + timedelta(days=90)
        
        return Musaitlik.objects.filter(
            diyetisyen=diyetisyen,
            tarih__gte=start_date,
            tarih__lte=end_date
        ).order_by('tarih', 'saat')
    
    @extend_schema(
        summary="Müsaitlik Listesi",
        description="Diyetisyenin müsaitlik saatlerini listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Müsaitlik Ekleme",
        description="Diyetisyen yeni müsaitlik saati ekler",
        request=MusaitlikSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(
    summary="Toplu Müsaitlik Ekleme",
    description="Bir tarih için birden fazla saat ekler",
    request=MusaitlikBulkCreateSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_create_availability(request):
    if not AuthService.is_diyetisyen(request.user):
        return Response({'error': 'Diyetisyen yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = MusaitlikBulkCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        try:
            created_slots = serializer.save()
            return Response({
                'message': f'{len(created_slots)} müsaitlik saati başarıyla eklendi.',
                'created_count': len(created_slots)
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MusaitlikDetailView(DiyetisyenRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MusaitlikSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Musaitlik.objects.filter(diyetisyen=self.request.user.diyetisyen)
    
    @extend_schema(summary="Müsaitlik Detay", description="Müsaitlik detaylarını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Müsaitlik Güncelle", description="Müsaitlik durumunu günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Müsaitlik Sil", description="Müsaitlik saatini siler")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class AssignedClientsView(DiyetisyenRequiredMixin, generics.ListAPIView):
    serializer_class = AssignedClientSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        diyetisyen = self.request.user.diyetisyen
        return DanisanDiyetisyenEslesme.objects.filter(
            diyetisyen=diyetisyen,
            durum='AKTIF'
        ).select_related('danisan').order_by('-eslesme_tarihi')
    
    @extend_schema(
        summary="Atanmış Danışanlar",
        description="Diyetisyene atanmış danışanları listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DiyetisyenNotListCreateView(DiyetisyenRequiredMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DiyetisyenNotCreateSerializer
        return DiyetisyenNotSerializer
    
    def get_queryset(self):
        diyetisyen = self.request.user.diyetisyen
        return DiyetisyenNot.objects.filter(
            diyetisyen=diyetisyen,
            silindi=False
        ).select_related('danisan', 'olusturan').order_by('-olusma_tarihi')
    
    @extend_schema(summary="Not Listesi", description="Diyetisyenin notlarını listeler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Not Ekleme", 
        description="Danışan için yeni not ekler",
        request=DiyetisyenNotCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DiyetisyenNotDetailView(DiyetisyenRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DiyetisyenNotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return DiyetisyenNot.objects.filter(
            diyetisyen=self.request.user.diyetisyen,
            silindi=False
        )
    
    def perform_destroy(self, instance):
        # Soft delete
        instance.silindi = True
        instance.save()
    
    @extend_schema(summary="Not Detay", description="Not detaylarını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Not Güncelle", description="Notu günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Not Sil", description="Notu siler (soft delete)")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@extend_schema(
    summary="Diyetisyen İstatistikleri",
    description="Diyetisyenin kendi istatistiklerini görüntüler",
    responses={200: DiyetisyenStatsSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def diyetisyen_statistics(request):
    if not AuthService.is_diyetisyen(request.user):
        return Response({'error': 'Diyetisyen yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        diyetisyen = request.user.diyetisyen
        
        # Tarih aralıkları
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Danışan istatistikleri
        toplam_danisan = DanisanDiyetisyenEslesme.objects.filter(diyetisyen=diyetisyen).count()
        aktif_danisan = DanisanDiyetisyenEslesme.objects.filter(
            diyetisyen=diyetisyen, durum='AKTIF'
        ).count()
        
        # Randevu istatistikleri
        randevular = Randevu.objects.filter(diyetisyen=request.user)
        bu_hafta_randevu = randevular.filter(tarih__gte=week_start).count()
        bu_ay_randevu = randevular.filter(tarih__gte=month_start).count()
        toplam_randevu = randevular.count()
        
        # İptal oranı
        iptal_randevu = randevular.filter(durum='IPTAL').count()
        iptal_orani = (iptal_randevu / toplam_randevu * 100) if toplam_randevu > 0 else 0
        
        # Ortalama puan (varsa)
        ortalama_puan = 0.0  # Değerlendirme sistemi eklendiğinde güncellenecek
        
        stats = {
            'toplam_danisan': toplam_danisan,
            'aktif_danisan': aktif_danisan,
            'bu_hafta_randevu': bu_hafta_randevu,
            'bu_ay_randevu': bu_ay_randevu,
            'toplam_randevu': toplam_randevu,
            'iptal_orani': round(iptal_orani, 2),
            'ortalama_puan': ortalama_puan
        }
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Kazanç Raporu",
    description="Diyetisyenin kazanç raporunu görüntüler",
    responses={200: DiyetisyenEarningsSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def earnings_report(request):
    if not AuthService.is_diyetisyen(request.user):
        return Response({'error': 'Diyetisyen yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        diyetisyen = request.user.diyetisyen
        
        # Bu ay için rapor
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Ödeme hareketleri
        payments = OdemeHareketi.objects.filter(
            diyetisyen=diyetisyen,
            odeme_tarihi__gte=month_start
        )
        
        toplam_randevu = Randevu.objects.filter(
            diyetisyen=request.user,
            tarih__gte=month_start
        ).count()
        
        tamamlanan_randevu = Randevu.objects.filter(
            diyetisyen=request.user,
            tarih__gte=month_start,
            durum='TAMAMLANDI'
        ).count()
        
        brut_kazanc = sum(payment.toplam_ucret for payment in payments)
        komisyon_kesintisi = sum(payment.komisyon_miktari for payment in payments)
        net_kazanc = sum(payment.diyetisyen_kazanci for payment in payments)
        
        earnings = {
            'donem': month_start.strftime('%Y-%m'),
            'toplam_randevu': toplam_randevu,
            'tamamlanan_randevu': tamamlanan_randevu,
            'brut_kazanc': brut_kazanc,
            'komisyon_kesintisi': komisyon_kesintisi,
            'net_kazanc': net_kazanc
        }
        
        return Response(earnings)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)