from rest_framework import serializers
from core.models import Sikayet, PromosyonKodu, Kullanici, Randevu
from django.utils import timezone


class SikayetSerializer(serializers.ModelSerializer):
    sikayet_eden_adi = serializers.CharField(source='sikayet_eden.ad', read_only=True)
    sikayet_eden_soyadi = serializers.CharField(source='sikayet_eden.soyad', read_only=True)
    sikayet_edilen_adi = serializers.CharField(source='sikayet_edilen.ad', read_only=True)
    sikayet_edilen_soyadi = serializers.CharField(source='sikayet_edilen.soyad', read_only=True)
    randevu_tarihi = serializers.DateTimeField(source='randevu.randevu_tarih_saat', read_only=True)
    
    class Meta:
        model = Sikayet
        fields = [
            'id', 'sikayet_tipi', 'sikayet_metni', 'sikayet_tarihi', 'cozum_durumu',
            'sikayet_eden_adi', 'sikayet_eden_soyadi',
            'sikayet_edilen_adi', 'sikayet_edilen_soyadi',
            'randevu_tarihi'
        ]
        read_only_fields = ['id', 'sikayet_tarihi', 'cozum_durumu']


class SikayetCreateSerializer(serializers.ModelSerializer):
    sikayet_edilen_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    randevu_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Sikayet
        fields = ['sikayet_edilen_id', 'randevu_id', 'sikayet_tipi', 'sikayet_metni']
    
    def validate_sikayet_edilen_id(self, value):
        if value:
            try:
                Kullanici.objects.get(id=value)
            except Kullanici.DoesNotExist:
                raise serializers.ValidationError("Geçersiz kullanıcı ID.")
        return value
    
    def validate_randevu_id(self, value):
        if value:
            try:
                randevu = Randevu.objects.get(id=value)
                # Randevunun şikayet eden kişiye ait olup olmadığını kontrol et
                request_user = self.context['request'].user
                if randevu.danisan != request_user and randevu.diyetisyen.kullanici != request_user:
                    raise serializers.ValidationError("Bu randevuya erişim yetkiniz yok.")
            except Randevu.DoesNotExist:
                raise serializers.ValidationError("Geçersiz randevu ID.")
        return value
    
    def create(self, validated_data):
        sikayet_edilen_id = validated_data.pop('sikayet_edilen_id', None)
        randevu_id = validated_data.pop('randevu_id', None)
        
        validated_data['sikayet_eden'] = self.context['request'].user
        validated_data['cozum_durumu'] = 'ACIK'
        
        if sikayet_edilen_id:
            validated_data['sikayet_edilen'] = Kullanici.objects.get(id=sikayet_edilen_id)
        
        if randevu_id:
            validated_data['randevu'] = Randevu.objects.get(id=randevu_id)
        
        return super().create(validated_data)


class AdminSikayetSerializer(serializers.ModelSerializer):
    """Admin için detaylı şikayet serializer"""
    sikayet_eden_email = serializers.EmailField(source='sikayet_eden.e_posta', read_only=True)
    sikayet_edilen_email = serializers.EmailField(source='sikayet_edilen.e_posta', read_only=True)
    
    class Meta:
        model = Sikayet
        fields = [
            'id', 'sikayet_tipi', 'sikayet_metni', 'sikayet_tarihi', 'cozum_durumu',
            'sikayet_eden_adi', 'sikayet_eden_soyadi', 'sikayet_eden_email',
            'sikayet_edilen_adi', 'sikayet_edilen_soyadi', 'sikayet_edilen_email',
            'randevu_tarihi'
        ]
        read_only_fields = ['id', 'sikayet_tarihi']


class SikayetCozumSerializer(serializers.Serializer):
    cozum_durumu = serializers.ChoiceField(
        choices=[('COZULDU', 'Çözüldü'), ('REDDEDILDI', 'Reddedildi')]
    )
    cozum_notu = serializers.CharField(required=False, allow_blank=True)


# Promosyon Kodu Serializers
class PromosyonKoduSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromosyonKodu
        fields = [
            'id', 'kod', 'indirim_miktari', 'indirim_tipi', 'kullanim_limiti',
            'kullanilma_sayisi', 'baslangic_tarihi', 'bitis_tarihi', 'aktif_mi'
        ]
        read_only_fields = ['id', 'kullanilma_sayisi']


class PromosyonKoduCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromosyonKodu
        fields = [
            'kod', 'indirim_miktari', 'indirim_tipi', 'kullanim_limiti',
            'baslangic_tarihi', 'bitis_tarihi', 'aktif_mi'
        ]
    
    def validate_kod(self, value):
        if PromosyonKodu.objects.filter(kod=value).exists():
            raise serializers.ValidationError("Bu promosyon kodu zaten mevcut.")
        return value.upper()
    
    def validate_baslangic_tarihi(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Başlangıç tarihi bugünden önce olamaz.")
        return value
    
    def validate(self, data):
        if data['bitis_tarihi'] <= data['baslangic_tarihi']:
            raise serializers.ValidationError("Bitiş tarihi başlangıç tarihinden sonra olmalıdır.")
        return data


class PromosyonKoduKullanimSerializer(serializers.Serializer):
    """Promosyon kodu kullanımı için"""
    kod = serializers.CharField(max_length=50)
    
    def validate_kod(self, value):
        kod_upper = value.upper()
        try:
            promo_kod = PromosyonKodu.objects.get(kod=kod_upper, aktif_mi=True)
        except PromosyonKodu.DoesNotExist:
            raise serializers.ValidationError("Geçersiz promosyon kodu.")
        
        # Tarihi kontrol et
        today = timezone.now().date()
        if today < promo_kod.baslangic_tarihi or today > promo_kod.bitis_tarihi:
            raise serializers.ValidationError("Promosyon kodu süresi dolmuş veya henüz aktif değil.")
        
        # Kullanım limiti kontrol et
        if promo_kod.kullanilma_sayisi >= promo_kod.kullanim_limiti:
            raise serializers.ValidationError("Promosyon kodu kullanım limiti dolmuş.")
        
        return kod_upper


class PromosyonKoduResponseSerializer(serializers.Serializer):
    """Promosyon kodu kullanım response"""
    gecerli = serializers.BooleanField()
    indirim_miktari = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    indirim_tipi = serializers.CharField(required=False)
    mesaj = serializers.CharField()