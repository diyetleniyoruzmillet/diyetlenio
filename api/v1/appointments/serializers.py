from rest_framework import serializers
from core.models import (
    Randevu, Musaitlik, DiyetisyenMusaitlikSablon, 
    DiyetisyenIzin, Diyetisyen
)
from api.v1.auth.serializers import KullaniciSerializer


class RandevuSerializer(serializers.ModelSerializer):
    danisan_bilgisi = KullaniciSerializer(source='danisan', read_only=True)
    diyetisyen_bilgisi = serializers.SerializerMethodField()
    
    def get_diyetisyen_bilgisi(self, obj):
        if obj.diyetisyen and obj.diyetisyen.kullanici:
            return KullaniciSerializer(obj.diyetisyen.kullanici).data
        return None
    
    class Meta:
        model = Randevu
        fields = [
            'id', 'danisan', 'diyetisyen', 'randevu_tarih_saat', 'kamera_linki',
            'durum', 'tip', 'ucret_tutar', 'baslangic_saati_gercek', 'bitis_saati_gercek',
            'iptal_eden_tur', 'iptal_edilme_tarihi', 'iptal_nedeni', 'admin_inceleme_gerekiyor',
            'danisan_bilgisi', 'diyetisyen_bilgisi'
        ]
        read_only_fields = [
            'id', 'diyetisyen', 'durum', 'iptal_eden_tur', 'iptal_edilme_tarihi',
            'baslangic_saati_gercek', 'bitis_saati_gercek', 'admin_inceleme_gerekiyor'
        ]


class RandevuCreateSerializer(serializers.Serializer):
    tarih = serializers.DateField()
    saat = serializers.TimeField()
    tip = serializers.ChoiceField(choices=Randevu.TIP_CHOICES, default='UCRETLI')
    notlar = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # Validate that appointment is in the future
        from datetime import datetime
        from django.utils import timezone
        
        tarih = data['tarih']
        saat = data['saat']
        randevu_datetime = datetime.combine(tarih, saat)
        randevu_datetime = timezone.make_aware(randevu_datetime)
        
        if randevu_datetime <= timezone.now():
            raise serializers.ValidationError("Randevu tarihi gelecekte olmalıdır.")
        
        return data


class MusaitlikSerializer(serializers.ModelSerializer):
    diyetisyen_bilgisi = serializers.SerializerMethodField()
    
    def get_diyetisyen_bilgisi(self, obj):
        if obj.diyetisyen and obj.diyetisyen.kullanici:
            return KullaniciSerializer(obj.diyetisyen.kullanici).data
        return None
    
    class Meta:
        model = Musaitlik
        fields = [
            'id', 'diyetisyen', 'gun', 'baslangic_saati', 'bitis_saati',
            'diyetisyen_bilgisi'
        ]
        read_only_fields = ['id']


class RandevuCancelSerializer(serializers.Serializer):
    iptal_nedeni = serializers.CharField(max_length=500, required=False)
    
    def validate(self, attrs):
        randevu = self.context['randevu']
        user = self.context['request'].user
        
        if randevu.durum in ['IPTAL_EDILDI', 'TAMAMLANDI']:
            raise serializers.ValidationError("Bu randevu zaten iptal edilmiş veya tamamlanmış.")
        
        # Sadece ilgili kişiler iptal edebilir
        if user not in [randevu.danisan, randevu.diyetisyen.kullanici] and user.rol.rol_adi != 'admin':
            raise serializers.ValidationError("Bu randevuyu iptal etme yetkiniz yok.")
        
        return attrs


class DiyetisyenMusaitlikSablonSerializer(serializers.ModelSerializer):
    gun_display = serializers.CharField(source='get_gun_display', read_only=True)
    
    class Meta:
        model = DiyetisyenMusaitlikSablon
        fields = [
            'id', 'gun', 'gun_display', 'baslangic_saati', 
            'bitis_saati', 'aktif', 'olusturma_tarihi'
        ]
        read_only_fields = ['id', 'olusturma_tarihi']
    
    def validate(self, data):
        if data['baslangic_saati'] >= data['bitis_saati']:
            raise serializers.ValidationError(
                "Başlangıç saati bitiş saatinden önce olmalıdır."
            )
        return data


class DiyetisyenIzinSerializer(serializers.ModelSerializer):
    izin_tipi_display = serializers.CharField(source='get_izin_tipi_display', read_only=True)
    
    class Meta:
        model = DiyetisyenIzin
        fields = [
            'id', 'baslangic_tarihi', 'bitis_tarihi', 'izin_tipi',
            'izin_tipi_display', 'baslangic_saati', 'bitis_saati',
            'aciklama', 'olusturma_tarihi'
        ]
        read_only_fields = ['id', 'olusturma_tarihi']
    
    def validate(self, data):
        if data['baslangic_tarihi'] > data['bitis_tarihi']:
            raise serializers.ValidationError(
                "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
        
        if data['izin_tipi'] == 'SAATLIK':
            if not (data.get('baslangic_saati') and data.get('bitis_saati')):
                raise serializers.ValidationError(
                    "Saatlik izin için başlangıç ve bitiş saati gereklidir."
                )
            if data['baslangic_saati'] >= data['bitis_saati']:
                raise serializers.ValidationError(
                    "Başlangıç saati bitiş saatinden önce olmalıdır."
                )
        
        return data


class AvailabilityRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    diyetisyen = serializers.IntegerField(required=False)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError(
                "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
        
        # Maksimum 30 gün aralık
        from datetime import timedelta
        if (data['end_date'] - data['start_date']) > timedelta(days=30):
            raise serializers.ValidationError(
                "Maksimum 30 günlük aralık seçebilirsiniz."
            )
        
        return data