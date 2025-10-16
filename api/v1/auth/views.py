from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    LoginSerializer, RegisterSerializer, KullaniciSerializer,
    TokenResponseSerializer, PasswordChangeSerializer
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = LoginSerializer
    
    @extend_schema(
        summary="Kullanıcı Girişi",
        description="Email ve şifre ile giriş yaparak JWT token alın",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(response=TokenResponseSerializer, description="Başarılı giriş"),
            400: OpenApiResponse(description="Geçersiz bilgiler")
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': KullaniciSerializer(user).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Kullanıcı Kaydı",
        description="Yeni kullanıcı kaydı oluşturun",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(response=TokenResponseSerializer, description="Başarılı kayıt"),
            400: OpenApiResponse(description="Geçersiz veriler")
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': KullaniciSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = KullaniciSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Kullanıcı Profili",
        description="Giriş yapmış kullanıcının profil bilgilerini görüntüle veya güncelle",
        responses={
            200: OpenApiResponse(response=KullaniciSerializer, description="Profil bilgileri")
        }
    )
    def get_object(self):
        return self.request.user


class PasswordChangeView(generics.GenericAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Şifre Değiştir",
        description="Kullanıcının şifresini değiştirin",
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Şifre başarıyla değiştirildi"),
            400: OpenApiResponse(description="Geçersiz veriler")
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Şifre başarıyla değiştirildi.'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Çıkış Yap",
    description="Kullanıcının oturumunu sonlandır",
    responses={
        200: OpenApiResponse(description="Başarılı çıkış")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Başarıyla çıkış yapıldı.'})
    except Exception:
        return Response({'message': 'Çıkış yapıldı.'})


@extend_schema(
    summary="Kullanıcı Doğrulama",
    description="JWT token ile kullanıcı bilgilerini doğrula",
    responses={
        200: OpenApiResponse(response=KullaniciSerializer, description="Kullanıcı bilgileri")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token(request):
    return Response({
        'user': KullaniciSerializer(request.user).data,
        'message': 'Token geçerli.'
    })