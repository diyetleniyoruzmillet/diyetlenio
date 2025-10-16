from rest_framework import serializers
from core.models import Yorum, Diyetisyen, Kullanici
from django.db.models import Avg


class YorumSerializer(serializers.ModelSerializer):
    danisan_adi = serializers.CharField(source='danisan.ad', read_only=True)
    danisan_soyadi = serializers.CharField(source='danisan.soyad', read_only=True)
    diyetisyen_adi = serializers.CharField(source='diyetisyen.kullanici.ad', read_only=True)
    diyetisyen_soyadi = serializers.CharField(source='diyetisyen.kullanici.soyad', read_only=True)
    
    class Meta:
        model = Yorum
        fields = [
            'id', 'puan', 'yorum_metni', 'yorum_tarihi', 'onay_durumu',
            'danisan_adi', 'danisan_soyadi', 'diyetisyen_adi', 'diyetisyen_soyadi'
        ]
        read_only_fields = ['id', 'yorum_tarihi', 'onay_durumu']


class YorumCreateSerializer(serializers.ModelSerializer):
    diyetisyen_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Yorum
        fields = ['diyetisyen_id', 'puan', 'yorum_metni']
    
    def validate_diyetisyen_id(self, value):
        try:
            diyetisyen = Diyetisyen.objects.get(kullanici__id=value)
        except Diyetisyen.DoesNotExist:
            raise serializers.ValidationError("Geçersiz diyetisyen ID.")
        return value
    
    def validate(self, data):
        # Danışanın aynı diyetisyene daha önce yorum yapıp yapmadığını kontrol et
        request_user = self.context['request'].user
        diyetisyen_id = data['diyetisyen_id']
        diyetisyen = Diyetisyen.objects.get(kullanici__id=diyetisyen_id)
        
        if Yorum.objects.filter(danisan=request_user, diyetisyen=diyetisyen).exists():
            raise serializers.ValidationError("Bu diyetisyene daha önce yorum yapmışsınız.")
        
        return data
    
    def validate_puan(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Puan 1-5 arasında olmalıdır.")
        return value
    
    def create(self, validated_data):
        diyetisyen_id = validated_data.pop('diyetisyen_id')
        diyetisyen = Diyetisyen.objects.get(kullanici__id=diyetisyen_id)
        
        validated_data['diyetisyen'] = diyetisyen
        validated_data['danisan'] = self.context['request'].user
        validated_data['onay_durumu'] = 'BEKLEMEDE'
        
        return super().create(validated_data)


class PublicYorumSerializer(serializers.ModelSerializer):
    """Onaylanmış yorumlar için public serializer"""
    danisan_adi = serializers.CharField(source='danisan.ad', read_only=True)
    danisan_soyadi = serializers.CharField(source='danisan.soyad', read_only=True)
    
    class Meta:
        model = Yorum
        fields = [
            'id', 'puan', 'yorum_metni', 'yorum_tarihi',
            'danisan_adi', 'danisan_soyadi'
        ]


class DiyetisyenYorumStatsSerializer(serializers.Serializer):
    """Diyetisyen yorum istatistikleri"""
    ortalama_puan = serializers.DecimalField(max_digits=3, decimal_places=2)
    toplam_yorum = serializers.IntegerField()
    puan_dagilimi = serializers.DictField()
    onaylanmis_yorum_sayisi = serializers.IntegerField()


class AdminYorumSerializer(serializers.ModelSerializer):
    """Admin için yorum serializer"""
    danisan_adi = serializers.CharField(source='danisan.ad', read_only=True)
    danisan_soyadi = serializers.CharField(source='danisan.soyad', read_only=True)
    danisan_email = serializers.EmailField(source='danisan.e_posta', read_only=True)
    diyetisyen_adi = serializers.CharField(source='diyetisyen.kullanici.ad', read_only=True)
    diyetisyen_soyadi = serializers.CharField(source='diyetisyen.kullanici.soyad', read_only=True)
    
    class Meta:
        model = Yorum
        fields = [
            'id', 'puan', 'yorum_metni', 'yorum_tarihi', 'onay_durumu',
            'danisan_adi', 'danisan_soyadi', 'danisan_email',
            'diyetisyen_adi', 'diyetisyen_soyadi'
        ]


class YorumOnaySerializer(serializers.Serializer):
    onay_durumu = serializers.ChoiceField(
        choices=[('ONAYLANDI', 'Onaylandı'), ('REDDEDILDI', 'Reddedildi')]
    )
    aciklama = serializers.CharField(required=False, allow_blank=True)