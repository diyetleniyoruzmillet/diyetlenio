from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta


class Rol(models.Model):
    id = models.AutoField(primary_key=True)
    rol_adi = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'roller'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roller'

    def __str__(self):
        return self.rol_adi


class KullaniciManager(BaseUserManager):
    def create_user(self, e_posta, ad, soyad, rol, password=None, telefon=None, **extra_fields):
        if not e_posta:
            raise ValueError('E-posta adresi gereklidir')
        
        user = self.model(
            e_posta=self.normalize_email(e_posta),
            ad=ad.title() if ad else ad,
            soyad=soyad.title() if soyad else soyad,
            rol=rol,
            telefon=telefon,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, e_posta, ad, soyad, rol=None, password=None):
        if rol is None:
            # Admin rolünü al veya oluştur
            admin_rol, created = Rol.objects.get_or_create(rol_adi='admin')
            rol = admin_rol
            
        user = self.create_user(
            e_posta=e_posta,
            ad=ad,
            soyad=soyad,
            rol=rol,
            password=password
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class Kullanici(AbstractUser):
    id = models.AutoField(primary_key=True)
    ad = models.CharField(max_length=100, db_index=True)  # İsim araması için indeks
    soyad = models.CharField(max_length=100, db_index=True)  # Soyisim araması için indeks
    e_posta = models.EmailField(max_length=150, unique=True, db_index=True)
    telefon = models.CharField(max_length=20, blank=True, null=True)
    kayit_tarihi = models.DateTimeField(auto_now_add=True, db_index=True)  # Kayıt tarihi sorguları için
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='kullanicilar', db_index=True)
    aktif_mi = models.BooleanField(default=True, db_index=True)  # Aktif kullanıcı sorguları için
    son_giris_tarihi = models.DateTimeField(blank=True, null=True)

    # AbstractUser fieldlarını override et
    username = None
    first_name = None
    last_name = None
    email = None

    USERNAME_FIELD = 'e_posta'
    REQUIRED_FIELDS = ['ad', 'soyad']
    
    @property
    def is_active(self):
        """Django authentication için is_active property"""
        return self.aktif_mi
    
    @is_active.setter
    def is_active(self, value):
        """Django authentication için is_active setter"""
        self.aktif_mi = value
    
    def save(self, *args, **kwargs):
        """İsim ve soyadın ilk harflerini büyük yap"""
        if self.ad:
            self.ad = self.ad.title()
        if self.soyad:
            self.soyad = self.soyad.title()
        super().save(*args, **kwargs)
    
    objects = KullaniciManager()

    class Meta:
        db_table = 'kullanicilar'
        verbose_name = 'Kullanıcı'
        verbose_name_plural = 'Kullanıcılar'
        indexes = [
            models.Index(fields=['e_posta', 'aktif_mi'], name='idx_user_email_active'),
            models.Index(fields=['rol', 'aktif_mi'], name='idx_user_role_active'),
            models.Index(fields=['kayit_tarihi'], name='idx_user_created'),
        ]

    def __str__(self):
        return f"{self.ad} {self.soyad}"


class Diyetisyen(models.Model):
    ONAY_DURUM_CHOICES = [
        ('BEKLEMEDE', 'Onay Bekliyor'),
        ('ONAYLANDI', 'Onaylandı'),
        ('REDDEDILDI', 'Reddedildi'),
    ]
    
    kullanici = models.OneToOneField(Kullanici, on_delete=models.CASCADE, primary_key=True)
    universite = models.CharField(max_length=200, blank=True, null=True)
    hakkinda_bilgi = models.TextField(blank=True, null=True)
    profil_fotografi = models.ImageField(upload_to='diyetisyen_profil/', blank=True, null=True)
    hizmet_ucreti = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    onay_durumu = models.CharField(max_length=20, choices=ONAY_DURUM_CHOICES, default='BEKLEMEDE', db_index=True)
    onaylayan_admin = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True, related_name='onayledigi_diyetisyenler')
    onay_tarihi = models.DateTimeField(blank=True, null=True)
    red_nedeni = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'diyetisyenler'
        verbose_name = 'Diyetisyen'
        verbose_name_plural = 'Diyetisyenler'

    def save(self, *args, **kwargs):
        if not self.slug:
            # Create slug in format: dyt.ad.soyad
            ad_slug = slugify(self.kullanici.ad).replace('-', '')
            soyad_slug = slugify(self.kullanici.soyad).replace('-', '')
            base_slug = f"dyt.{ad_slug}.{soyad_slug}"
            slug = base_slug
            counter = 1
            
            # Ensure uniqueness
            while Diyetisyen.objects.filter(slug=slug).exists():
                slug = f"dyt.{ad_slug}.{soyad_slug}{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.kullanici)
    
    def get_absolute_url(self):
        return f"/{self.slug}/"


class DanisanDiyetisyenEslesme(models.Model):
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    on_gorusme_yapildi_mi = models.BooleanField(default=False)
    hasta_mi = models.BooleanField(default=False)
    eslesme_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'danisandiyetisyeneslesme'
        unique_together = ['diyetisyen', 'danisan']
        verbose_name = 'Danışan-Diyetisyen Eşleşme'
        verbose_name_plural = 'Danışan-Diyetisyen Eşleşmeleri'


class Musaitlik(models.Model):
    GUN_CHOICES = [
        (1, 'Pazartesi'),
        (2, 'Salı'),
        (3, 'Çarşamba'),
        (4, 'Perşembe'),
        (5, 'Cuma'),
        (6, 'Cumartesi'),
        (7, 'Pazar'),
    ]

    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE, related_name='musaitlikler')
    gun = models.SmallIntegerField(choices=GUN_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(7)])
    baslangic_saati = models.TimeField()
    bitis_saati = models.TimeField()
    aktif = models.BooleanField(default=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'musaitlikler'
        unique_together = ['diyetisyen', 'gun', 'baslangic_saati', 'bitis_saati']
        verbose_name = 'Müsaitlik'
        verbose_name_plural = 'Müsaitlikler'

    def __str__(self):
        return f"{self.diyetisyen} - {self.get_gun_display()} {self.baslangic_saati}-{self.bitis_saati}"


class DiyetisyenMusaitlikSablon(models.Model):
    """Diyetisyenlerin haftalık çalışma saatlerini tanımlayabilmesi için"""
    GUN_CHOICES = [
        (1, 'Pazartesi'),
        (2, 'Salı'),
        (3, 'Çarşamba'),
        (4, 'Perşembe'),
        (5, 'Cuma'),
        (6, 'Cumartesi'),
        (7, 'Pazar'),
    ]

    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE, related_name='musaitlik_sablonlari')
    gun = models.SmallIntegerField(choices=GUN_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(7)])
    baslangic_saati = models.TimeField()
    bitis_saati = models.TimeField()
    aktif = models.BooleanField(default=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)
    guncelleme_tarihi = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'diyetisyen_musaitlik_sablonlari'
        unique_together = ['diyetisyen', 'gun', 'baslangic_saati', 'bitis_saati']
        verbose_name = 'Diyetisyen Müsaitlik Şablonu'
        verbose_name_plural = 'Diyetisyen Müsaitlik Şablonları'

    def __str__(self):
        return f"{self.diyetisyen} - {self.get_gun_display()} {self.baslangic_saati}-{self.bitis_saati}"


class DiyetisyenIzin(models.Model):
    """Diyetisyenlerin izin günlerini tanımlayabilmesi için"""
    IZIN_TIP_CHOICES = [
        ('TAM_GUN', 'Tam Gün'),
        ('YARIM_GUN', 'Yarım Gün'),
        ('SAATLIK', 'Saatlik'),
    ]

    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE, related_name='izinler')
    baslangic_tarihi = models.DateField()
    bitis_tarihi = models.DateField()
    izin_tipi = models.CharField(max_length=20, choices=IZIN_TIP_CHOICES, default='TAM_GUN')
    baslangic_saati = models.TimeField(blank=True, null=True)
    bitis_saati = models.TimeField(blank=True, null=True)
    aciklama = models.TextField(blank=True, null=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'diyetisyen_izinleri'
        verbose_name = 'Diyetisyen İzin'
        verbose_name_plural = 'Diyetisyen İzinleri'

    def __str__(self):
        return f"{self.diyetisyen} - {self.baslangic_tarihi} - {self.get_izin_tipi_display()}"


class Randevu(models.Model):
    DURUM_CHOICES = [
        ('BEKLEMEDE', 'Beklemede'),
        ('ONAYLANDI', 'Onaylandı'),
        ('TAMAMLANDI', 'Tamamlandı'),
        ('IPTAL_EDILDI', 'İptal Edildi'),
    ]

    TIP_CHOICES = [
        ('ON_GORUSME', 'Ön Görüşme'),
        ('UCRETLI', 'Ücretli'),
    ]
    RANDEVU_TURU_CHOICES = [
        ('ONLINE', 'Online Görüşme'),
    ]

    IPTAL_EDEN_CHOICES = [
        ('diyetisyen', 'Diyetisyen'),
        ('danisan', 'Danışan'),
        ('admin', 'admin'),
        ('SISTEM', 'Sistem'),
    ]

    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE, db_index=True)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE, db_index=True)
    randevu_tarih_saat = models.DateTimeField(db_index=True)  # En çok sorgulanan alan
    kamera_linki = models.CharField(max_length=255, blank=True, null=True)  # meeting_url olarak kullanılacak
    durum = models.CharField(max_length=50, choices=DURUM_CHOICES, db_index=True)  # Durum sorguları için
    tip = models.CharField(max_length=20, choices=TIP_CHOICES, db_index=True)
    randevu_turu = models.CharField(max_length=20, choices=RANDEVU_TURU_CHOICES, default='ONLINE', db_index=True)
    ucret_tutar = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    baslangic_saati_gercek = models.DateTimeField(blank=True, null=True)
    bitis_saati_gercek = models.DateTimeField(blank=True, null=True)
    iptal_eden_tur = models.CharField(max_length=20, choices=IPTAL_EDEN_CHOICES, blank=True, null=True)
    iptal_edilme_tarihi = models.DateTimeField(blank=True, null=True)
    iptal_nedeni = models.TextField(blank=True, null=True)
    admin_inceleme_gerekiyor = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'randevular'
        verbose_name = 'Randevu'
        verbose_name_plural = 'Randevular'
        indexes = [
            models.Index(fields=['diyetisyen', 'randevu_tarih_saat'], name='idx_appointment_dyt_date'),
            models.Index(fields=['danisan', 'randevu_tarih_saat'], name='idx_appointment_patient_date'),
            models.Index(fields=['durum', 'randevu_tarih_saat'], name='idx_appointment_status_date'),
            models.Index(fields=['randevu_tarih_saat', 'durum'], name='idx_appointment_date_status'),
            models.Index(fields=['diyetisyen', 'durum'], name='idx_appointment_dyt_status'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(bitis_saati_gercek__isnull=True) | models.Q(bitis_saati_gercek__gte=models.F('baslangic_saati_gercek')),
                name='check_end_time_after_start'
            )
        ]

    def __str__(self):
        return f"Randevu #{self.id} - {self.diyetisyen} - {self.danisan}"


class DiyetListesi(models.Model):
    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    randevu = models.ForeignKey(Randevu, on_delete=models.SET_NULL, blank=True, null=True)
    baslik = models.CharField(max_length=255)
    icerik = models.TextField()
    yuklenme_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'diyetlisteleri'
        verbose_name = 'Diyet Listesi'
        verbose_name_plural = 'Diyet Listeleri'


class MakaleKategori(models.Model):
    id = models.AutoField(primary_key=True)
    ad = models.CharField(max_length=100, unique=True, db_index=True)
    aciklama = models.TextField(blank=True, null=True)
    renk = models.CharField(max_length=7, default='#007bff')  # Hex color code
    sira = models.PositiveIntegerField(default=0, db_index=True)
    aktif_mi = models.BooleanField(default=True, db_index=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'makale_kategorileri'
        verbose_name = 'Makale Kategorisi'
        verbose_name_plural = 'Makale Kategorileri'
        ordering = ['sira', 'ad']

    def __str__(self):
        return self.ad


class Makale(models.Model):
    ONAY_DURUM_CHOICES = [
        ('BEKLEMEDE', 'Beklemede'),
        ('ONAYLANDI', 'Onaylandı'),
        ('REDDEDILDI', 'Reddedildi'),
    ]

    id = models.AutoField(primary_key=True)
    yazar_kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True, related_name='yazdigi_makaleler')
    kategori = models.ForeignKey(MakaleKategori, on_delete=models.SET_NULL, blank=True, null=True, related_name='makaleler')
    baslik = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    ozet = models.TextField(blank=True, null=True)
    icerik = models.TextField()
    kapak_resmi = models.URLField(blank=True, null=True)
    okunma_sayisi = models.PositiveIntegerField(default=0, db_index=True)
    begeni_sayisi = models.PositiveIntegerField(default=0, db_index=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    guncelleme_tarihi = models.DateTimeField(auto_now=True, null=True)
    yayimlanma_tarihi = models.DateTimeField(blank=True, null=True, db_index=True)
    onay_durumu = models.CharField(max_length=20, choices=ONAY_DURUM_CHOICES, default='BEKLEMEDE', db_index=True)
    onaylayan_admin = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True, related_name='onayledigi_makaleler')
    red_sebebi = models.TextField(blank=True, null=True)
    etiketler = models.CharField(max_length=500, blank=True, null=True)  # Comma-separated tags
    seo_baslik = models.CharField(max_length=60, blank=True, null=True)
    seo_aciklama = models.CharField(max_length=160, blank=True, null=True)

    class Meta:
        db_table = 'makaleler'
        verbose_name = 'Makale'
        verbose_name_plural = 'Makaleler'
        ordering = ['-yayimlanma_tarihi', '-olusturma_tarihi']
        indexes = [
            models.Index(fields=['onay_durumu', 'yayimlanma_tarihi'], name='idx_article_status_published'),
            models.Index(fields=['kategori', 'onay_durumu'], name='idx_article_category_status'),
            models.Index(fields=['yazar_kullanici', 'onay_durumu'], name='idx_article_author_status'),
            models.Index(fields=['okunma_sayisi'], name='idx_article_views'),
        ]

    def __str__(self):
        return self.baslik

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(self.baslik)
            if not base_slug:
                base_slug = str(uuid.uuid4())[:8]
            
            # Check for unique slug
            original_slug = base_slug
            counter = 1
            while Makale.objects.filter(slug=base_slug).exclude(pk=self.pk).exists():
                base_slug = f"{original_slug}-{counter}"
                counter += 1
            
            self.slug = base_slug
            
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.onay_durumu == 'ONAYLANDI' and self.yayimlanma_tarihi is not None

    @property
    def etiket_listesi(self):
        if self.etiketler:
            return [tag.strip() for tag in self.etiketler.split(',') if tag.strip()]
        return []


class Yorum(models.Model):
    ONAY_DURUM_CHOICES = [
        ('BEKLEMEDE', 'Beklemede'),
        ('ONAYLANDI', 'Onaylandı'),
        ('REDDEDILDI', 'Reddedildi'),
    ]

    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    puan = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    yorum_metni = models.TextField(blank=True, null=True)
    yorum_tarihi = models.DateTimeField(auto_now_add=True)
    onay_durumu = models.CharField(max_length=20, choices=ONAY_DURUM_CHOICES, default='BEKLEMEDE')

    class Meta:
        db_table = 'yorumlar'
        verbose_name = 'Yorum'
        verbose_name_plural = 'Yorumlar'


class DanisanSaglikVerisi(models.Model):
    id = models.AutoField(primary_key=True)
    danisan = models.OneToOneField(Kullanici, on_delete=models.CASCADE)
    boy = models.SmallIntegerField(blank=True, null=True)
    kilo = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    hedef_kilo = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    alerjiler = models.TextField(blank=True, null=True)
    kronik_hastaliklar = models.TextField(blank=True, null=True)
    son_guncelleme = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'danisansaglikverileri'
        verbose_name = 'Danışan Sağlık Verisi'
        verbose_name_plural = 'Danışan Sağlık Verileri'


class UzmanlikAlani(models.Model):
    id = models.AutoField(primary_key=True)
    alan_adi = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'uzmanlikalanlari'
        verbose_name = 'Uzmanlık Alanı'
        verbose_name_plural = 'Uzmanlık Alanları'

    def __str__(self):
        return self.alan_adi


class DiyetisyenUzmanlikAlani(models.Model):
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE)
    uzmanlik_alani = models.ForeignKey(UzmanlikAlani, on_delete=models.RESTRICT)

    class Meta:
        db_table = 'diyetisyenuzmanlikalanlari'
        unique_together = ['diyetisyen', 'uzmanlik_alani']
        verbose_name = 'Diyetisyen Uzmanlık Alanı'
        verbose_name_plural = 'Diyetisyen Uzmanlık Alanları'


class OdemeHareketi(models.Model):
    ODEME_DURUM_CHOICES = [
        ('BEKLEMEDE', 'Beklemede'),
        ('TAMAMLANDI', 'Tamamlandı'),
        ('IPTAL_EDILDI', 'İptal Edildi'),
        ('IADE_EDILDI', 'İade Edildi'),
    ]
    
    id = models.AutoField(primary_key=True)
    randevu = models.ForeignKey(Randevu, on_delete=models.PROTECT, blank=True, null=True)  # PROTECT kullanımı tutarlı
    danisan = models.ForeignKey(Kullanici, on_delete=models.PROTECT, related_name='odeme_hareketleri_danisan')  # PROTECT'e değiştirildi
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.PROTECT, db_index=True)  # PROTECT ve indeks
    toplam_ucret = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    komisyon_orani = models.DecimalField(max_digits=4, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    komisyon_miktari = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    diyetisyen_kazanci = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    odeme_tarihi = models.DateTimeField(auto_now_add=True, db_index=True)
    odeme_durumu = models.CharField(max_length=50, choices=ODEME_DURUM_CHOICES, default='BEKLEMEDE', db_index=True)

    class Meta:
        db_table = 'odemehareketleri'
        verbose_name = 'Ödeme Hareketi'
        verbose_name_plural = 'Ödeme Hareketleri'
        indexes = [
            models.Index(fields=['diyetisyen', 'odeme_tarihi'], name='idx_payment_dyt_date'),
            models.Index(fields=['danisan', 'odeme_tarihi'], name='idx_payment_patient_date'),
            models.Index(fields=['odeme_durumu', 'odeme_tarihi'], name='idx_payment_status_date'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(toplam_ucret__gte=0),
                name='check_positive_total_amount'
            ),
            models.CheckConstraint(
                check=models.Q(komisyon_orani__gte=0) & models.Q(komisyon_orani__lte=100),
                name='check_commission_rate_valid'
            ),
            models.CheckConstraint(
                check=models.Q(diyetisyen_kazanci__lte=models.F('toplam_ucret')),
                name='check_dietitian_earnings_valid'
            )
        ]


class DiyetisyenOdeme(models.Model):
    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.RESTRICT)
    donem_baslangic = models.DateTimeField()
    donem_bitis = models.DateTimeField()
    odenecek_net_tutar = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    odeme_durumu = models.CharField(max_length=50, default='BEKLEMEDE')
    odeme_tarihi = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'diyetisyenodemeleri'
        verbose_name = 'Diyetisyen Ödeme'
        verbose_name_plural = 'Diyetisyen Ödemeleri'


class AcilIletisim(models.Model):
    id = models.AutoField(primary_key=True)
    talep_eden_kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True)
    talep_tarihi_saati = models.DateTimeField(auto_now_add=True)
    telegram_bildirim_gonderildi_mi = models.BooleanField(default=False)
    cozum_durumu = models.CharField(max_length=50, default='BEKLEMEDE')

    class Meta:
        db_table = 'acililetisim'
        verbose_name = 'Acil İletişim'
        verbose_name_plural = 'Acil İletişimler'


class Bildirim(models.Model):
    BILDIRIM_TUR_CHOICES = [
        ('RANDEVU_YENI', 'Yeni Randevu'),
        ('RANDEVU_ONAY', 'Randevu Onayı'),
        ('RANDEVU_IPTAL', 'Randevu İptali'),
        ('RANDEVU_HATIRLATMA', 'Randevu Hatırlatması'),
        ('ODEME_ONAY', 'Ödeme Onayı'),
        ('ODEME_HATA', 'Ödeme Hatası'),
        ('DIYET_HAZIR', 'Diyet Listesi Hazır'),
        ('DIYETISYEN_ONAY', 'Diyetisyen Onayı'),
        ('SISTEM_DUYURU', 'Sistem Duyurusu'),
        ('GENEL', 'Genel'),
    ]
    
    ONCELIK_CHOICES = [
        ('DUSUK', 'Düşük'),
        ('NORMAL', 'Normal'),
        ('YUKSEK', 'Yüksek'),
        ('KRITIK', 'Kritik'),
    ]
    
    id = models.AutoField(primary_key=True)
    alici_kullanici = models.ForeignKey(Kullanici, on_delete=models.CASCADE, related_name='bildirimler')
    baslik = models.CharField(max_length=200, default='Bildirim')
    mesaj = models.TextField()
    tur = models.CharField(max_length=50, choices=BILDIRIM_TUR_CHOICES, default='GENEL')
    oncelik = models.CharField(max_length=20, choices=ONCELIK_CHOICES, default='NORMAL')
    hedef_url = models.CharField(max_length=500, blank=True, null=True, help_text='Bildirimi tıklandığında yönlendirilecek URL')
    okundu_mu = models.BooleanField(default=False, db_index=True)
    tarih = models.DateTimeField(auto_now_add=True, db_index=True)
    gecerlilik_tarihi = models.DateTimeField(blank=True, null=True, help_text='Bu tarihten sonra bildirim gösterilmez')
    
    # İlgili nesnelere referanslar
    randevu = models.ForeignKey('Randevu', on_delete=models.CASCADE, blank=True, null=True)
    odeme_hareketi = models.ForeignKey('OdemeHareketi', on_delete=models.CASCADE, blank=True, null=True)
    
    class Meta:
        db_table = 'bildirimler'
        verbose_name = 'Bildirim'
        verbose_name_plural = 'Bildirimler'
        ordering = ['-tarih']
        indexes = [
            models.Index(fields=['alici_kullanici', '-tarih']),
            models.Index(fields=['alici_kullanici', 'okundu_mu']),
            models.Index(fields=['tur', '-tarih']),
        ]
    
    def __str__(self):
        return f"{self.alici_kullanici.ad} - {self.baslik}"
    
    def get_redirect_url(self):
        """Bildirim türüne göre yönlendirme URL'si döndürür"""
        if self.hedef_url:
            return self.hedef_url
            
        # Bildirim türüne göre otomatik URL oluştur
        if self.tur.startswith('RANDEVU') and self.randevu:
            return f"/appointment/{self.randevu.id}/"
        elif self.tur.startswith('ODEME') and self.odeme_hareketi:
            return f"/payments/{self.odeme_hareketi.id}/"
        elif self.tur == 'DIYET_HAZIR':
            return "/dashboard/?section=diets"
        elif self.tur == 'DIYETISYEN_ONAY':
            return "/profile/"
        else:
            return "/dashboard/"
    
    def get_icon_class(self):
        """Bildirim türüne göre ikon sınıfı döndürür"""
        icon_map = {
            'RANDEVU_YENI': 'fas fa-calendar-plus text-primary',
            'RANDEVU_ONAY': 'fas fa-calendar-check text-success',
            'RANDEVU_IPTAL': 'fas fa-calendar-times text-danger',
            'RANDEVU_HATIRLATMA': 'fas fa-bell text-warning',
            'ODEME_ONAY': 'fas fa-credit-card text-success',
            'ODEME_HATA': 'fas fa-exclamation-triangle text-danger',
            'DIYET_HAZIR': 'fas fa-clipboard-list text-info',
            'DIYETISYEN_ONAY': 'fas fa-user-check text-success',
            'SISTEM_DUYURU': 'fas fa-bullhorn text-info',
            'GENEL': 'fas fa-info-circle text-secondary',
        }
        return icon_map.get(self.tur, 'fas fa-bell text-secondary')
    
    def get_priority_class(self):
        """Öncelik seviyesine göre CSS sınıfı döndürür"""
        priority_map = {
            'KRITIK': 'border-danger bg-danger bg-opacity-10',
            'YUKSEK': 'border-warning bg-warning bg-opacity-10',
            'NORMAL': 'border-primary bg-primary bg-opacity-10',
            'DUSUK': 'border-secondary bg-secondary bg-opacity-10',
        }
        return priority_map.get(self.oncelik, 'border-secondary')


class SistemAyari(models.Model):
    id = models.AutoField(primary_key=True)
    ayar_adi = models.CharField(max_length=100, unique=True)
    ayar_degeri = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sistemayarlari'
        verbose_name = 'Sistem Ayarı'
        verbose_name_plural = 'Sistem Ayarları'

    def __str__(self):
        return self.ayar_adi


class Sikayet(models.Model):
    id = models.AutoField(primary_key=True)
    sikayet_eden = models.ForeignKey(Kullanici, on_delete=models.RESTRICT, related_name='sikayet_edenler')
    sikayet_edilen = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True, related_name='sikayet_edilenler')
    randevu = models.ForeignKey(Randevu, on_delete=models.SET_NULL, blank=True, null=True)
    sikayet_tipi = models.CharField(max_length=50, blank=True, null=True)
    sikayet_metni = models.TextField()
    sikayet_tarihi = models.DateTimeField(auto_now_add=True)
    cozum_durumu = models.CharField(max_length=50, default='ACIK')

    class Meta:
        db_table = 'sikayetler'
        verbose_name = 'Şikayet'
        verbose_name_plural = 'Şikayetler'


class PromosyonKodu(models.Model):
    INDIRIM_TIP_CHOICES = [
        ('YUZDE', 'Yüzde'),
        ('SABIT', 'Sabit'),
    ]

    id = models.AutoField(primary_key=True)
    kod = models.CharField(max_length=50, unique=True)
    indirim_miktari = models.DecimalField(max_digits=5, decimal_places=2)
    indirim_tipi = models.CharField(max_length=20, choices=INDIRIM_TIP_CHOICES)
    kullanim_limiti = models.IntegerField(default=1)
    kullanim_sayisi = models.IntegerField(default=0)
    gecerlilik_tarihi = models.DateTimeField(blank=True, null=True)
    aktif_mi = models.BooleanField(default=True)

    class Meta:
        db_table = 'promosyonkodlari'
        verbose_name = 'Promosyon Kodu'
        verbose_name_plural = 'Promosyon Kodları'

    def __str__(self):
        return self.kod


class AnalitikVeri(models.Model):
    id = models.AutoField(primary_key=True)
    kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True)
    olay_adi = models.CharField(max_length=100)
    sayfa_url = models.TextField(blank=True, null=True)
    oturum_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analitikveri'
        verbose_name = 'Analitik Veri'
        verbose_name_plural = 'Analitik Verileri'


class PlatformGeriBildirim(models.Model):
    id = models.AutoField(primary_key=True)
    kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True)
    puan = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True, null=True)
    konu = models.CharField(max_length=100, blank=True, null=True)
    metin = models.TextField()
    tarih = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platformgeribildirimleri'
        verbose_name = 'Platform Geri Bildirim'
        verbose_name_plural = 'Platform Geri Bildirimleri'


class Referans(models.Model):
    ONAY_DURUM_CHOICES = [
        ('BEKLEMEDE', 'Beklemede'),
        ('ONAYLANDI', 'Onaylandı'),
        ('REDDEDILDI', 'Reddedildi'),
    ]

    id = models.AutoField(primary_key=True)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    taniklik_metni = models.TextField()
    onay_durumu = models.CharField(max_length=20, choices=ONAY_DURUM_CHOICES, default='BEKLEMEDE')
    yayimlanma_tarihi = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'referanslar'
        verbose_name = 'Referans'
        verbose_name_plural = 'Referanslar'


class MakaleYorum(models.Model):
    id = models.AutoField(primary_key=True)
    makale = models.ForeignKey(Makale, on_delete=models.CASCADE)
    kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True)
    yorum_metni = models.TextField()
    yorum_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'makaleyorumlari'
        verbose_name = 'Makale Yorum'
        verbose_name_plural = 'Makale Yorumları'


class BasariHikayesi(models.Model):
    id = models.AutoField(primary_key=True)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.SET_NULL, blank=True, null=True)
    baslangic_kilo = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    bitis_kilo = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    hikaye_metni = models.TextField()
    fotograflar = models.JSONField(blank=True, null=True)
    yayim_onayi = models.BooleanField(default=False)

    class Meta:
        db_table = 'basarihikayeleri'
        verbose_name = 'Başarı Hikayesi'
        verbose_name_plural = 'Başarı Hikayeleri'


class AdminYonlendirme(models.Model):
    DURUM_CHOICES = [
        ('GERCEKLESTI', 'Gerçekleşti'),
        ('BEKLEMEDE', 'Beklemede'),
        ('REDDEDILDI', 'Reddedildi'),
    ]

    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Kullanici, on_delete=models.RESTRICT, related_name='admin_yonlendirmeleri')
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE, related_name='yonlendirilen_danisan')
    kaynak_diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.SET_NULL, blank=True, null=True, related_name='kaynak_yonlendirmeler')
    hedef_diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.RESTRICT, related_name='hedef_yonlendirmeler')
    neden = models.TextField(blank=True, null=True)
    durum = models.CharField(max_length=20, choices=DURUM_CHOICES, default='GERCEKLESTI')
    ilgili_randevu = models.ForeignKey(Randevu, on_delete=models.SET_NULL, blank=True, null=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adminyonlendirmeleri'
        verbose_name = 'Admin Yönlendirme'
        verbose_name_plural = 'Admin Yönlendirmeleri'


class RandevuMudahaleTalebi(models.Model):
    OLUSTURAN_TUR_CHOICES = [
        ('OTOMATIK', 'Otomatik'),
        ('admin', 'admin'),
        ('SISTEM', 'Sistem'),
    ]

    DURUM_CHOICES = [
        ('ACIK', 'Açık'),
        ('COZUMLENDI', 'Çözümlendi'),
    ]

    id = models.AutoField(primary_key=True)
    randevu = models.ForeignKey(Randevu, on_delete=models.CASCADE)
    olusturan_tur = models.CharField(max_length=20, choices=OLUSTURAN_TUR_CHOICES, default='OTOMATIK')
    durum = models.CharField(max_length=20, choices=DURUM_CHOICES, default='ACIK')
    aciklama = models.TextField(blank=True, null=True)
    olusma_tarihi = models.DateTimeField(auto_now_add=True)
    kapama_tarihi = models.DateTimeField(blank=True, null=True)
    kapatan_admin = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, blank=True, null=True)
    yapilan_islem = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'randevumudahaletalebi'
        verbose_name = 'Randevu Müdahale Talebi'
        verbose_name_plural = 'Randevu Müdahale Talepleri'


class SoruSeti(models.Model):
    id = models.AutoField(primary_key=True)
    ad = models.CharField(max_length=150)
    aciklama = models.TextField(blank=True, null=True)
    aktif_mi = models.BooleanField(default=True)
    hedef_rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, blank=True, null=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sorusetleri'
        verbose_name = 'Soru Seti'
        verbose_name_plural = 'Soru Setleri'

    def __str__(self):
        return self.ad


class Soru(models.Model):
    SORU_TIP_CHOICES = [
        ('SINGLE_CHOICE', 'Tek Seçim'),
        ('MULTI_CHOICE', 'Çoklu Seçim'),
        ('TEXT', 'Metin'),
        ('NUMBER', 'Sayı'),
        ('DATE', 'Tarih'),
    ]

    id = models.AutoField(primary_key=True)
    soru_seti = models.ForeignKey(SoruSeti, on_delete=models.CASCADE)
    soru_metni = models.TextField()
    soru_tipi = models.CharField(max_length=20, choices=SORU_TIP_CHOICES)
    sira = models.IntegerField(default=0)
    gerekli = models.BooleanField(default=False)
    min_deger = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_deger = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_tarih = models.DateField(blank=True, null=True)
    max_tarih = models.DateField(blank=True, null=True)
    placeholder = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'sorular'
        verbose_name = 'Soru'
        verbose_name_plural = 'Sorular'

    def __str__(self):
        return f"{self.soru_seti.ad} - {self.soru_metni[:50]}"


class SoruSecenek(models.Model):
    id = models.AutoField(primary_key=True)
    soru = models.ForeignKey(Soru, on_delete=models.CASCADE)
    etiket = models.CharField(max_length=200)
    deger = models.CharField(max_length=100)
    sira = models.IntegerField(default=0)

    class Meta:
        db_table = 'sorusecenekleri'
        unique_together = ['soru', 'deger']
        verbose_name = 'Soru Seçenek'
        verbose_name_plural = 'Soru Seçenekleri'

    def __str__(self):
        return self.etiket


class AnketOturum(models.Model):
    DURUM_CHOICES = [
        ('ACIK', 'Açık'),
        ('TAMAMLANDI', 'Tamamlandı'),
    ]

    id = models.AutoField(primary_key=True)
    kullanici = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    soru_seti = models.ForeignKey(SoruSeti, on_delete=models.CASCADE)
    durum = models.CharField(max_length=20, choices=DURUM_CHOICES, default='ACIK')
    baslama_tarihi = models.DateTimeField(auto_now_add=True)
    tamamlama_tarihi = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'anketoturumlari'
        unique_together = ['kullanici', 'soru_seti']
        verbose_name = 'Anket Oturum'
        verbose_name_plural = 'Anket Oturumları'


class AnketCevap(models.Model):
    id = models.AutoField(primary_key=True)
    anket_oturum = models.ForeignKey(AnketOturum, on_delete=models.CASCADE)
    soru = models.ForeignKey(Soru, on_delete=models.CASCADE)
    cevap_metin = models.TextField(blank=True, null=True)
    cevap_sayi = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cevap_tarih = models.DateField(blank=True, null=True)
    cevap_secenek = models.ForeignKey(SoruSecenek, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        db_table = 'anketcevaplari'
        unique_together = ['anket_oturum', 'soru']
        verbose_name = 'Anket Cevap'
        verbose_name_plural = 'Anket Cevapları'


class AnketCokluSecim(models.Model):
    id = models.AutoField(primary_key=True)
    anket_cevap = models.ForeignKey(AnketCevap, on_delete=models.CASCADE)
    secenek = models.ForeignKey(SoruSecenek, on_delete=models.CASCADE)

    class Meta:
        db_table = 'anketcoklusecimler'
        unique_together = ['anket_cevap', 'secenek']
        verbose_name = 'Anket Çoklu Seçim'
        verbose_name_plural = 'Anket Çoklu Seçimler'


class DiyetisyenNot(models.Model):
    id = models.AutoField(primary_key=True)
    diyetisyen = models.ForeignKey(Diyetisyen, on_delete=models.CASCADE)
    danisan = models.ForeignKey(Kullanici, on_delete=models.CASCADE, related_name='diyetisyen_notlari')
    baslik = models.CharField(max_length=200, blank=True, null=True)
    not_metin = models.TextField()
    sadece_diyetisyen_gorsun = models.BooleanField(default=True)
    olusturan = models.ForeignKey(Kullanici, on_delete=models.RESTRICT, related_name='olusturulan_notlar')
    olusma_tarihi = models.DateTimeField(auto_now_add=True)
    guncelleme_tarihi = models.DateTimeField(blank=True, null=True)
    silindi = models.BooleanField(default=False)

    class Meta:
        db_table = 'diyetisyennotlari'
        verbose_name = 'Diyetisyen Not'
        verbose_name_plural = 'Diyetisyen Notları'


class Dosya(models.Model):
    BAGLANTI_TIP_CHOICES = [
        ('KULLANICI', 'Kullanıcı'),
        ('RANDEVU', 'Randevu'),
        ('DIYETISYEN_NOTU', 'Diyetisyen Notu'),
        ('DANISAN_SAGLIK', 'Danışan Sağlık'),
        ('MAKALE', 'Makale'),
        ('BASARI_HIKAYESI', 'Başarı Hikayesi'),
    ]

    DOSYA_TUR_CHOICES = [
        ('FOTOGRAF', 'Fotoğraf'),
        ('BELGE', 'Belge'),
        ('DIGER', 'Diğer'),
    ]

    GIZLILIK_CHOICES = [
        ('OZEL', 'Özel'),
        ('DANISAN_GOREBILIR', 'Danışan Görebilir'),
        ('DIYETISYEN_GOREBILIR', 'Diyetisyen Görebilir'),
        ('admin', 'admin'),
        ('HERKESE_ACIK', 'Herkese Açık'),
    ]

    id = models.BigAutoField(primary_key=True)
    yukleyen_kullanici = models.ForeignKey(Kullanici, on_delete=models.CASCADE)
    baglanti_tipi = models.CharField(max_length=30, choices=BAGLANTI_TIP_CHOICES)
    baglanti_id = models.BigIntegerField()
    dosya_adi = models.CharField(max_length=255)
    uzanti = models.CharField(max_length=20, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    boyut_byte = models.BigIntegerField(blank=True, null=True)
    saklama_yolu = models.TextField()
    dosya_turu = models.CharField(max_length=20, choices=DOSYA_TUR_CHOICES)
    aciklama = models.TextField(blank=True, null=True)
    gizlilik = models.CharField(max_length=20, choices=GIZLILIK_CHOICES, default='OZEL')
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dosyalar'
        verbose_name = 'Dosya'
        verbose_name_plural = 'Dosyalar'

    def __str__(self):
        return self.dosya_adi
