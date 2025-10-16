from rest_framework import serializers


class PlatformStatsSerializer(serializers.Serializer):
    # Kullanıcı istatistikleri
    toplam_kullanici = serializers.IntegerField()
    aktif_kullanici = serializers.IntegerField()
    yeni_kullanici_bu_ay = serializers.IntegerField()
    danisan_sayisi = serializers.IntegerField()
    diyetisyen_sayisi = serializers.IntegerField()
    
    # Randevu istatistikleri
    toplam_randevu = serializers.IntegerField()
    bu_ay_randevu = serializers.IntegerField()
    bu_hafta_randevu = serializers.IntegerField()
    bugun_randevu = serializers.IntegerField()
    tamamlanan_randevu = serializers.IntegerField()
    iptal_edilen_randevu = serializers.IntegerField()
    iptal_orani = serializers.FloatField()
    
    # Finansal istatistikler
    bu_ay_toplam_gelir = serializers.DecimalField(max_digits=12, decimal_places=2)
    toplam_komisyon = serializers.DecimalField(max_digits=12, decimal_places=2)
    ortalama_randevu_ucreti = serializers.DecimalField(max_digits=10, decimal_places=2)


class RandevuTrendiSerializer(serializers.Serializer):
    tarih = serializers.DateField()
    toplam_randevu = serializers.IntegerField()
    tamamlanan = serializers.IntegerField()
    iptal_edilen = serializers.IntegerField()


class DiyetisyenPerformansSerializer(serializers.Serializer):
    diyetisyen_id = serializers.IntegerField()
    diyetisyen_adi = serializers.CharField()
    toplam_randevu = serializers.IntegerField()
    tamamlanan_randevu = serializers.IntegerField()
    iptal_edilen_randevu = serializers.IntegerField()
    iptal_orani = serializers.FloatField()
    toplam_kazanc = serializers.DecimalField(max_digits=10, decimal_places=2)
    ortalama_puan = serializers.FloatField()
    aktif_danisan_sayisi = serializers.IntegerField()


class UzmanlikAlaniStatsSerializer(serializers.Serializer):
    uzmanlik_alani = serializers.CharField()
    diyetisyen_sayisi = serializers.IntegerField()
    randevu_sayisi = serializers.IntegerField()
    talep_orani = serializers.FloatField()


class AylikRaporSerializer(serializers.Serializer):
    ay = serializers.CharField()
    yil = serializers.IntegerField()
    
    # Kullanıcı verileri
    yeni_kullanici = serializers.IntegerField()
    aktif_kullanici = serializers.IntegerField()
    
    # Randevu verileri
    toplam_randevu = serializers.IntegerField()
    tamamlanan_randevu = serializers.IntegerField()
    iptal_edilen_randevu = serializers.IntegerField()
    
    # Mali veriler
    toplam_gelir = serializers.DecimalField(max_digits=12, decimal_places=2)
    komisyon_geliri = serializers.DecimalField(max_digits=12, decimal_places=2)
    diyetisyen_odenen = serializers.DecimalField(max_digits=12, decimal_places=2)


class IptalAnaliziSerializer(serializers.Serializer):
    diyetisyen_id = serializers.IntegerField()
    diyetisyen_adi = serializers.CharField()
    son_7gun_iptal = serializers.IntegerField()
    son_30gun_iptal = serializers.IntegerField()
    toplam_randevu = serializers.IntegerField()
    iptal_orani = serializers.FloatField()
    risk_seviyesi = serializers.CharField()  # DUSUK, ORTA, YUKSEK


class MudahaleRaporuSerializer(serializers.Serializer):
    toplam_mudahale_talepleri = serializers.IntegerField()
    acik_talepler = serializers.IntegerField()
    cozumlenen_talepler = serializers.IntegerField()
    ortalama_cozum_suresi = serializers.FloatField()  # Saat cinsinden
    en_cok_mudahale_gereken_diyetisyenler = DiyetisyenPerformansSerializer(many=True)


class CustomDateRangeSerializer(serializers.Serializer):
    baslangic_tarihi = serializers.DateField()
    bitis_tarihi = serializers.DateField()
    
    def validate(self, attrs):
        if attrs['baslangic_tarihi'] > attrs['bitis_tarihi']:
            raise serializers.ValidationError("Başlangıç tarihi bitiş tarihinden büyük olamaz.")
        return attrs