from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from drf_spectacular.utils import extend_schema

from core.models import (
    Kullanici, DanisanSaglikVerisi, Bildirim, UzmanlikAlani,
    Diyetisyen, Randevu, DanisanDiyetisyenEslesme
)
from core.services.auth_service import AuthService
from .serializers import (
    UserSearchSerializer, DanisanSaglikVerisiSerializer, DanisanSaglikVerisiUpdateSerializer,
    NotificationSerializer, NotificationCreateSerializer, UzmanlikAlaniSerializer,
    PublicDiyetisyenSerializer, UserProfileUpdateSerializer, UserStatsSerializer
)


@extend_schema(
    summary="Kullanıcı Arama",
    description="Ad, soyad veya e-posta ile kullanıcı arama (Admin için)",
    parameters=[
        {
            'name': 'q',
            'in': 'query',
            'description': 'Arama kelimesi',
            'required': True,
            'schema': {'type': 'string'}
        },
        {
            'name': 'rol',
            'in': 'query',
            'description': 'Rol filtresi (DANISAN, DIYETISYEN, ADMIN)',
            'required': False,
            'schema': {'type': 'string'}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_users(request):
    if not AuthService.is_admin(request.user):
        return Response({'error': 'Admin yetkisi gereklidir.'}, status=status.HTTP_403_FORBIDDEN)
    
    query = request.query_params.get('q', '').strip()
    rol_filter = request.query_params.get('rol', '').strip()
    
    if not query:
        return Response({'error': 'Arama kelimesi gereklidir.'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Arama query'si
    users = Kullanici.objects.filter(
        Q(ad__icontains=query) |
        Q(soyad__icontains=query) |
        Q(e_posta__icontains=query)
    ).select_related('rol')
    
    # Rol filtresi
    if rol_filter:
        users = users.filter(rol__rol_adi=rol_filter.upper())
    
    users = users.order_by('ad', 'soyad')[:50]  # Limit 50
    
    serializer = UserSearchSerializer(users, many=True)
    return Response({
        'count': users.count(),
        'results': serializer.data
    })


class HealthDataListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DanisanSaglikVerisiSerializer
        return DanisanSaglikVerisiSerializer
    
    def get_queryset(self):
        if AuthService.is_danisan(self.request.user):
            return DanisanSaglikVerisi.objects.filter(danisan=self.request.user)
        else:
            return DanisanSaglikVerisi.objects.none()
    
    @extend_schema(
        summary="Sağlık Verileri Listesi",
        description="Danışanın sağlık verilerini listeler",
    )
    def get(self, request, *args, **kwargs):
        if not AuthService.is_danisan(request.user):
            return Response({'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Sağlık Verisi Ekleme",
        description="Danışan yeni sağlık verisi ekler",
        request=DanisanSaglikVerisiSerializer
    )
    def post(self, request, *args, **kwargs):
        if not AuthService.is_danisan(request.user):
            return Response({'error': 'Bu işlem sadece danışanlar için geçerlidir.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        return super().post(request, *args, **kwargs)


class HealthDataDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DanisanSaglikVerisiUpdateSerializer
        return DanisanSaglikVerisiSerializer
    
    def get_queryset(self):
        return DanisanSaglikVerisi.objects.filter(danisan=self.request.user)
    
    @extend_schema(summary="Sağlık Verisi Detay", description="Sağlık verisi detayını görüntüler")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(summary="Sağlık Verisi Güncelle", description="Sağlık verisini günceller")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Bildirim.objects.filter(
            alici=self.request.user
        ).select_related('gonderici').order_by('-gonderim_tarihi')
    
    @extend_schema(
        summary="Bildirim Listesi",
        description="Kullanıcının bildirimlerini listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Bildirimi Okundu Olarak İşaretle",
    description="Belirli bir bildirimi okundu olarak işaretler"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, pk):
    notification = get_object_or_404(Bildirim, pk=pk, alici=request.user)
    
    if not notification.okundu:
        notification.okundu = True
        notification.okunma_tarihi = timezone.now()
        notification.save()
    
    return Response({'message': 'Bildirim okundu olarak işaretlendi.'})


@extend_schema(
    summary="Tüm Bildirimleri Okundu İşaretle",
    description="Kullanıcının tüm okunmamış bildirimlerini okundu olarak işaretler"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    updated_count = Bildirim.objects.filter(
        alici=request.user,
        okundu=False
    ).update(okundu=True, okunma_tarihi=timezone.now())
    
    return Response({
        'message': f'{updated_count} bildirim okundu olarak işaretlendi.'
    })


class PublicDiyetisyenListView(generics.ListAPIView):
    serializer_class = PublicDiyetisyenSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Diyetisyen.objects.filter(
            kullanici__is_active=True
        ).select_related('kullanici')
        
        # Uzmanlık alanı filtresi
        uzmanlik_filter = self.request.query_params.get('uzmanlik', '').strip()
        if uzmanlik_filter:
            from core.models import DiyetisyenUzmanlikAlani
            uzmanlik_diyetisyen_ids = DiyetisyenUzmanlikAlani.objects.filter(
                uzmanlik_alani__alan_adi__icontains=uzmanlik_filter
            ).values_list('diyetisyen__id', flat=True)
            queryset = queryset.filter(id__in=uzmanlik_diyetisyen_ids)
        
        # Ücret filtresi
        min_ucret = self.request.query_params.get('min_ucret', '').strip()
        max_ucret = self.request.query_params.get('max_ucret', '').strip()
        
        if min_ucret:
            queryset = queryset.filter(hizmet_ucreti__gte=min_ucret)
        if max_ucret:
            queryset = queryset.filter(hizmet_ucreti__lte=max_ucret)
        
        return queryset.order_by('kullanici__ad', 'kullanici__soyad')
    
    @extend_schema(
        summary="Diyetisyen Listesi",
        description="Aktif diyetisyenleri listeler",
        parameters=[
            {
                'name': 'uzmanlik',
                'in': 'query',
                'description': 'Uzmanlık alanı filtresi',
                'required': False,
                'schema': {'type': 'string'}
            },
            {
                'name': 'min_ucret',
                'in': 'query',
                'description': 'Minimum ücret',
                'required': False,
                'schema': {'type': 'number'}
            },
            {
                'name': 'max_ucret',
                'in': 'query',
                'description': 'Maksimum ücret',
                'required': False,
                'schema': {'type': 'number'}
            }
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UzmanlikAlaniListView(generics.ListAPIView):
    serializer_class = UzmanlikAlaniSerializer
    permission_classes = [IsAuthenticated]
    queryset = UzmanlikAlani.objects.all().order_by('alan_adi')
    
    @extend_schema(
        summary="Uzmanlık Alanları",
        description="Tüm uzmanlık alanlarını listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    @extend_schema(
        summary="Profil Güncelleme",
        description="Kullanıcı profil bilgilerini günceller",
        request=UserProfileUpdateSerializer
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


@extend_schema(
    summary="Kullanıcı İstatistikleri",
    description="Kullanıcının kendi istatistiklerini görüntüler",
    responses={200: UserStatsSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_statistics(request):
    try:
        user = request.user
        
        # Randevu istatistikleri
        randevular = Randevu.objects.filter(danisan=user)
        toplam_randevu = randevular.count()
        tamamlanan_randevu = randevular.filter(durum='TAMAMLANDI').count()
        iptal_edilen_randevu = randevular.filter(durum='IPTAL_EDILDI').count()
        
        # Aktif diyetisyen
        aktif_esleme = DanisanDiyetisyenEslesme.objects.filter(
            danisan=user
        ).select_related('diyetisyen__kullanici').first()
        
        aktif_diyetisyen = None
        if aktif_esleme:
            diyetisyen = aktif_esleme.diyetisyen.kullanici
            aktif_diyetisyen = f"{diyetisyen.ad} {diyetisyen.soyad}"
        
        # Son randevu tarihi
        son_randevu = randevular.order_by('-randevu_tarih_saat').first()
        son_randevu_tarihi = son_randevu.randevu_tarih_saat.date() if son_randevu else None
        
        # Üyelik süresi
        uyelik_suresi = (timezone.now().date() - user.date_joined.date()).days
        
        stats = {
            'toplam_randevu': toplam_randevu,
            'tamamlanan_randevu': tamamlanan_randevu,
            'iptal_edilen_randevu': iptal_edilen_randevu,
            'aktif_diyetisyen': aktif_diyetisyen,
            'son_randevu_tarihi': son_randevu_tarihi,
            'uyelik_suresi': uyelik_suresi
        }
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)