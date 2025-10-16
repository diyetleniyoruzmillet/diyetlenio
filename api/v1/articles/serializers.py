from rest_framework import serializers
from core.models import Makale, MakaleKategori, MakaleYorum, Kullanici
from api.v1.auth.serializers import KullaniciSerializer


class MakaleKategoriSerializer(serializers.ModelSerializer):
    makale_sayisi = serializers.SerializerMethodField()
    
    class Meta:
        model = MakaleKategori
        fields = ['id', 'ad', 'aciklama', 'renk', 'sira', 'aktif_mi', 'makale_sayisi']
        read_only_fields = ['id', 'makale_sayisi']
    
    def get_makale_sayisi(self, obj):
        return obj.makaleler.filter(onay_durumu='ONAYLANDI').count()


class MakaleSerializer(serializers.ModelSerializer):
    yazar_adi = serializers.CharField(source='yazar_kullanici.ad', read_only=True)
    yazar_soyadi = serializers.CharField(source='yazar_kullanici.soyad', read_only=True)
    yazar_email = serializers.EmailField(source='yazar_kullanici.e_posta', read_only=True)
    kategori_adi = serializers.CharField(source='kategori.ad', read_only=True)
    yorum_sayisi = serializers.SerializerMethodField()
    etiket_listesi = serializers.ReadOnlyField()
    
    class Meta:
        model = Makale
        fields = [
            'id', 'baslik', 'slug', 'ozet', 'icerik', 'kapak_resmi', 'kategori', 'kategori_adi',
            'yayimlanma_tarihi', 'onay_durumu', 'okunma_sayisi', 'begeni_sayisi',
            'yazar_adi', 'yazar_soyadi', 'yazar_email', 'yorum_sayisi', 'etiketler', 'etiket_listesi',
            'olusturma_tarihi', 'guncelleme_tarihi'
        ]
        read_only_fields = ['id', 'slug', 'yayimlanma_tarihi', 'onay_durumu', 'okunma_sayisi', 'begeni_sayisi']
    
    def get_yorum_sayisi(self, obj):
        return MakaleYorum.objects.filter(makale=obj).count()


class MakaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Makale
        fields = ['baslik', 'ozet', 'icerik', 'kapak_resmi', 'kategori', 'etiketler', 'seo_baslik', 'seo_aciklama']
    
    def create(self, validated_data):
        validated_data['yazar_kullanici'] = self.context['request'].user
        validated_data['onay_durumu'] = 'BEKLEMEDE'
        return super().create(validated_data)


class MakaleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Makale
        fields = ['baslik', 'ozet', 'icerik', 'kapak_resmi', 'kategori', 'etiketler', 'seo_baslik', 'seo_aciklama']


class PublicMakaleSerializer(serializers.ModelSerializer):
    """Onaylanmış makaleler için public serializer"""
    yazar_adi = serializers.CharField(source='yazar_kullanici.ad', read_only=True)
    yazar_soyadi = serializers.CharField(source='yazar_kullanici.soyad', read_only=True)
    kategori_adi = serializers.CharField(source='kategori.ad', read_only=True)
    kategori_renk = serializers.CharField(source='kategori.renk', read_only=True)
    yorum_sayisi = serializers.SerializerMethodField()
    etiket_listesi = serializers.ReadOnlyField()
    
    class Meta:
        model = Makale
        fields = [
            'id', 'baslik', 'slug', 'ozet', 'icerik', 'kapak_resmi', 'yayimlanma_tarihi', 
            'okunma_sayisi', 'begeni_sayisi', 'kategori_adi', 'kategori_renk',
            'yazar_adi', 'yazar_soyadi', 'yorum_sayisi', 'etiket_listesi',
            'seo_baslik', 'seo_aciklama'
        ]
    
    def get_yorum_sayisi(self, obj):
        return MakaleYorum.objects.filter(makale=obj).count()


class MakaleYorumSerializer(serializers.ModelSerializer):
    kullanici_adi = serializers.CharField(source='kullanici.ad', read_only=True)
    kullanici_soyadi = serializers.CharField(source='kullanici.soyad', read_only=True)
    
    class Meta:
        model = MakaleYorum
        fields = [
            'id', 'yorum_metni', 'yorum_tarihi',
            'kullanici_adi', 'kullanici_soyadi'
        ]
        read_only_fields = ['id', 'yorum_tarihi']


class MakaleYorumCreateSerializer(serializers.ModelSerializer):
    makale_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = MakaleYorum
        fields = ['makale_id', 'yorum_metni']
    
    def validate_makale_id(self, value):
        try:
            makale = Makale.objects.get(id=value, onay_durumu='ONAYLANDI')
        except Makale.DoesNotExist:
            raise serializers.ValidationError("Geçersiz veya onaylanmamış makale ID.")
        return value
    
    def create(self, validated_data):
        makale_id = validated_data.pop('makale_id')
        validated_data['makale'] = Makale.objects.get(id=makale_id)
        validated_data['kullanici'] = self.context['request'].user
        return super().create(validated_data)


# Admin için makale onay serializer'ları
class AdminMakaleSerializer(serializers.ModelSerializer):
    yazar_adi = serializers.CharField(source='yazar_kullanici.ad', read_only=True)
    yazar_soyadi = serializers.CharField(source='yazar_kullanici.soyad', read_only=True)
    yazar_email = serializers.EmailField(source='yazar_kullanici.e_posta', read_only=True)
    
    class Meta:
        model = Makale
        fields = [
            'id', 'baslik', 'ozet', 'icerik', 'yayimlanma_tarihi', 'onay_durumu',
            'yazar_adi', 'yazar_soyadi', 'yazar_email'
        ]
        read_only_fields = ['id', 'yayimlanma_tarihi', 'yazar_kullanici']


class MakaleOnaySerializer(serializers.Serializer):
    onay_durumu = serializers.ChoiceField(
        choices=[('ONAYLANDI', 'Onaylandı'), ('REDDEDILDI', 'Reddedildi')]
    )
    aciklama = serializers.CharField(required=False, allow_blank=True)