from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from core.models import DiyetListesi, Diyetisyen
from core.services.auth_service import AuthService
from .serializers import (
    DiyetListesiSerializer, DiyetListesiCreateSerializer, 
    DiyetListesiUpdateSerializer
)


class DiyetisyenRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_diyetisyen(request.user):
            return Response(
                {'error': 'Bu işlem sadece diyetisyenler için geçerlidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


class DiyetListesiListCreateView(DiyetisyenRequiredMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DiyetListesiCreateSerializer
        return DiyetListesiSerializer
    
    def get_queryset(self):
        diyetisyen = Diyetisyen.objects.get(kullanici=self.request.user)
        return DiyetListesi.objects.filter(diyetisyen=diyetisyen).order_by('-yuklenme_tarihi')
    
    @extend_schema(
        summary="Diyet Planları Listesi",
        description="Diyetisyenin oluşturduğu diyet planlarını listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Diyet Planı Oluştur",
        description="Danışan için yeni diyet planı oluşturur",
        request=DiyetListesiCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DiyetListesiDetailView(DiyetisyenRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DiyetListesiUpdateSerializer
        return DiyetListesiSerializer
    
    def get_queryset(self):
        diyetisyen = Diyetisyen.objects.get(kullanici=self.request.user)
        return DiyetListesi.objects.filter(diyetisyen=diyetisyen)
    
    @extend_schema(summary="Diyet Planı Detay", description="Diyet planı detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Diyet Planı Güncelle", description="Diyet planını günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Diyet Planı Sil", description="Diyet planını siler")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


# Danışanlar için diyet planlarını görüntüleme
class DanisanDiyetPlanlariView(generics.ListAPIView):
    serializer_class = DiyetListesiSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if not AuthService.is_danisan(self.request.user):
            return DiyetListesi.objects.none()
        return DiyetListesi.objects.filter(danisan=self.request.user).order_by('-yuklenme_tarihi')
    
    @extend_schema(
        summary="Danışanın Diyet Planları",
        description="Danışanın aldığı tüm diyet planlarını listeler",
    )
    def get(self, request, *args, **kwargs):
        if not AuthService.is_danisan(request.user):
            return Response(
                {'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Diyet Planı Detay (Danışan)",
    description="Danışanın belirli diyet planını görüntüler"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def danisan_diyet_plan_detay(request, pk):
    if not AuthService.is_danisan(request.user):
        return Response(
            {'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    diyet_plani = get_object_or_404(DiyetListesi, pk=pk, danisan=request.user)
    serializer = DiyetListesiSerializer(diyet_plani)
    return Response(serializer.data)