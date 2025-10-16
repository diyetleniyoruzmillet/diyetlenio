from rest_framework import serializers
from core.models import DiyetListesi, Diyetisyen, Kullanici
from api.v1.auth.serializers import KullaniciSerializer


class DiyetListesiSerializer(serializers.ModelSerializer):
    diyetisyen_adi = serializers.CharField(source='diyetisyen.kullanici.ad', read_only=True)
    diyetisyen_soyadi = serializers.CharField(source='diyetisyen.kullanici.soyad', read_only=True)
    danisan_adi = serializers.CharField(source='danisan.ad', read_only=True)
    danisan_soyadi = serializers.CharField(source='danisan.soyad', read_only=True)
    randevu_tarihi = serializers.DateTimeField(source='randevu.randevu_tarih_saat', read_only=True)
    
    class Meta:
        model = DiyetListesi
        fields = [
            'id', 'baslik', 'icerik', 'yuklenme_tarihi',
            'diyetisyen_adi', 'diyetisyen_soyadi',
            'danisan_adi', 'danisan_soyadi', 'randevu_tarihi'
        ]
        read_only_fields = ['id', 'yuklenme_tarihi']


class DiyetListesiCreateSerializer(serializers.ModelSerializer):
    danisan_id = serializers.IntegerField(write_only=True)
    randevu_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = DiyetListesi
        fields = ['danisan_id', 'randevu_id', 'baslik', 'icerik']
    
    def validate_danisan_id(self, value):
        try:
            Kullanici.objects.get(id=value, rol__rol_adi='danisan')
        except Kullanici.DoesNotExist:
            raise serializers.ValidationError("Geçersiz danışan ID.")
        return value
    
    def validate_randevu_id(self, value):
        if value:
            from core.models import Randevu
            try:
                randevu = Randevu.objects.get(id=value)
                # Randevunun request.user'ın diyetisyeni olup olmadığını kontrol et
                request_user = self.context['request'].user
                if randevu.diyetisyen.kullanici != request_user:
                    raise serializers.ValidationError("Bu randevuya erişim yetkiniz yok.")
            except Randevu.DoesNotExist:
                raise serializers.ValidationError("Geçersiz randevu ID.")
        return value
    
    def create(self, validated_data):
        danisan_id = validated_data.pop('danisan_id')
        randevu_id = validated_data.pop('randevu_id', None)
        
        # Diyetisyen bilgisini request user'dan al
        request_user = self.context['request'].user
        diyetisyen = Diyetisyen.objects.get(kullanici=request_user)
        
        validated_data['diyetisyen'] = diyetisyen
        validated_data['danisan'] = Kullanici.objects.get(id=danisan_id)
        
        if randevu_id:
            from core.models import Randevu
            validated_data['randevu'] = Randevu.objects.get(id=randevu_id)
        
        return super().create(validated_data)


class DiyetListesiUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiyetListesi
        fields = ['baslik', 'icerik']