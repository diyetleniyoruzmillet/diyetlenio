from rest_framework import generics, status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from datetime import datetime

from core.models import (
    Randevu, Musaitlik, DiyetisyenMusaitlikSablon,
    DiyetisyenIzin, Diyetisyen
)
from django.utils import timezone
from core.services.randevu_service import RandevuService
from core.services.musaitlik_service import MusaitlikService
from .serializers import (
    RandevuSerializer, RandevuCreateSerializer, MusaitlikSerializer,
    RandevuCancelSerializer, DiyetisyenMusaitlikSablonSerializer,
    DiyetisyenIzinSerializer, AvailabilityRequestSerializer
)


class RandevuListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RandevuCreateSerializer
        return RandevuSerializer
    
    def get_queryset(self):
        return RandevuService.get_user_randevular(self.request.user)
    
    @extend_schema(
        summary="Randevu Listesi",
        description="Kullanıcının randevularını listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Yeni Randevu Oluştur",
        description="Danışan için yeni randevu oluşturur",
        request=RandevuCreateSerializer
    )
    def post(self, request, *args, **kwargs):
        if request.user.rol.rol_adi != 'danisan':
            return Response(
                {'error': 'Sadece danışanlar randevu oluşturabilir.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Combine date and time into datetime
            from datetime import datetime, time as dt_time
            tarih = serializer.validated_data['tarih']
            saat = serializer.validated_data['saat']
            
            # Create datetime from date and time
            if isinstance(saat, str):
                saat = datetime.strptime(saat, '%H:%M:%S').time()
            elif isinstance(saat, dt_time):
                pass  # Already time object
            
            randevu_datetime = timezone.make_aware(datetime.combine(tarih, saat))
            
            # Create appointment directly (simplified for now)
            # Find available diyetisyen (simplified assignment)
            from core.models import Diyetisyen
            available_diyetisyen = Diyetisyen.objects.filter(onay_durumu='ONAYLANDI').first()
            
            randevu = Randevu.objects.create(
                danisan=request.user,
                diyetisyen=available_diyetisyen,  # Assign first available diyetisyen
                randevu_tarih_saat=randevu_datetime,
                randevu_turu='ONLINE',
                durum='BEKLEMEDE' if available_diyetisyen else 'BEKLEMEDE',
                tip=serializer.validated_data.get('tip', 'UCRETLI')
            )
            
            return Response(
                RandevuSerializer(randevu).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RandevuDetailView(generics.RetrieveAPIView):
    serializer_class = RandevuSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return RandevuService.get_user_randevular(self.request.user)
    
    @extend_schema(
        summary="Randevu Detayı",
        description="Belirli bir randevunun detaylarını görüntüler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Randevu İptal Et",
    description="Randevuyu iptal eder",
    request=RandevuCancelSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_randevu(request, pk):
    randevu = get_object_or_404(Randevu, pk=pk)
    
    # Yetki kontrolü
    if (request.user not in [randevu.danisan, randevu.diyetisyen] and 
        request.user.rol.rol_adi != 'admin'):
        return Response(
            {'error': 'Bu randevuyu iptal etme yetkiniz yok.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = RandevuCancelSerializer(
        data=request.data,
        context={'randevu': randevu, 'request': request}
    )
    
    if serializer.is_valid():
        try:
            RandevuService.cancel_randevu(
                randevu=randevu,
                cancelled_by=request.user,
                reason=serializer.validated_data.get('iptal_sebebi')
            )
            
            return Response({
                'message': 'Randevu başarıyla iptal edildi.',
                'randevu': RandevuSerializer(randevu).data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MusaitlikListView(generics.ListAPIView):
    serializer_class = MusaitlikSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Müsait Saatler",
        description="Belirli tarih için müsait saatleri listeler",
        parameters=[
            {
                'name': 'tarih',
                'in': 'query',
                'description': 'Tarih (YYYY-MM-DD)',
                'required': True,
                'schema': {'type': 'string', 'format': 'date'}
            },
            {
                'name': 'diyetisyen',
                'in': 'query',
                'description': 'Diyetisyen ID (opsiyonel)',
                'required': False,
                'schema': {'type': 'integer'}
            }
        ]
    )
    def get(self, request, *args, **kwargs):
        tarih = request.query_params.get('tarih')
        diyetisyen_id = request.query_params.get('diyetisyen')
        
        if not tarih:
            return Response(
                {'error': 'Tarih parametresi gereklidir.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        diyetisyen = None
        if diyetisyen_id:
            try:
                from core.models import Kullanici
                diyetisyen = Kullanici.objects.get(id=diyetisyen_id, rol__rol_adi='diyetisyen')
            except Kullanici.DoesNotExist:
                return Response(
                    {'error': 'Diyetisyen bulunamadı.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        self.queryset = RandevuService.get_available_slots(tarih, diyetisyen)
        return super().get(request, *args, **kwargs)


@extend_schema(
    summary="Randevu Tamamla",
    description="Randevuyu tamamla (sadece diyetisyen)"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_randevu(request, pk):
    if request.user.rol.rol_adi != 'diyetisyen':
        return Response(
            {'error': 'Sadece diyetisyenler randevu tamamlayabilir.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    randevu = get_object_or_404(Randevu, pk=pk, diyetisyen=request.user)
    
    try:
        completion_notes = request.data.get('notlar')
        RandevuService.complete_randevu(randevu, completion_notes)
        
        return Response({
            'message': 'Randevu başarıyla tamamlandı.',
            'randevu': RandevuSerializer(randevu).data
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# Müsaitlik Management API Views

@extend_schema(
    summary="Müsait Saatler",
    description="Belirli tarih aralığında müsait saatleri getir",
    parameters=[
        {
            'name': 'start_date',
            'in': 'query',
            'description': 'Başlangıç tarihi (YYYY-MM-DD)',
            'required': True,
            'schema': {'type': 'string', 'format': 'date'}
        },
        {
            'name': 'end_date',
            'in': 'query',
            'description': 'Bitiş tarihi (YYYY-MM-DD)',
            'required': True,
            'schema': {'type': 'string', 'format': 'date'}
        },
        {
            'name': 'diyetisyen',
            'in': 'query',
            'description': 'Diyetisyen ID',
            'required': True,
            'schema': {'type': 'integer'}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def availability_view(request):
    serializer = AvailabilityRequestSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici_id=data['diyetisyen'])
    except Diyetisyen.DoesNotExist:
        return Response(
            {'error': 'Diyetisyen bulunamadı.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    available_slots = MusaitlikService.get_available_slots(
        diyetisyen=diyetisyen,
        start_date=data['start_date'],
        end_date=data['end_date']
    )
    
    return Response(available_slots)


class DiyetisyenMusaitlikSablonListCreateView(generics.ListCreateAPIView):
    serializer_class = DiyetisyenMusaitlikSablonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'diyetisyen'):
            return MusaitlikService.get_diyetisyen_musaitlik_sablonu(
                self.request.user.diyetisyen
            )
        return DiyetisyenMusaitlikSablon.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'diyetisyen'):
            raise PermissionError("Sadece diyetisyenler müsaitlik ekleyebilir.")
        serializer.save(diyetisyen=self.request.user.diyetisyen)
    
    @extend_schema(
        summary="Diyetisyen Müsaitlik Şablonları",
        description="Diyetisyenin haftalık çalışma saatlerini listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Müsaitlik Şablonu Ekle",
        description="Diyetisyen için yeni müsaitlik şablonu ekler",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DiyetisyenMusaitlikSablonDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DiyetisyenMusaitlikSablonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'diyetisyen'):
            return DiyetisyenMusaitlikSablon.objects.filter(
                diyetisyen=self.request.user.diyetisyen
            )
        return DiyetisyenMusaitlikSablon.objects.none()


class DiyetisyenIzinListCreateView(generics.ListCreateAPIView):
    serializer_class = DiyetisyenIzinSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'diyetisyen'):
            return MusaitlikService.get_diyetisyen_izinler(
                self.request.user.diyetisyen
            )
        return DiyetisyenIzin.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'diyetisyen'):
            raise PermissionError("Sadece diyetisyenler izin ekleyebilir.")
        
        try:
            MusaitlikService.create_izin(
                diyetisyen=self.request.user.diyetisyen,
                izin_data=serializer.validated_data
            )
        except Exception as e:
            raise serializers.ValidationError(str(e))
    
    @extend_schema(
        summary="Diyetisyen İzinleri",
        description="Diyetisyenin izin günlerini listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="İzin Ekle",
        description="Diyetisyen için yeni izin ekler",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DiyetisyenIzinDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DiyetisyenIzinSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'diyetisyen'):
            return DiyetisyenIzin.objects.filter(
                diyetisyen=self.request.user.diyetisyen
            )
        return DiyetisyenIzin.objects.none()
    
    def perform_destroy(self, instance):
        try:
            MusaitlikService.delete_izin(
                izin_id=instance.id,
                diyetisyen=self.request.user.diyetisyen
            )
        except Exception as e:
            raise serializers.ValidationError(str(e))


@extend_schema(
    summary="Haftalık Program",
    description="Diyetisyenin haftalık çalışma programını getir",
    parameters=[
        {
            'name': 'week_start',
            'in': 'query',
            'description': 'Hafta başlangıç tarihi (YYYY-MM-DD)',
            'required': True,
            'schema': {'type': 'string', 'format': 'date'}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weekly_schedule_view(request):
    if not hasattr(request.user, 'diyetisyen'):
        return Response(
            {'error': 'Sadece diyetisyenler erişebilir.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    week_start_str = request.query_params.get('week_start')
    if not week_start_str:
        return Response(
            {'error': 'week_start parametresi gereklidir.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Geçersiz tarih formatı. YYYY-MM-DD kullanın.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    schedule = MusaitlikService.get_weekly_schedule(
        diyetisyen=request.user.diyetisyen,
        week_start_date=week_start
    )
    
    return Response(schedule)


@extend_schema(
    summary="Meeting Room Oluştur/Al",
    description="Randevu için online görüşme odası oluşturur veya mevcut odayı döner"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_meeting_room(request, pk):
    randevu = get_object_or_404(Randevu, pk=pk)
    
    # Yetki kontrolü - sadece randevuya katılan kişiler
    if request.user not in [randevu.danisan, randevu.diyetisyen]:
        return Response(
            {'error': 'Bu randevuya erişim yetkiniz yok.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Randevu durumu kontrolü
    if randevu.durum != 'ONAYLANDI':
        return Response(
            {'error': 'Sadece onaylanmış randevular için görüşme odası oluşturulabilir.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Randevu türü kontrolü
    if randevu.randevu_turu != 'ONLINE':
        return Response(
            {'error': 'Bu randevu online görüşme türünde değil.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Zaman kontrolü - randevu saatinden 15 dakika önce erişim
    from django.utils import timezone
    from datetime import timedelta
    
    randevu_datetime = timezone.make_aware(
        timezone.datetime.combine(randevu.tarih, randevu.saat)
    )
    access_time = randevu_datetime - timedelta(minutes=15)
    
    if timezone.now() < access_time:
        return Response(
            {'error': f'Görüşme odasına {access_time.strftime("%H:%M")} saatinden sonra erişebilirsiniz.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Meeting URL varsa döner, yoksa oluşturur
    if not randevu.kamera_linki:
        # Basit meeting room URL'i oluştur
        import uuid
        room_id = str(uuid.uuid4())[:8]
        randevu.kamera_linki = f"https://meet.diyetlenio.com/{room_id}"
        randevu.save()
    
    return Response({
        'success': True,
        'meeting_url': randevu.kamera_linki,
        'randevu_id': randevu.id,
        'participants': {
            'danisan': f"{randevu.danisan.ad} {randevu.danisan.soyad}",
            'diyetisyen': f"{randevu.diyetisyen.kullanici.ad} {randevu.diyetisyen.kullanici.soyad}"
        }
    })