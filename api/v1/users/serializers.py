from rest_framework import serializers
from core.models import (
    Kullanici, DanisanSaglikVerisi, Bildirim, UzmanlikAlani, 
    Diyetisyen, DiyetisyenUzmanlikAlani
)
from api.v1.auth.serializers import KullaniciSerializer


class UserSearchSerializer(serializers.ModelSerializer):
    rol_adi = serializers.CharField(source='rol.rol_adi', read_only=True)
    
    class Meta:
        model = Kullanici
        fields = ['id', 'e_posta', 'ad', 'soyad', 'telefon', 'rol_adi', 'is_active', 'date_joined', 'son_giris_tarihi']


class DanisanSaglikVerisiSerializer(serializers.ModelSerializer):
    class Meta:
        model = DanisanSaglikVerisi
        fields = [
            'id', 'boy', 'kilo', 'hedef_kilo', 'dogum_tarihi', 'cinsiyet',
            'aktivite_seviyesi', 'saglik_durumu', 'alerjiler', 'kullandigi_ilaclar',
            'kayit_tarihi'
        ]
        read_only_fields = ['id', 'kayit_tarihi']
    
    def create(self, validated_data):
        validated_data['danisan'] = self.context['request'].user
        return super().create(validated_data)


class DanisanSaglikVerisiUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DanisanSaglikVerisi
        fields = [
            'boy', 'kilo', 'hedef_kilo', 'aktivite_seviyesi', 
            'saglik_durumu', 'alerjiler', 'kullandigi_ilaclar'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    gonderici_adi = serializers.CharField(source='gonderici.ad', read_only=True)
    gonderici_soyadi = serializers.CharField(source='gonderici.soyad', read_only=True)
    
    class Meta:
        model = Bildirim
        fields = [
            'id', 'baslik', 'icerik', 'gonderici', 'gonderici_adi', 'gonderici_soyadi',
            'okundu', 'gonderim_tarihi', 'okunma_tarihi'
        ]
        read_only_fields = ['id', 'gonderim_tarihi', 'okunma_tarihi']


class NotificationCreateSerializer(serializers.ModelSerializer):
    alici_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Bildirim
        fields = ['alici_id', 'baslik', 'icerik']
    
    def validate_alici_id(self, value):
        try:
            Kullanici.objects.get(id=value)
        except Kullanici.DoesNotExist:
            raise serializers.ValidationError("Geçersiz kullanıcı ID.")
        return value
    
    def create(self, validated_data):
        alici_id = validated_data.pop('alici_id')
        validated_data['alici'] = Kullanici.objects.get(id=alici_id)
        validated_data['gonderici'] = self.context['request'].user
        return super().create(validated_data)


class UzmanlikAlaniSerializer(serializers.ModelSerializer):
    class Meta:
        model = UzmanlikAlani
        fields = ['id', 'alan_adi']


class PublicDiyetisyenSerializer(serializers.ModelSerializer):
    kullanici = KullaniciSerializer(read_only=True)
    uzmanlik_alanlari = serializers.SerializerMethodField()
    ortalama_puan = serializers.SerializerMethodField()
    randevu_sayisi = serializers.SerializerMethodField()
    
    class Meta:
        model = Diyetisyen
        fields = [
            'kullanici', 'universite', 'hakkinda_bilgi', 'profil_fotografi',
            'hizmet_ucreti', 'uzmanlik_alanlari', 'ortalama_puan', 'randevu_sayisi'
        ]
    
    def get_uzmanlik_alanlari(self, obj):
        uzmanliklar = DiyetisyenUzmanlikAlani.objects.filter(diyetisyen=obj)
        return [uz.uzmanlik_alani.alan_adi for uz in uzmanliklar]
    
    def get_ortalama_puan(self, obj):
        # Değerlendirme sistemi eklendikten sonra gerçek puan hesaplanacak
        return 4.5
    
    def get_randevu_sayisi(self, obj):
        from core.models import Randevu
        return Randevu.objects.filter(diyetisyen=obj, durum='TAMAMLANDI').count()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kullanici
        fields = ['ad', 'soyad', 'telefon']
    
    def validate_telefon(self, value):
        if value and not value.startswith('+'):
            raise serializers.ValidationError("Telefon numarası + ile başlamalıdır.")
        return value


class UserStatsSerializer(serializers.Serializer):
    toplam_randevu = serializers.IntegerField()
    tamamlanan_randevu = serializers.IntegerField()
    iptal_edilen_randevu = serializers.IntegerField()
    aktif_diyetisyen = serializers.CharField(allow_null=True)
    son_randevu_tarihi = serializers.DateField(allow_null=True)
    uyelik_suresi = serializers.IntegerField()  # Gün cinsinden