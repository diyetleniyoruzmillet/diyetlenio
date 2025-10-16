from rest_framework import serializers
from core.models import (
    SoruSeti, Soru, SoruSecenek, AnketOturum, 
    AnketCevap, AnketCokluSecim, Kullanici
)


class SoruSecenekSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoruSecenek
        fields = ['id', 'etiket', 'deger', 'sira']


class SoruSerializer(serializers.ModelSerializer):
    secenekler = SoruSecenekSerializer(source='sorusecenek_set', many=True, read_only=True)
    
    class Meta:
        model = Soru
        fields = [
            'id', 'soru_metni', 'soru_tipi', 'zorunlu_mu', 'sira_no',
            'secenekler'
        ]


class SoruSetiSerializer(serializers.ModelSerializer):
    sorular = SoruSerializer(source='soru_set', many=True, read_only=True)
    hedef_rol_adi = serializers.CharField(source='hedef_rol.rol_adi', read_only=True)
    
    class Meta:
        model = SoruSeti
        fields = [
            'id', 'ad', 'aciklama', 'aktif_mi', 'hedef_rol_adi', 'sorular'
        ]


class SoruSetiListSerializer(serializers.ModelSerializer):
    """Soru seti listesi için daha hafif serializer"""
    hedef_rol_adi = serializers.CharField(source='hedef_rol.rol_adi', read_only=True)
    soru_sayisi = serializers.SerializerMethodField()
    
    class Meta:
        model = SoruSeti
        fields = ['id', 'ad', 'aciklama', 'aktif_mi', 'hedef_rol_adi', 'soru_sayisi']
    
    def get_soru_sayisi(self, obj):
        return obj.soru_set.count()


class AnketCevapSerializer(serializers.Serializer):
    """Anket cevaplarını almak için serializer"""
    soru_id = serializers.IntegerField()
    cevap_metin = serializers.CharField(required=False, allow_blank=True)
    cevap_sayi = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    secilen_secenekler = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )


class AnketOturumCreateSerializer(serializers.ModelSerializer):
    soru_seti_id = serializers.IntegerField(write_only=True)
    cevaplar = serializers.ListField(
        child=AnketCevapSerializer(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = AnketOturum
        fields = ['soru_seti_id', 'cevaplar']
    
    def validate_soru_seti_id(self, value):
        try:
            soru_seti = SoruSeti.objects.get(id=value, aktif_mi=True)
            # Kullanıcının rolü ile soru setinin hedef rolü uyuşuyor mu?
            user_rol = self.context['request'].user.rol
            if soru_seti.hedef_rol and soru_seti.hedef_rol != user_rol:
                raise serializers.ValidationError("Bu anket sizin için uygun değil.")
        except SoruSeti.DoesNotExist:
            raise serializers.ValidationError("Geçersiz soru seti ID.")
        return value
    
    def create(self, validated_data):
        soru_seti_id = validated_data['soru_seti_id']
        cevaplar_data = validated_data.get('cevaplar', [])
        
        # AnketOturum oluştur
        anket_oturum = AnketOturum.objects.create(
            soru_seti_id=soru_seti_id,
            kullanici=self.context['request'].user,
            durum='ACIK'
        )
        
        # Cevapları kaydet
        for cevap_data in cevaplar_data:
            soru_id = cevap_data['soru_id']
            
            # Sorunun bu soru setinde olup olmadığını kontrol et
            try:
                soru = Soru.objects.get(id=soru_id, soru_seti_id=soru_seti_id)
            except Soru.DoesNotExist:
                continue
            
            # AnketCevap oluştur
            anket_cevap = AnketCevap.objects.create(
                anket_oturum=anket_oturum,
                soru=soru,
                cevap_metin=cevap_data.get('cevap_metin'),
                cevap_sayi=cevap_data.get('cevap_sayi')
            )
            
            # Çoklu seçim cevaplarını kaydet
            secilen_secenekler = cevap_data.get('secilen_secenekler', [])
            for secenek_id in secilen_secenekler:
                try:
                    secenek = SoruSecenek.objects.get(id=secenek_id, soru=soru)
                    AnketCokluSecim.objects.create(
                        anket_cevap=anket_cevap,
                        secenek=secenek
                    )
                except SoruSecenek.DoesNotExist:
                    continue
        
        # Anketi tamamla
        anket_oturum.durum = 'TAMAMLANDI'
        anket_oturum.save()
        
        return anket_oturum


class AnketCevapDetailSerializer(serializers.ModelSerializer):
    """Anket cevap detayları"""
    soru_metni = serializers.CharField(source='soru.soru_metni', read_only=True)
    secilen_secenekler = serializers.SerializerMethodField()
    
    class Meta:
        model = AnketCevap
        fields = [
            'id', 'soru_metni', 'cevap_metin', 'cevap_sayi', 'secilen_secenekler'
        ]
    
    def get_secilen_secenekler(self, obj):
        secimler = AnketCokluSecim.objects.filter(anket_cevap=obj)
        return [
            {
                'id': secim.secenek.id,
                'etiket': secim.secenek.etiket,
                'deger': secim.secenek.deger
            }
            for secim in secimler
        ]


class AnketOturumSerializer(serializers.ModelSerializer):
    soru_seti_adi = serializers.CharField(source='soru_seti.ad', read_only=True)
    kullanici_adi = serializers.CharField(source='kullanici.ad', read_only=True)
    kullanici_soyadi = serializers.CharField(source='kullanici.soyad', read_only=True)
    cevaplar = AnketCevapDetailSerializer(source='anketcevap_set', many=True, read_only=True)
    
    class Meta:
        model = AnketOturum
        fields = [
            'id', 'soru_seti_adi', 'kullanici_adi', 'kullanici_soyadi',
            'baslangic_tarihi', 'durum', 'cevaplar'
        ]