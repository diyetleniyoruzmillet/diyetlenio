from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from core.models import Sikayet, PromosyonKodu
from core.services.auth_service import AuthService
from .serializers import (
    SikayetSerializer, SikayetCreateSerializer, AdminSikayetSerializer,
    SikayetCozumSerializer, PromosyonKoduSerializer, PromosyonKoduCreateSerializer,
    PromosyonKoduKullanimSerializer, PromosyonKoduResponseSerializer
)


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_admin(request.user):
            return Response(
                {'error': 'Admin yetkisi gereklidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


# Şikayet Endpoints
class SikayetListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SikayetCreateSerializer
        return SikayetSerializer
    
    def get_queryset(self):
        # Kullanıcının kendi şikayetleri
        return Sikayet.objects.filter(sikayet_eden=self.request.user).order_by('-sikayet_tarihi')
    
    @extend_schema(
        summary="Kullanıcının Şikayetleri",
        description="Kullanıcının yaptığı şikayetleri listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Şikayet Oluştur",
        description="Yeni şikayet kaydı oluşturur",
        request=SikayetCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SikayetDetailView(generics.RetrieveAPIView):
    serializer_class = SikayetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Sikayet.objects.filter(sikayet_eden=self.request.user)
    
    @extend_schema(summary="Şikayet Detay", description="Şikayet detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# Admin Şikayet Endpoints
class AdminSikayetListView(AdminRequiredMixin, generics.ListAPIView):
    serializer_class = AdminSikayetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Sikayet.objects.all().order_by('-sikayet_tarihi')
        
        # Query parametreleri ile filtreleme
        cozum_durumu = self.request.query_params.get('cozum_durumu')
        if cozum_durumu:
            queryset = queryset.filter(cozum_durumu=cozum_durumu)
        
        sikayet_tipi = self.request.query_params.get('sikayet_tipi')
        if sikayet_tipi:
            queryset = queryset.filter(sikayet_tipi=sikayet_tipi)
        
        return queryset
    
    @extend_schema(
        summary="Tüm Şikayetler (Admin)",
        description="Tüm şikayetleri listeler",
        parameters=[
            {
                'name': 'cozum_durumu',
                'in': 'query',
                'description': 'Çözüm durumu filtresi',
                'required': False,
                'schema': {'type': 'string'}
            },
            {
                'name': 'sikayet_tipi',
                'in': 'query',
                'description': 'Şikayet tipi filtresi',
                'required': False,
                'schema': {'type': 'string'}
            }
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Şikayeti Çöz (Admin)",
    description="Admin şikayeti çözülmüş olarak işaretler",
    request=SikayetCozumSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_sikayet_cozum(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    sikayet = get_object_or_404(Sikayet, pk=pk)
    serializer = SikayetCozumSerializer(data=request.data)
    
    if serializer.is_valid():
        cozum_durumu = serializer.validated_data['cozum_durumu']
        sikayet.cozum_durumu = cozum_durumu
        sikayet.save()
        
        return Response({
            'message': f'Şikayet {cozum_durumu.lower()} olarak işaretlendi.',
            'sikayet_id': sikayet.id,
            'cozum_durumu': cozum_durumu
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Promosyon Kodu Endpoints
@extend_schema(
    summary="Promosyon Kodu Kontrol",
    description="Promosyon kodunun geçerliliğini kontrol eder",
    request=PromosyonKoduKullanimSerializer,
    responses={200: PromosyonKoduResponseSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promosyon_kodu_kontrol(request):
    serializer = PromosyonKoduKullanimSerializer(data=request.data)
    
    if serializer.is_valid():
        kod = serializer.validated_data['kod']
        
        try:
            promo_kod = PromosyonKodu.objects.get(kod=kod, aktif_mi=True)
            
            # Tarihi kontrol et
            today = timezone.now().date()
            if today < promo_kod.baslangic_tarihi or today > promo_kod.bitis_tarihi:
                return Response({
                    'gecerli': False,
                    'mesaj': 'Promosyon kodu süresi dolmuş veya henüz aktif değil.'
                })
            
            # Kullanım limiti kontrol et
            if promo_kod.kullanilma_sayisi >= promo_kod.kullanim_limiti:
                return Response({
                    'gecerli': False,
                    'mesaj': 'Promosyon kodu kullanım limiti dolmuş.'
                })
            
            return Response({
                'gecerli': True,
                'indirim_miktari': promo_kod.indirim_miktari,
                'indirim_tipi': promo_kod.indirim_tipi,
                'mesaj': 'Promosyon kodu geçerli.'
            })
            
        except PromosyonKodu.DoesNotExist:
            return Response({
                'gecerli': False,
                'mesaj': 'Geçersiz promosyon kodu.'
            })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Admin Promosyon Kodu Endpoints
class AdminPromosyonKoduListCreateView(AdminRequiredMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PromosyonKoduCreateSerializer
        return PromosyonKoduSerializer
    
    def get_queryset(self):
        return PromosyonKodu.objects.all().order_by('-id')
    
    @extend_schema(
        summary="Promosyon Kodları (Admin)",
        description="Tüm promosyon kodlarını listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Promosyon Kodu Oluştur",
        description="Yeni promosyon kodu oluşturur",
        request=PromosyonKoduCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AdminPromosyonKoduDetailView(AdminRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PromosyonKoduSerializer
    permission_classes = [IsAuthenticated]
    queryset = PromosyonKodu.objects.all()
    
    @extend_schema(summary="Promosyon Kodu Detay", description="Promosyon kodu detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Promosyon Kodu Güncelle", description="Promosyon kodunu günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Promosyon Kodu Sil", description="Promosyon kodunu siler")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@extend_schema(
    summary="Promosyon Kodu İstatistikleri (Admin)",
    description="Promosyon kodlarının kullanım istatistiklerini getirir"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_promosyon_istatistikleri(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    # Genel istatistikler
    toplam_kod = PromosyonKodu.objects.count()
    aktif_kod = PromosyonKodu.objects.filter(aktif_mi=True).count()
    suresi_dolan = PromosyonKodu.objects.filter(
        bitis_tarihi__lt=timezone.now().date()
    ).count()
    
    # En çok kullanılan kodlar
    populer_kodlar = PromosyonKodu.objects.filter(
        kullanilma_sayisi__gt=0
    ).order_by('-kullanilma_sayisi')[:10]
    
    populer_kodlar_data = []
    for kod in populer_kodlar:
        populer_kodlar_data.append({
            'kod': kod.kod,
            'kullanim_sayisi': kod.kullanilma_sayisi,
            'kullanim_limiti': kod.kullanim_limiti,
            'indirim_miktari': kod.indirim_miktari,
            'indirim_tipi': kod.indirim_tipi
        })
    
    stats = {
        'toplam_promosyon_kodu': toplam_kod,
        'aktif_kod_sayisi': aktif_kod,
        'suresi_dolan_kod': suresi_dolan,
        'en_populer_kodlar': populer_kodlar_data
    }
    
    return Response(stats)