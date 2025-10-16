from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import Kullanici, Rol, UzmanlikAlani, Diyetisyen
from .serializers import KullaniciSerializer


class DanisanRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = Kullanici
        fields = ('e_posta', 'password', 'password_confirm', 'ad', 'soyad', 'telefon')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Şifreler eşleşmiyor.")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Danışan rolünü al
        danisan_rol, _ = Rol.objects.get_or_create(rol_adi='danisan')
        
        user = Kullanici.objects.create_user(
            password=password,
            rol=danisan_rol,
            **validated_data
        )
        return user


class DiyetisyenRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    # Diyetisyen özel alanları (mevcut model alanlarına uygun)
    universite = serializers.CharField(max_length=200, required=False, allow_blank=True)
    hakkinda_bilgi = serializers.CharField(required=False, allow_blank=True)
    hizmet_ucreti = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    uzmanlik_alanlari = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=10,
        help_text="En az 1, en fazla 10 uzmanlık alanı"
    )
    
    class Meta:
        model = Kullanici
        fields = (
            'e_posta', 'password', 'password_confirm', 'ad', 'soyad', 'telefon',
            'universite', 'hakkinda_bilgi', 'hizmet_ucreti', 'uzmanlik_alanlari'
        )
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Şifreler eşleşmiyor.")
        
        return attrs
    
    def validate_uzmanlik_alanlari(self, value):
        # Geçerli uzmanlık alanları listesi
        valid_areas = [
            'Klinik Beslenme',
            'Spor Beslenmesi',
            'Pediatrik Beslenme',
            'Obezite ve Kilo Yönetimi',
            'Diyabet Beslenmesi',
            'Kardiyovasküler Beslenme',
            'Onkolojik Beslenme',
            'Geriatrik Beslenme',
            'Vegetaryen/Vegan Beslenme',
            'Fonksiyonel Beslenme'
        ]
        
        for alan in value:
            if alan not in valid_areas:
                raise serializers.ValidationError(f"'{alan}' geçerli bir uzmanlık alanı değil.")
        
        return value
    
    def create(self, validated_data):
        # Diyetisyen özel verilerini ayır
        universite = validated_data.pop('universite', '')
        hakkinda_bilgi = validated_data.pop('hakkinda_bilgi', '')
        hizmet_ucreti = validated_data.pop('hizmet_ucreti', 0.00)
        uzmanlik_alanlari = validated_data.pop('uzmanlik_alanlari')
        
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Diyetisyen rolünü al
        diyetisyen_rol, _ = Rol.objects.get_or_create(rol_adi='diyetisyen')
        
        # Kullanıcı oluştur (başlangıçta deaktif)
        user = Kullanici.objects.create_user(
            password=password,
            rol=diyetisyen_rol,
            is_active=False,  # Admin onayı bekliyor
            **validated_data
        )
        
        # Diyetisyen profili oluştur (mevcut model alanları ile)
        diyetisyen = Diyetisyen.objects.create(
            kullanici=user,
            universite=universite,
            hakkinda_bilgi=hakkinda_bilgi,
            hizmet_ucreti=hizmet_ucreti
        )
        
        # Uzmanlık alanlarını ekle (many-to-many ilişki ile)
        from core.models import DiyetisyenUzmanlikAlani
        for alan_adi in uzmanlik_alanlari:
            uzmanlik_alani, _ = UzmanlikAlani.objects.get_or_create(alan_adi=alan_adi)
            DiyetisyenUzmanlikAlani.objects.create(
                diyetisyen=diyetisyen,
                uzmanlik_alani=uzmanlik_alani
            )
        
        return user


class DiyetisyenDetailSerializer(serializers.ModelSerializer):
    kullanici = KullaniciSerializer(read_only=True)
    uzmanlik_alanlari = serializers.StringRelatedField(many=True, read_only=True)
    
    class Meta:
        model = Diyetisyen
        fields = [
            'id', 'kullanici', 'deneyim_yili', 'egitim_bilgileri',
            'sertifikalar', 'onay_durumu', 'onay_tarihi', 'aktif',
            'uzmanlik_alanlari'
        ]


class RegistrationResponseSerializer(serializers.Serializer):
    user = KullaniciSerializer()
    message = serializers.CharField()
    # Diyetisyen için token yok (onay beklediği için)
    access = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)