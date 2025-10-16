from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from core.models import SoruSeti, Soru, AnketOturum
from core.services.auth_service import AuthService
from .serializers import (
    SoruSetiSerializer, SoruSetiListSerializer, AnketOturumCreateSerializer,
    AnketOturumSerializer
)


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_admin(request.user):
            return Response(
                {'error': 'Admin yetkisi gereklidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


# Public endpoints - kullanıcılar için
class SoruSetiListView(generics.ListAPIView):
    serializer_class = SoruSetiListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Kullanıcının rolüne uygun aktif soru setleri
        user = self.request.user
        queryset = SoruSeti.objects.filter(aktif_mi=True)
        
        # Hedef rol filtresi
        if hasattr(user, 'rol') and user.rol:
            from django.db import models
            queryset = queryset.filter(
                models.Q(hedef_rol=user.rol) | models.Q(hedef_rol__isnull=True)
            )
        
        return queryset.order_by('ad')
    
    @extend_schema(
        summary="Aktif Soru Setleri",
        description="Kullanıcının cevaplayabileceği aktif soru setlerini listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SoruSetiDetailView(generics.RetrieveAPIView):
    serializer_class = SoruSetiSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = SoruSeti.objects.filter(aktif_mi=True)
        
        if hasattr(user, 'rol') and user.rol:
            from django.db import models
            queryset = queryset.filter(
                models.Q(hedef_rol=user.rol) | models.Q(hedef_rol__isnull=True)
            )
        
        return queryset
    
    @extend_schema(
        summary="Soru Seti Detay",
        description="Soru setinin tüm sorularını ve seçeneklerini getirir",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# Anket cevaplama
@extend_schema(
    summary="Anket Cevapla",
    description="Soru setindeki sorulara cevap verir",
    request=AnketOturumCreateSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anket_cevapla(request):
    serializer = AnketOturumCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        anket_oturum = serializer.save()
        response_serializer = AnketOturumSerializer(anket_oturum)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Kullanıcının anket geçmişi
class UserAnketListView(generics.ListAPIView):
    serializer_class = AnketOturumSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return AnketOturum.objects.filter(
            kullanici=self.request.user
        ).order_by('-baslangic_tarihi')
    
    @extend_schema(
        summary="Kullanıcının Anket Geçmişi",
        description="Kullanıcının doldurduğu anketleri listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Anket Detay",
    description="Kullanıcının belirli anket cevaplarını görüntüler"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_anket_detail(request, pk):
    anket_oturum = get_object_or_404(AnketOturum, pk=pk, kullanici=request.user)
    serializer = AnketOturumSerializer(anket_oturum)
    return Response(serializer.data)


# Admin endpoints - soru seti yönetimi
class AdminSoruSetiListView(AdminRequiredMixin, generics.ListAPIView):
    serializer_class = SoruSetiListSerializer
    permission_classes = [IsAuthenticated]
    queryset = SoruSeti.objects.all().order_by('ad')
    
    @extend_schema(
        summary="Tüm Soru Setleri (Admin)",
        description="Tüm soru setlerini listeler (admin görünümü)",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminAnketOturumListView(AdminRequiredMixin, generics.ListAPIView):
    serializer_class = AnketOturumSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Query parameters ile filtreleme
        queryset = AnketOturum.objects.all().order_by('-baslangic_tarihi')
        
        soru_seti_id = self.request.query_params.get('soru_seti_id')
        if soru_seti_id:
            queryset = queryset.filter(soru_seti_id=soru_seti_id)
        
        kullanici_id = self.request.query_params.get('kullanici_id')
        if kullanici_id:
            queryset = queryset.filter(kullanici_id=kullanici_id)
        
        durum = self.request.query_params.get('durum')
        if durum:
            queryset = queryset.filter(durum=durum)
        
        return queryset
    
    @extend_schema(
        summary="Tüm Anket Oturumları (Admin)",
        description="Tüm kullanıcıların anket cevaplarını listeler",
        parameters=[
            {
                'name': 'soru_seti_id',
                'in': 'query',
                'description': 'Soru seti ID filtresi',
                'required': False,
                'schema': {'type': 'integer'}
            },
            {
                'name': 'kullanici_id',
                'in': 'query',
                'description': 'Kullanıcı ID filtresi',
                'required': False,
                'schema': {'type': 'integer'}
            },
            {
                'name': 'durum',
                'in': 'query',
                'description': 'Anket durumu filtresi',
                'required': False,
                'schema': {'type': 'string', 'enum': ['ACIK', 'TAMAMLANDI']}
            }
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Anket İstatistikleri (Admin)",
    description="Belirli soru seti için istatistikler"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_anket_istatistikleri(request, soru_seti_id):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    soru_seti = get_object_or_404(SoruSeti, pk=soru_seti_id)
    
    # Temel istatistikler
    toplam_katilim = AnketOturum.objects.filter(soru_seti=soru_seti).count()
    tamamlanan = AnketOturum.objects.filter(soru_seti=soru_seti, durum='TAMAMLANDI').count()
    acik = AnketOturum.objects.filter(soru_seti=soru_seti, durum='ACIK').count()
    
    # Soru başına cevap sayıları
    sorular = Soru.objects.filter(soru_seti=soru_seti).order_by('sira_no')
    soru_istatistikleri = []
    
    for soru in sorular:
        from core.models import AnketCevap
        cevap_sayisi = AnketCevap.objects.filter(soru=soru).count()
        soru_istatistikleri.append({
            'soru_id': soru.id,
            'soru_metni': soru.soru_metni,
            'cevap_sayisi': cevap_sayisi
        })
    
    stats = {
        'soru_seti': {
            'id': soru_seti.id,
            'ad': soru_seti.ad,
            'aciklama': soru_seti.aciklama
        },
        'toplam_katilim': toplam_katilim,
        'tamamlanan': tamamlanan,
        'acik': acik,
        'tamamlanma_orani': (tamamlanan / toplam_katilim * 100) if toplam_katilim > 0 else 0,
        'soru_istatistikleri': soru_istatistikleri
    }
    
    return Response(stats)