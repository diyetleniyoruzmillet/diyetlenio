from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from core.models import Makale, MakaleKategori, MakaleYorum
from core.services.auth_service import AuthService
from .serializers import (
    MakaleKategoriSerializer, MakaleSerializer, MakaleCreateSerializer, MakaleUpdateSerializer,
    PublicMakaleSerializer, MakaleYorumSerializer, MakaleYorumCreateSerializer,
    AdminMakaleSerializer, MakaleOnaySerializer
)


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_admin(request.user):
            return Response(
                {'error': 'Admin yetkisi gereklidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


class DiyetisyenRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not AuthService.is_diyetisyen(request.user):
            return Response(
                {'error': 'Diyetisyen yetkisi gereklidir.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)


# Kategori endpoints
class MakaleKategoriListView(generics.ListAPIView):
    serializer_class = MakaleKategoriSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return MakaleKategori.objects.filter(aktif_mi=True).order_by('sira', 'ad')
    
    @extend_schema(
        summary="Makale Kategorileri",
        description="Aktif makale kategorilerini listeler (public endpoint)",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminMakaleKategoriListCreateView(AdminRequiredMixin, generics.ListCreateAPIView):
    serializer_class = MakaleKategoriSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MakaleKategori.objects.all().order_by('sira', 'ad')
    
    @extend_schema(summary="Kategoriler (Admin)", description="Tüm kategorileri listeler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Kategori Oluştur", description="Yeni kategori oluşturur")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AdminMakaleKategoriDetailView(AdminRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MakaleKategoriSerializer
    permission_classes = [IsAuthenticated]
    queryset = MakaleKategori.objects.all()
    
    @extend_schema(summary="Kategori Detay", description="Kategori detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Kategori Güncelle", description="Kategoriyi günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Kategori Sil", description="Kategoriyi siler")
    def delete(self, request, *args, **kwargs):
        kategori = self.get_object()
        if kategori.makaleler.exists():
            return Response(
                {'error': 'Bu kategoriye ait makaleler olduğu için silinemez.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().delete(request, *args, **kwargs)


# Public endpoints - onaylanmış makaleler
class PublicMakaleListView(generics.ListAPIView):
    serializer_class = PublicMakaleSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Makale.objects.filter(onay_durumu='ONAYLANDI').order_by('-yayimlanma_tarihi')
    
    @extend_schema(
        summary="Onaylanmış Makaleler",
        description="Yayınlanmış tüm makaleleri listeler (public endpoint)",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PublicMakaleDetailView(generics.RetrieveAPIView):
    serializer_class = PublicMakaleSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Makale.objects.filter(onay_durumu='ONAYLANDI')
    
    @extend_schema(summary="Makale Detay", description="Yayınlanmış makale detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# Makale yorumları
class MakaleYorumListView(generics.ListAPIView):
    serializer_class = MakaleYorumSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        makale_id = self.kwargs['makale_id']
        return MakaleYorum.objects.filter(makale_id=makale_id).order_by('-yorum_tarihi')
    
    @extend_schema(
        summary="Makale Yorumları",
        description="Belirli makaleye yapılan yorumları listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Makaleye Yorum Yap",
    description="Onaylanmış makaleye yorum ekler",
    request=MakaleYorumCreateSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def makale_yorum_ekle(request, makale_id):
    makale = get_object_or_404(Makale, id=makale_id, onay_durumu='ONAYLANDI')
    
    serializer = MakaleYorumCreateSerializer(
        data={**request.data, 'makale_id': makale_id},
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Author endpoints - yazarlar için
class AuthorMakaleListCreateView(DiyetisyenRequiredMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MakaleCreateSerializer
        return MakaleSerializer
    
    def get_queryset(self):
        return Makale.objects.filter(yazar_kullanici=self.request.user).order_by('-id')
    
    @extend_schema(
        summary="Yazarın Makaleleri",
        description="Kullanıcının yazdığı tüm makaleleri listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Makale Yaz",
        description="Yeni makale oluşturur (onay bekler)",
        request=MakaleCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AuthorMakaleDetailView(DiyetisyenRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return MakaleUpdateSerializer
        return MakaleSerializer
    
    def get_queryset(self):
        return Makale.objects.filter(yazar_kullanici=self.request.user)
    
    @extend_schema(summary="Makale Detay", description="Yazarın makale detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Makale Güncelle", description="Makaleyi günceller")
    def patch(self, request, *args, **kwargs):
        makale = self.get_object()
        if makale.onay_durumu == 'ONAYLANDI':
            return Response(
                {'error': 'Onaylanmış makaleler düzenlenemez.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Makale Sil", description="Makaleyi siler")
    def delete(self, request, *args, **kwargs):
        makale = self.get_object()
        if makale.onay_durumu == 'ONAYLANDI':
            return Response(
                {'error': 'Onaylanmış makaleler silinemez.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().delete(request, *args, **kwargs)


# Admin endpoints - makale onay/red
class AdminPendingMakaleListView(AdminRequiredMixin, generics.ListAPIView):
    serializer_class = AdminMakaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Makale.objects.filter(onay_durumu='BEKLEMEDE').order_by('-id')
    
    @extend_schema(
        summary="Onay Bekleyen Makaleler",
        description="Admin onayı bekleyen makaleleri listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Makale Onayla/Reddet",
    description="Admin makaleyi onaylar veya reddeder",
    request=MakaleOnaySerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_makale_onay(request, pk):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    makale = get_object_or_404(Makale, pk=pk, onay_durumu='BEKLEMEDE')
    serializer = MakaleOnaySerializer(data=request.data)
    
    if serializer.is_valid():
        onay_durumu = serializer.validated_data['onay_durumu']
        makale.onay_durumu = onay_durumu
        
        if onay_durumu == 'ONAYLANDI':
            makale.yayimlanma_tarihi = timezone.now()
        
        makale.save()
        
        return Response({
            'message': f'Makale {onay_durumu.lower()} olarak işaretlendi.',
            'makale_id': makale.id,
            'onay_durumu': onay_durumu
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)