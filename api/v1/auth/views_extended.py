from rest_framework import status, generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from core.models import Diyetisyen
from .serializers import KullaniciSerializer
from .serializers_extended import (
    DanisanRegisterSerializer, 
    DiyetisyenRegisterSerializer,
    RegistrationResponseSerializer
)


class DanisanRegisterView(generics.CreateAPIView):
    serializer_class = DanisanRegisterSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Danışan Kaydı",
        description="Danışan olarak platform kayıt işlemi",
        request=DanisanRegisterSerializer,
        responses={
            201: OpenApiResponse(response=RegistrationResponseSerializer, description="Başarılı kayıt"),
            400: OpenApiResponse(description="Geçersiz veriler")
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Danışan için hemen token ver
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': KullaniciSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'message': 'Danışan hesabınız başarıyla oluşturuldu! Hemen giriş yapabilirsiniz.'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DiyetisyenRegisterView(generics.CreateAPIView):
    serializer_class = DiyetisyenRegisterSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Diyetisyen Başvurusu",
        description="Diyetisyen olarak platform başvuru işlemi. Admin onayı gerektirir.",
        request=DiyetisyenRegisterSerializer,
        responses={
            201: OpenApiResponse(response=RegistrationResponseSerializer, description="Başvuru alındı"),
            400: OpenApiResponse(description="Geçersiz veriler")
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Diyetisyen için token verme (henüz aktif değil)
            return Response({
                'user': KullaniciSerializer(user).data,
                'message': 'Diyetisyen başvurunuz alınmıştır. Admin onayından sonra hesabınız aktif olacaktır. '
                          'Onay durumunuz hakkında e-posta ile bilgilendirileceksiniz.'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DiyetisyenPendingListView(generics.ListAPIView):
    """Admin için onay bekleyen diyetisyenler"""
    from core.models import Diyetisyen
    from .serializers_extended import DiyetisyenDetailSerializer
    
    serializer_class = DiyetisyenDetailSerializer
    
    def get_queryset(self):
        # Sadece admin görebilir
        if not hasattr(self.request.user, 'rol') or self.request.user.rol.rol_adi != 'admin':
            return self.serializer_class.Meta.model.objects.none()
        
        return Diyetisyen.objects.filter(
            onay_durumu='BEKLEMEDE'
        ).select_related('kullanici').prefetch_related('uzmanlik_alanlari')
    
    @extend_schema(
        summary="Onay Bekleyen Diyetisyenler",
        description="Admin için onay bekleyen diyetisyen başvurularını listeler",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)