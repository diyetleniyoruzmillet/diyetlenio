from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import Kullanici, Rol


class KullaniciSerializer(serializers.ModelSerializer):
    rol_adi = serializers.CharField(source='rol.rol_adi', read_only=True)
    
    class Meta:
        model = Kullanici
        fields = ('id', 'e_posta', 'ad', 'soyad', 'telefon', 'rol_adi', 'date_joined', 'is_active')
        read_only_fields = ('id', 'date_joined', 'rol_adi')


class LoginSerializer(serializers.Serializer):
    e_posta = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        e_posta = attrs.get('e_posta')
        password = attrs.get('password')
        
        if e_posta and password:
            user = authenticate(username=e_posta, password=password)
            
            if not user:
                raise serializers.ValidationError('Geçersiz email veya şifre.')
            
            if not user.is_active:
                raise serializers.ValidationError('Kullanıcı hesabı deaktif durumda.')
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Email ve şifre alanları gereklidir.')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    rol_adi = serializers.CharField(write_only=True)
    
    class Meta:
        model = Kullanici
        fields = ('e_posta', 'password', 'password_confirm', 'ad', 'soyad', 'telefon', 'rol_adi')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Şifreler eşleşmiyor.")
        return attrs
    
    def validate_rol_adi(self, value):
        if value not in ['danisan', 'diyetisyen']:
            raise serializers.ValidationError("Geçersiz rol. Sadece DANISAN veya DIYETISYEN olabilir.")
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        rol_adi = validated_data.pop('rol_adi')
        
        # Rol nesnesini bul veya oluştur
        rol, created = Rol.objects.get_or_create(rol_adi=rol_adi)
        
        user = Kullanici.objects.create_user(
            password=password,
            rol=rol,
            **validated_data
        )
        return user


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = KullaniciSerializer()


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mevcut şifre hatalı.")
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Yeni şifreler eşleşmiyor.")
        return attrs
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user