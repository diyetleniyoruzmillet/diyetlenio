from rest_framework import serializers
from core.models import (
    Diyetisyen, Musaitlik, DanisanDiyetisyenEslesme, 
    DiyetisyenNot, Kullanici, DiyetisyenUzmanlikAlani
)
from api.v1.auth.serializers import KullaniciSerializer


class DiyetisyenProfileSerializer(serializers.ModelSerializer):
    kullanici = KullaniciSerializer(read_only=True)
    uzmanlik_alanlari = serializers.SerializerMethodField()
    
    class Meta:
        model = Diyetisyen
        fields = [
            'kullanici', 'universite', 'hakkinda_bilgi', 'profil_fotografi',
            'hizmet_ucreti', 'uzmanlik_alanlari'
        ]
    
    def get_uzmanlik_alanlari(self, obj):
        uzmanliklar = DiyetisyenUzmanlikAlani.objects.filter(diyetisyen=obj)
        return [uz.uzmanlik_alani.alan_adi for uz in uzmanliklar]


class DiyetisyenProfileUpdateSerializer(serializers.ModelSerializer):
    universite = serializers.CharField(max_length=200, required=False, allow_blank=True)
    hakkinda_bilgi = serializers.CharField(required=False, allow_blank=True)
    hizmet_ucreti = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    profil_fotografi = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = Diyetisyen
        fields = ['universite', 'hakkinda_bilgi', 'hizmet_ucreti', 'profil_fotografi']


class MusaitlikSerializer(serializers.ModelSerializer):
    class Meta:
        model = Musaitlik
        fields = ['id', 'tarih', 'saat', 'musait']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        # Diyetisyen bilgisini request'ten al
        validated_data['diyetisyen'] = self.context['request'].user.diyetisyen
        return super().create(validated_data)


class MusaitlikBulkCreateSerializer(serializers.Serializer):
    tarih = serializers.DateField()
    saatler = serializers.ListField(
        child=serializers.TimeField(),
        min_length=1,
        max_length=20,
        help_text="Müsait saatler listesi"
    )
    
    def validate_saatler(self, value):
        # Saatlerin çakışmamasını kontrol et
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Aynı saat birden fazla kez eklenemez.")
        return value
    
    def create(self, validated_data):
        diyetisyen = self.context['request'].user.diyetisyen
        tarih = validated_data['tarih']
        saatler = validated_data['saatler']
        
        created_musaitlik = []
        for saat in saatler:
            musaitlik, created = Musaitlik.objects.get_or_create(
                diyetisyen=diyetisyen,
                tarih=tarih,
                saat=saat,
                defaults={'musait': True}
            )
            if created:
                created_musaitlik.append(musaitlik)
        
        return created_musaitlik


class AssignedClientSerializer(serializers.ModelSerializer):
    danisan_bilgileri = KullaniciSerializer(source='danisan', read_only=True)
    esleme_tarihi = serializers.DateTimeField(source='eslesme_tarihi', read_only=True)
    
    class Meta:
        model = DanisanDiyetisyenEslesme
        fields = [
            'id', 'danisan_bilgileri', 'esleme_tarihi', 'durum',
            'on_gorusme_yapildi_mi', 'hasta_mi'
        ]


class DiyetisyenNotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiyetisyenNot
        fields = ['danisan', 'baslik', 'not_metin', 'sadece_diyetisyen_gorsun']
    
    def create(self, validated_data):
        # Diyetisyen ve oluşturan bilgisini ekle
        validated_data['diyetisyen'] = self.context['request'].user.diyetisyen
        validated_data['olusturan'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_danisan(self, value):
        diyetisyen = self.context['request'].user.diyetisyen
        # Danışanın bu diyetisyene atanmış olduğunu kontrol et
        if not DanisanDiyetisyenEslesme.objects.filter(
            diyetisyen=diyetisyen,
            danisan=value,
            durum='AKTIF'
        ).exists():
            raise serializers.ValidationError("Bu danışan size atanmamış.")
        return value


class DiyetisyenNotSerializer(serializers.ModelSerializer):
    danisan_adi = serializers.CharField(source='danisan.ad', read_only=True)
    danisan_soyadi = serializers.CharField(source='danisan.soyad', read_only=True)
    olusturan_adi = serializers.CharField(source='olusturan.ad', read_only=True)
    
    class Meta:
        model = DiyetisyenNot
        fields = [
            'id', 'danisan', 'danisan_adi', 'danisan_soyadi', 'baslik', 'not_metin',
            'sadece_diyetisyen_gorsun', 'olusturan_adi', 'olusma_tarihi', 
            'guncelleme_tarihi', 'silindi'
        ]
        read_only_fields = ['id', 'olusma_tarihi', 'guncelleme_tarihi']


class DiyetisyenEarningsSerializer(serializers.Serializer):
    donem = serializers.CharField(help_text="Örnek: '2025-01' veya '2025-01-15'")
    toplam_randevu = serializers.IntegerField()
    tamamlanan_randevu = serializers.IntegerField()
    brut_kazanc = serializers.DecimalField(max_digits=10, decimal_places=2)
    komisyon_kesintisi = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_kazanc = serializers.DecimalField(max_digits=10, decimal_places=2)


class DiyetisyenStatsSerializer(serializers.Serializer):
    toplam_danisan = serializers.IntegerField()
    aktif_danisan = serializers.IntegerField()
    bu_hafta_randevu = serializers.IntegerField()
    bu_ay_randevu = serializers.IntegerField()
    toplam_randevu = serializers.IntegerField()
    iptal_orani = serializers.FloatField()
    ortalama_puan = serializers.FloatField()