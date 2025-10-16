from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.conf import settings
from django.db import models
from drf_spectacular.utils import extend_schema
import os

from core.models import Dosya
from core.services.auth_service import AuthService
from .serializers import (
    DosyaUploadSerializer, DosyaSerializer, DosyaUpdateSerializer,
    DosyaListFilterSerializer
)


class DosyaListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DosyaUploadSerializer
        return DosyaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Dosya.objects.select_related('yukleyen')
        
        # Gizlilik seviyesi kontrolü
        if AuthService.is_admin(user):
            # Admin tüm dosyaları görebilir
            pass
        elif AuthService.is_diyetisyen(user):
            # Diyetisyen: HERKES, DIYETISYEN, kendi yüklediği dosyalar
            queryset = queryset.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'diyetisyen']) |
                models.Q(yukleyen=user)
            )
        else:
            # Danışan: HERKES, KULLANICI, kendi yüklediği dosyalar
            queryset = queryset.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'KULLANICI']) |
                models.Q(yukleyen=user)
            )
        
        # Filtreleme
        baglanti_tipi = self.request.query_params.get('baglanti_tipi')
        baglanti_id = self.request.query_params.get('baglanti_id')
        gizlilik_seviyesi = self.request.query_params.get('gizlilik_seviyesi')
        
        if baglanti_tipi:
            queryset = queryset.filter(baglanti_tipi=baglanti_tipi)
        if baglanti_id:
            queryset = queryset.filter(baglanti_id=baglanti_id)
        if gizlilik_seviyesi:
            queryset = queryset.filter(gizlilik_seviyesi=gizlilik_seviyesi)
        
        return queryset.order_by('-yukleme_tarihi')
    
    @extend_schema(
        summary="Dosya Listesi",
        description="Kullanıcının erişebileceği dosyaları listeler",
        parameters=[
            {
                'name': 'baglanti_tipi',
                'in': 'query',
                'description': 'Bağlantı tipi filtresi',
                'required': False,
                'schema': {'type': 'string', 'enum': ['KULLANICI', 'RANDEVU', 'diyetisyen', 'GENEL']}
            },
            {
                'name': 'baglanti_id',
                'in': 'query',
                'description': 'Bağlantı ID filtresi',
                'required': False,
                'schema': {'type': 'integer'}
            },
            {
                'name': 'gizlilik_seviyesi',
                'in': 'query',
                'description': 'Gizlilik seviyesi filtresi',
                'required': False,
                'schema': {'type': 'string', 'enum': ['HERKES', 'KULLANICI', 'diyetisyen', 'admin']}
            }
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Dosya Yükleme",
        description="Yeni dosya yükler",
        request=DosyaUploadSerializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DosyaDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DosyaUpdateSerializer
        return DosyaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Dosya.objects.select_related('yukleyen')
        
        # Gizlilik kontrolü (get_queryset'tekiyle aynı)
        if AuthService.is_admin(user):
            pass
        elif AuthService.is_diyetisyen(user):
            queryset = queryset.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'diyetisyen']) |
                models.Q(yukleyen=user)
            )
        else:
            queryset = queryset.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'KULLANICI']) |
                models.Q(yukleyen=user)
            )
        
        return queryset
    
    def perform_destroy(self, instance):
        # Dosya sahibi veya admin silebilir
        if instance.yukleyen != self.request.user and not AuthService.is_admin(self.request.user):
            raise PermissionError("Bu dosyayı silme yetkiniz yok.")
        
        # Fiziksel dosyayı sil
        file_path = os.path.join(settings.BASE_DIR, 'media', instance.dosya_yolu)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        super().perform_destroy(instance)
    
    @extend_schema(summary="Dosya Detay", description="Dosya detaylarını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Dosya Güncelle", description="Dosya bilgilerini günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @extend_schema(summary="Dosya Sil", description="Dosyayı siler")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@extend_schema(
    summary="Dosya İndir",
    description="Dosyayı indirir ve indirme sayısını artırır"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file(request, pk):
    try:
        # Dosyayı getir ve yetki kontrolü yap
        user = request.user
        
        # Gizlilik kontrolü ile dosyayı getir
        if AuthService.is_admin(user):
            dosya = get_object_or_404(Dosya, pk=pk)
        elif AuthService.is_diyetisyen(user):
            dosya = get_object_or_404(
                Dosya.objects.filter(
                    models.Q(gizlilik_seviyesi__in=['HERKES', 'diyetisyen']) |
                    models.Q(yukleyen=user)
                ),
                pk=pk
            )
        else:
            dosya = get_object_or_404(
                Dosya.objects.filter(
                    models.Q(gizlilik_seviyesi__in=['HERKES', 'KULLANICI']) |
                    models.Q(yukleyen=user)
                ),
                pk=pk
            )
        
        # Dosya yolu
        file_path = os.path.join(settings.BASE_DIR, 'media', dosya.dosya_yolu)
        
        if not os.path.exists(file_path):
            raise Http404("Dosya bulunamadı.")
        
        # İndirme sayısını artır
        dosya.indirilme_sayisi += 1
        dosya.save(update_fields=['indirilme_sayisi'])
        
        # Dosyayı döndür
        response = FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=dosya.dosya_adi
        )
        
        return response
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Kullanıcı Dosyaları",
    description="Sadece kullanıcının kendi yüklediği dosyaları listeler"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_files(request):
    try:
        dosyalar = Dosya.objects.filter(
            yukleyen=request.user
        ).order_by('-yukleme_tarihi')
        
        serializer = DosyaSerializer(dosyalar, many=True, context={'request': request})
        
        return Response({
            'count': dosyalar.count(),
            'results': serializer.data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Dosya Arama",
    description="Dosya adı veya açıklamada arama yapar"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_files(request):
    try:
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response({'error': 'Arama kelimesi gereklidir.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Gizlilik kontrolü ile arama
        if AuthService.is_admin(user):
            dosyalar = Dosya.objects.filter(
                models.Q(dosya_adi__icontains=query) |
                models.Q(aciklama__icontains=query)
            )
        elif AuthService.is_diyetisyen(user):
            dosyalar = Dosya.objects.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'diyetisyen']) |
                models.Q(yukleyen=user)
            ).filter(
                models.Q(dosya_adi__icontains=query) |
                models.Q(aciklama__icontains=query)
            )
        else:
            dosyalar = Dosya.objects.filter(
                models.Q(gizlilik_seviyesi__in=['HERKES', 'KULLANICI']) |
                models.Q(yukleyen=user)
            ).filter(
                models.Q(dosya_adi__icontains=query) |
                models.Q(aciklama__icontains=query)
            )
        
        dosyalar = dosyalar.select_related('yukleyen').order_by('-yukleme_tarihi')[:50]
        
        serializer = DosyaSerializer(dosyalar, many=True, context={'request': request})
        
        return Response({
            'count': dosyalar.count(),
            'results': serializer.data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)