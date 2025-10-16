from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q
from drf_spectacular.utils import extend_schema

from core.models import Yorum, Diyetisyen, Kullanici
from core.services.auth_service import AuthService
from .serializers import (
    YorumSerializer, YorumCreateSerializer, PublicYorumSerializer,
    DiyetisyenYorumStatsSerializer, AdminYorumSerializer, YorumOnaySerializer
)


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_admin(request.user):
            return Response(
                {'error': 'Admin yetkisi gereklidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


# Public endpoints - onaylanmış yorumlar
@extend_schema(
    summary="Diyetisyen Yorumları",
    description="Belirli diyetisyenin onaylanmış yorumlarını listeler",
    responses={200: PublicYorumSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def diyetisyen_yorumlari(request, diyetisyen_id):
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici__id=diyetisyen_id)
    except Diyetisyen.DoesNotExist:
        return Response({'error': 'Diyetisyen bulunamadı.'}, status=status.HTTP_404_NOT_FOUND)
    
    yorumlar = Yorum.objects.filter(
        diyetisyen=diyetisyen, 
        onay_durumu='ONAYLANDI'
    ).order_by('-yorum_tarihi')
    
    serializer = PublicYorumSerializer(yorumlar, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Diyetisyen Yorum İstatistikleri",
    description="Diyetisyenin puan ortalaması ve yorum istatistiklerini döndürür",
    responses={200: DiyetisyenYorumStatsSerializer}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def diyetisyen_yorum_stats(request, diyetisyen_id):
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici__id=diyetisyen_id)
    except Diyetisyen.DoesNotExist:
        return Response({'error': 'Diyetisyen bulunamadı.'}, status=status.HTTP_404_NOT_FOUND)
    
    # Onaylanmış yorumlar
    onaylanmis_yorumlar = Yorum.objects.filter(
        diyetisyen=diyetisyen, 
        onay_durumu='ONAYLANDI'
    )
    
    # İstatistikler
    ortalama_puan = onaylanmis_yorumlar.aggregate(Avg('puan'))['puan__avg'] or 0
    toplam_yorum = Yorum.objects.filter(diyetisyen=diyetisyen).count()
    onaylanmis_yorum_sayisi = onaylanmis_yorumlar.count()
    
    # Puan dağılımı
    puan_dagilimi = {}
    for i in range(1, 6):
        puan_dagilimi[str(i)] = onaylanmis_yorumlar.filter(puan=i).count()
    
    stats = {
        'ortalama_puan': round(ortalama_puan, 2),
        'toplam_yorum': toplam_yorum,
        'onaylanmis_yorum_sayisi': onaylanmis_yorum_sayisi,
        'puan_dagilimi': puan_dagilimi
    }
    
    return Response(stats)


# Danışan endpoints
class DanisanYorumListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return YorumCreateSerializer
        return YorumSerializer
    
    def get_queryset(self):
        if not AuthService.is_danisan(self.request.user):
            return Yorum.objects.none()
        return Yorum.objects.filter(danisan=self.request.user).order_by('-yorum_tarihi')
    
    @extend_schema(
        summary="Danışanın Yorumları",
        description="Danışanın yaptığı tüm yorumları listeler",
    )
    def get(self, request, *args, **kwargs):
        if not AuthService.is_danisan(request.user):
            return Response(
                {'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Diyetisyene Yorum Yap",
        description="Diyetisyen için yeni yorum ve puan ekler",
        request=YorumCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        if not AuthService.is_danisan(request.user):
            return Response(
                {'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().post(request, *args, **kwargs)


class DanisanYorumDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = YorumSerializer
    
    def get_queryset(self):
        return Yorum.objects.filter(danisan=self.request.user)
    
    @extend_schema(summary="Yorum Detay", description="Danışanın yorum detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Yorum Güncelle", description="Yorumu günceller (sadece beklemede olanlar)")
    def patch(self, request, *args, **kwargs):
        yorum = self.get_object()
        if yorum.onay_durumu != 'BEKLEMEDE':
            return Response(
                {'error': 'Sadece beklemede olan yorumlar düzenlenebilir.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Yorum Sil", description="Yorumu siler")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


# Diyetisyen endpoints - kendileri hakkındaki yorumları görme
@extend_schema(
    summary="Diyetisyenin Aldığı Yorumlar",
    description="Diyetisyenin kendisi hakkında yapılan yorumları görüntüler",
    responses={200: YorumSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def diyetisyen_aldigi_yorumlar(request):
    if not AuthService.is_diyetisyen(request.user):
        return Response(
            {'error': 'Bu işlem sadece diyetisyenler için geçerlidir.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    diyetisyen = Diyetisyen.objects.get(kullanici=request.user)
    yorumlar = Yorum.objects.filter(diyetisyen=diyetisyen).order_by('-yorum_tarihi')
    
    serializer = YorumSerializer(yorumlar, many=True)
    return Response(serializer.data)


# Admin endpoints - yorum onay/red
class AdminPendingYorumListView(AdminRequiredMixin, generics.ListAPIView):
    serializer_class = AdminYorumSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Yorum.objects.filter(onay_durumu='BEKLEMEDE').order_by('-yorum_tarihi')
    
    @extend_schema(
        summary="Onay Bekleyen Yorumlar",
        description="Admin onayı bekleyen yorumları listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Yorum Onayla/Reddet",
    description="Admin yorumu onaylar veya reddeder",
    request=YorumOnaySerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_yorum_onay(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    yorum = get_object_or_404(Yorum, pk=pk, onay_durumu='BEKLEMEDE')
    serializer = YorumOnaySerializer(data=request.data)
    
    if serializer.is_valid():
        onay_durumu = serializer.validated_data['onay_durumu']
        yorum.onay_durumu = onay_durumu
        yorum.save()
        
        return Response({
            'message': f'Yorum {onay_durumu.lower()} olarak işaretlendi.',
            'yorum_id': yorum.id,
            'onay_durumu': onay_durumu
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)