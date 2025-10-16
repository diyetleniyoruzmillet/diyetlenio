from rest_framework import serializers
from core.models import Dosya, Kullanici
from api.v1.auth.serializers import KullaniciSerializer


class DosyaUploadSerializer(serializers.ModelSerializer):
    dosya_file = serializers.FileField(write_only=True)
    baglanti_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Dosya
        fields = [
            'dosya_file', 'dosya_adi', 'aciklama', 'baglanti_tipi', 
            'baglanti_id', 'gizlilik_seviyesi'
        ]
    
    def validate_dosya_file(self, value):
        # Dosya boyutu kontrolü (10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Dosya boyutu en fazla 10MB olabilir.")
        
        # Dosya tipi kontrolü
        allowed_extensions = [
            '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif',
            '.txt', '.xlsx', '.xls', '.ppt', '.pptx'
        ]
        
        file_name = value.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError("Desteklenmeyen dosya formatı.")
        
        return value
    
    def validate_baglanti_tipi(self, value):
        valid_types = ['KULLANICI', 'RANDEVU', 'diyetisyen', 'GENEL']
        if value not in valid_types:
            raise serializers.ValidationError("Geçersiz bağlantı tipi.")
        return value
    
    def validate(self, attrs):
        baglanti_tipi = attrs.get('baglanti_tipi')
        baglanti_id = attrs.get('baglanti_id')
        
        # Bağlantı ID kontrolü
        if baglanti_tipi in ['KULLANICI', 'RANDEVU', 'diyetisyen'] and not baglanti_id:
            raise serializers.ValidationError("Bu bağlantı tipi için bağlantı ID gereklidir.")
        
        # Bağlantı ID geçerliliği
        if baglanti_tipi == 'KULLANICI' and baglanti_id:
            try:
                Kullanici.objects.get(id=baglanti_id)
            except Kullanici.DoesNotExist:
                raise serializers.ValidationError("Geçersiz kullanıcı ID.")
        
        return attrs
    
    def create(self, validated_data):
        dosya_file = validated_data.pop('dosya_file')
        
        # Dosya yolu oluştur
        import os
        from django.utils import timezone
        from django.conf import settings
        
        # Upload directory
        upload_dir = os.path.join(settings.BASE_DIR, 'media', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Unique filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        original_name = dosya_file.name
        name, ext = os.path.splitext(original_name)
        unique_filename = f"{timestamp}_{name}{ext}"
        
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Dosyayı kaydet
        with open(file_path, 'wb') as f:
            for chunk in dosya_file.chunks():
                f.write(chunk)
        
        # Database kaydı
        validated_data['dosya_yolu'] = f"uploads/{unique_filename}"
        validated_data['dosya_boyutu'] = dosya_file.size
        validated_data['yukleme_tarihi'] = timezone.now()
        validated_data['yukleyen'] = self.context['request'].user
        
        return super().create(validated_data)


class DosyaSerializer(serializers.ModelSerializer):
    yukleyen_adi = serializers.CharField(source='yukleyen.ad', read_only=True)
    yukleyen_soyadi = serializers.CharField(source='yukleyen.soyad', read_only=True)
    dosya_url = serializers.SerializerMethodField()
    dosya_boyutu_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = Dosya
        fields = [
            'id', 'dosya_adi', 'dosya_yolu', 'dosya_url', 'dosya_boyutu', 
            'dosya_boyutu_mb', 'aciklama', 'baglanti_tipi', 'baglanti_id',
            'gizlilik_seviyesi', 'yukleyen', 'yukleyen_adi', 'yukleyen_soyadi',
            'yukleme_tarihi', 'indirilme_sayisi'
        ]
        read_only_fields = [
            'id', 'dosya_yolu', 'dosya_boyutu', 'yukleyen', 'yukleme_tarihi',
            'indirilme_sayisi'
        ]
    
    def get_dosya_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/media/{obj.dosya_yolu}')
        return f'/media/{obj.dosya_yolu}'
    
    def get_dosya_boyutu_mb(self, obj):
        return round(obj.dosya_boyutu / (1024 * 1024), 2) if obj.dosya_boyutu else 0


class DosyaUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dosya
        fields = ['dosya_adi', 'aciklama', 'gizlilik_seviyesi']


class DosyaListFilterSerializer(serializers.Serializer):
    baglanti_tipi = serializers.ChoiceField(
        choices=['KULLANICI', 'RANDEVU', 'diyetisyen', 'GENEL'],
        required=False
    )
    baglanti_id = serializers.IntegerField(required=False)
    gizlilik_seviyesi = serializers.ChoiceField(
        choices=['HERKES', 'KULLANICI', 'diyetisyen', 'admin'],
        required=False
    )