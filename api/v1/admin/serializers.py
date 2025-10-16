from rest_framework import serializers
from core.models import Kullanici, Diyetisyen, Randevu, DiyetisyenUzmanlikAlani
from api.v1.auth.serializers import KullaniciSerializer


class DiyetisyenApprovalSerializer(serializers.Serializer):
    onay_notlari = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        diyetisyen = self.context['diyetisyen']
        if diyetisyen.onay_durumu != 'BEKLEMEDE':
            raise serializers.ValidationError("Bu diyetisyen zaten değerlendirilmiş.")
        return attrs


class DiyetisyenRejectionSerializer(serializers.Serializer):
    red_sebebi = serializers.CharField(max_length=500, required=True)
    
    def validate(self, attrs):
        diyetisyen = self.context['diyetisyen']
        if diyetisyen.onay_durumu != 'BEKLEMEDE':
            raise serializers.ValidationError("Bu diyetisyen zaten değerlendirilmiş.")
        return attrs


class DiyetisyenDetailWithApplicationSerializer(serializers.ModelSerializer):
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


class RandevuReassignSerializer(serializers.Serializer):
    yeni_diyetisyen_id = serializers.IntegerField()
    neden = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_yeni_diyetisyen_id(self, value):
        try:
            diyetisyen_user = Kullanici.objects.get(id=value, rol__rol_adi='diyetisyen', is_active=True)
            diyetisyen = Diyetisyen.objects.get(kullanici=diyetisyen_user)
        except (Kullanici.DoesNotExist, Diyetisyen.DoesNotExist):
            raise serializers.ValidationError("Geçerli bir aktif diyetisyen seçmelisiniz.")
        
        return value


class UserDeactivationSerializer(serializers.Serializer):
    neden = serializers.CharField(max_length=500, required=True)
    
    def validate(self, attrs):
        user = self.context['user']
        if user.rol.rol_adi == 'admin':
            raise serializers.ValidationError("Admin kullanıcılar deaktif edilemez.")
        if not user.is_active:
            raise serializers.ValidationError("Bu kullanıcı zaten deaktif.")
        return attrs


class AdminStatsSerializer(serializers.Serializer):
    toplam_kullanici = serializers.IntegerField()
    aktif_kullanici = serializers.IntegerField()
    danisan_sayisi = serializers.IntegerField()
    diyetisyen_sayisi = serializers.IntegerField()
    onay_bekleyen_diyetisyen = serializers.IntegerField()
    onaylanan_diyetisyen = serializers.IntegerField()
    bugun_randevu = serializers.IntegerField()
    bu_hafta_randevu = serializers.IntegerField()
    bu_ay_randevu = serializers.IntegerField()
    iptal_orani = serializers.FloatField()


class PendingDiyetisyenListSerializer(serializers.ModelSerializer):
    kullanici = KullaniciSerializer(read_only=True)
    uzmanlik_alanlari = serializers.SerializerMethodField()
    basvuru_tarihi = serializers.DateTimeField(source='kullanici.date_joined', read_only=True)
    
    class Meta:
        model = Diyetisyen
        fields = [
            'kullanici', 'universite', 'hakkinda_bilgi', 'hizmet_ucreti',
            'uzmanlik_alanlari', 'basvuru_tarihi'
        ]
    
    def get_uzmanlik_alanlari(self, obj):
        uzmanliklar = DiyetisyenUzmanlikAlani.objects.filter(diyetisyen=obj)
        return [uz.uzmanlik_alani.alan_adi for uz in uzmanliklar]