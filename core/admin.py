from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Kullanici, Rol, Diyetisyen, DanisanDiyetisyenEslesme,
    Musaitlik, Randevu, DiyetListesi, Makale, MakaleKategori, Yorum,
    DanisanSaglikVerisi, UzmanlikAlani, DiyetisyenUzmanlikAlani,
    Bildirim, OdemeHareketi, DiyetisyenOdeme, AcilIletisim,
    SistemAyari, Sikayet, PromosyonKodu, AnalitikVeri,
    PlatformGeriBildirim, Referans, MakaleYorum, BasariHikayesi,
    AdminYonlendirme, RandevuMudahaleTalebi, SoruSeti, Soru,
    SoruSecenek, AnketOturum, AnketCevap, AnketCokluSecim,
    DiyetisyenNot, Dosya
)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['id', 'rol_adi']
    search_fields = ['rol_adi']


@admin.register(Kullanici)
class KullaniciAdmin(UserAdmin):
    list_display = ['id', 'e_posta', 'ad', 'soyad', 'rol', 'aktif_mi', 'kayit_tarihi']
    list_filter = ['rol', 'aktif_mi', 'kayit_tarihi']
    search_fields = ['e_posta', 'ad', 'soyad']
    ordering = ['-kayit_tarihi']
    
    fieldsets = (
        (None, {'fields': ('e_posta', 'password')}),
        ('Kişisel Bilgiler', {'fields': ('ad', 'soyad', 'telefon')}),
        ('İzinler', {'fields': ('rol', 'aktif_mi', 'is_staff', 'is_superuser')}),
        ('Önemli Tarihler', {'fields': ('last_login', 'son_giris_tarihi')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('e_posta', 'ad', 'soyad', 'rol', 'password1', 'password2'),
        }),
    )


@admin.register(Diyetisyen)
class DiyetisyenAdmin(admin.ModelAdmin):
    list_display = ['kullanici', 'universite', 'hizmet_ucreti']
    search_fields = ['kullanici__ad', 'kullanici__soyad', 'universite']
    list_filter = ['universite']


@admin.register(Randevu)
class RandevuAdmin(admin.ModelAdmin):
    list_display = ['id', 'diyetisyen', 'danisan', 'randevu_tarih_saat', 'durum', 'tip']
    list_filter = ['durum', 'tip', 'randevu_tarih_saat']
    search_fields = ['diyetisyen__kullanici__ad', 'danisan__ad']
    date_hierarchy = 'randevu_tarih_saat'


@admin.register(DiyetListesi)
class DiyetListesiAdmin(admin.ModelAdmin):
    list_display = ['id', 'baslik', 'diyetisyen', 'danisan', 'yuklenme_tarihi']
    list_filter = ['yuklenme_tarihi']
    search_fields = ['baslik', 'diyetisyen__kullanici__ad', 'danisan__ad']


@admin.register(MakaleKategori)
class MakaleKategoriAdmin(admin.ModelAdmin):
    list_display = ['id', 'ad', 'sira', 'aktif_mi', 'olusturma_tarihi']
    list_filter = ['aktif_mi', 'olusturma_tarihi']
    search_fields = ['ad']
    ordering = ['sira', 'ad']
    
    fieldsets = (
        (None, {'fields': ('ad', 'aciklama')}),
        ('Görünüm', {'fields': ('renk', 'sira')}),
        ('Durum', {'fields': ('aktif_mi',)}),
    )


@admin.register(Makale)
class MakaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'baslik', 'yazar_kullanici', 'kategori', 'onay_durumu_colored', 'okunma_sayisi', 'yayimlanma_tarihi']
    list_filter = ['onay_durumu', 'kategori', 'yayimlanma_tarihi', 'olusturma_tarihi']
    search_fields = ['baslik', 'yazar_kullanici__ad', 'yazar_kullanici__soyad', 'ozet', 'etiketler']
    readonly_fields = ['slug', 'okunma_sayisi', 'begeni_sayisi', 'olusturma_tarihi', 'guncelleme_tarihi']
    date_hierarchy = 'yayimlanma_tarihi'
    ordering = ['-olusturma_tarihi']
    list_per_page = 25
    
    def get_fieldsets(self, request, obj=None):
        """Kullanıcı rolüne göre farklı fieldsets döndür"""
        
        # Diyetisyen için basitleştirilmiş fieldsets
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'diyetisyen':
            return (
                ('📝 Temel Bilgiler', {
                    'fields': ('baslik', 'slug', 'kategori'),
                    'description': 'Makalenin temel bilgilerini girin. Slug otomatik oluşturulacaktır.'
                }),
                ('📖 İçerik', {
                    'fields': ('ozet', 'icerik', 'kapak_resmi', 'etiketler'),
                    'description': 'Makale içeriği ve görseller'
                }),
                ('🔍 SEO Optimizasyonu', {
                    'fields': ('seo_baslik', 'seo_aciklama'),
                    'classes': ('collapse',),
                    'description': 'Arama motoru optimizasyonu için başlık ve açıklama'
                }),
            )
        
        # Admin/superuser için tam fieldsets
        return (
            ('📝 Temel Bilgiler', {
                'fields': ('baslik', 'slug', 'kategori', 'yazar_kullanici'),
                'description': 'Makalenin temel bilgilerini girin. Slug otomatik oluşturulacaktır.'
            }),
            ('📖 İçerik', {
                'fields': ('ozet', 'icerik', 'kapak_resmi', 'etiketler'),
                'description': 'Makale içeriği ve görseller'
            }),
            ('🔍 SEO Optimizasyonu', {
                'fields': ('seo_baslik', 'seo_aciklama'),
                'classes': ('collapse',),
                'description': 'Arama motoru optimizasyonu için başlık ve açıklama'
            }),
            ('✅ Durum ve Onay', {
                'fields': ('onay_durumu', 'onaylayan_admin', 'red_sebebi', 'yayimlanma_tarihi'),
                'description': 'Makale onay durumu ve yayımlanma bilgileri'
            }),
            ('📊 İstatistikler', {
                'fields': ('okunma_sayisi', 'begeni_sayisi', 'olusturma_tarihi', 'guncelleme_tarihi'),
                'classes': ('collapse',),
                'description': 'Makale performans metrikleri'
            }),
        )
    
    def onay_durumu_colored(self, obj):
        from django.utils.html import format_html
        colors = {
            'BEKLEMEDE': '#ffc107',
            'ONAYLANDI': '#28a745', 
            'REDDEDILDI': '#dc3545'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.onay_durumu, '#6c757d'),
            obj.get_onay_durumu_display()
        )
    onay_durumu_colored.short_description = 'Onay Durumu'
    onay_durumu_colored.admin_order_field = 'onay_durumu'
    
    def get_queryset(self, request):
        """Diyetisyenler sadece kendi makalelerini görebilir"""
        qs = super().get_queryset(request)
        
        # Superuser veya admin rolü varsa tüm makaleleri göster
        if request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin'):
            return qs
        
        # Diyetisyenler sadece kendi makalelerini görebilir
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'diyetisyen':
            return qs.filter(yazar_kullanici=request.user)
        
        return qs.none()  # Diğer kullanıcılar hiçbir makale göremez
    
    def has_change_permission(self, request, obj=None):
        """Değiştirme izni kontrolü"""
        if request.user.is_superuser:
            return True
            
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin':
            return True
            
        # Diyetisyenler sadece kendi makalelerini düzenleyebilir
        if obj and hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'diyetisyen':
            return obj.yazar_kullanici == request.user
            
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Silme izni kontrolü"""
        if request.user.is_superuser:
            return True
            
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin':
            return True
            
        # Diyetisyenler kendi makalelerini silemez (sadece admin)
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'diyetisyen':
            return False
            
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        # Eğer yazar belirtilmemişse mevcut kullanıcıyı yazar yap
        if not obj.yazar_kullanici:
            obj.yazar_kullanici = request.user
        
        # Diyetisyenler için otomatik değerler
        if hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'diyetisyen':
            # Diyetisyenler sadece kendi makalelerini düzenleyebilir
            if change and obj.yazar_kullanici != request.user:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("Bu makaleyi düzenleme yetkiniz yok.")
                
            # Yeni makale ekliyorsa yazar kendisi olsun
            if not change:
                obj.yazar_kullanici = request.user
                obj.onay_durumu = 'BEKLEMEDE'  # Diyetisyen makaleleri onay bekler
        
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        # Makale istatistikleri
        extra_context = extra_context or {}
        
        from django.utils import timezone
        today = timezone.now().date()
        
        total_articles = Makale.objects.count()
        pending_articles = Makale.objects.filter(onay_durumu='BEKLEMEDE').count()
        approved_articles = Makale.objects.filter(onay_durumu='ONAYLANDI').count()
        published_articles = Makale.objects.filter(yayimlanma_tarihi__isnull=False).count()
        
        extra_context.update({
            'total_articles': total_articles,
            'pending_articles': pending_articles,
            'approved_articles': approved_articles,
            'published_articles': published_articles,
            'today': today,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    actions = ['approve_articles', 'reject_articles', 'publish_articles']
    
    def approve_articles(self, request, queryset):
        from django.utils import timezone
        count = 0
        for article in queryset.filter(onay_durumu='BEKLEMEDE'):
            article.onay_durumu = 'ONAYLANDI'
            article.onaylayan_admin = request.user
            if not article.yayimlanma_tarihi:
                article.yayimlanma_tarihi = timezone.now()
            article.save()
            count += 1
        
        self.message_user(request, f'{count} makale onaylandı.')
    approve_articles.short_description = 'Seçilen makaleleri onayla'
    
    def reject_articles(self, request, queryset):
        count = 0
        for article in queryset.filter(onay_durumu='BEKLEMEDE'):
            article.onay_durumu = 'REDDEDILDI'
            article.onaylayan_admin = request.user
            article.save()
            count += 1
        
        self.message_user(request, f'{count} makale reddedildi.')
    reject_articles.short_description = 'Seçilen makaleleri reddet'
    
    def publish_articles(self, request, queryset):
        from django.utils import timezone
        count = 0
        for article in queryset.filter(onay_durumu='ONAYLANDI', yayimlanma_tarihi__isnull=True):
            article.yayimlanma_tarihi = timezone.now()
            article.save()
            count += 1
        
        self.message_user(request, f'{count} makale yayımlandı.')
    publish_articles.short_description = 'Seçilen onaylı makaleleri yayımla'


@admin.register(Yorum)
class YorumAdmin(admin.ModelAdmin):
    list_display = ['id', 'diyetisyen', 'danisan', 'puan', 'onay_durumu', 'yorum_tarihi']
    list_filter = ['puan', 'onay_durumu', 'yorum_tarihi']
    search_fields = ['diyetisyen__kullanici__ad', 'danisan__ad']


@admin.register(UzmanlikAlani)
class UzmanlikAlaniAdmin(admin.ModelAdmin):
    list_display = ['id', 'alan_adi']
    search_fields = ['alan_adi']


@admin.register(OdemeHareketi)
class OdemeHareketiAdmin(admin.ModelAdmin):
    list_display = ['id', 'randevu', 'danisan', 'diyetisyen', 'toplam_ucret', 'odeme_durumu', 'odeme_tarihi']
    list_filter = ['odeme_durumu', 'odeme_tarihi']
    search_fields = ['danisan__ad', 'diyetisyen__kullanici__ad']


@admin.register(DiyetisyenOdeme)
class DiyetisyenOdemeAdmin(admin.ModelAdmin):
    list_display = ['id', 'diyetisyen', 'donem_baslangic', 'donem_bitis', 'odenecek_net_tutar', 'odeme_durumu']
    list_filter = ['odeme_durumu', 'donem_baslangic']


@admin.register(Sikayet)
class SikayetAdmin(admin.ModelAdmin):
    list_display = ['id', 'sikayet_eden', 'sikayet_edilen', 'sikayet_tipi', 'cozum_durumu', 'sikayet_tarihi']
    list_filter = ['sikayet_tipi', 'cozum_durumu', 'sikayet_tarihi']
    search_fields = ['sikayet_eden__ad', 'sikayet_edilen__ad']


@admin.register(PromosyonKodu)
class PromosyonKoduAdmin(admin.ModelAdmin):
    list_display = ['kod', 'indirim_miktari', 'indirim_tipi', 'kullanim_sayisi', 'kullanim_limiti', 'aktif_mi']
    list_filter = ['indirim_tipi', 'aktif_mi']
    search_fields = ['kod']


@admin.register(SistemAyari)
class SistemAyariAdmin(admin.ModelAdmin):
    list_display = ['ayar_adi', 'ayar_degeri']
    search_fields = ['ayar_adi']


@admin.register(RandevuMudahaleTalebi)
class RandevuMudahaleTalebiAdmin(admin.ModelAdmin):
    list_display = ['id', 'randevu', 'olusturan_tur', 'durum', 'olusma_tarihi']
    list_filter = ['olusturan_tur', 'durum', 'olusma_tarihi']


@admin.register(SoruSeti)
class SoruSetiAdmin(admin.ModelAdmin):
    list_display = ['id', 'ad', 'hedef_rol', 'aktif_mi', 'olusturma_tarihi']
    list_filter = ['hedef_rol', 'aktif_mi']
    search_fields = ['ad']


@admin.register(Soru)
class SoruAdmin(admin.ModelAdmin):
    list_display = ['id', 'soru_seti', 'soru_tipi', 'sira', 'gerekli']
    list_filter = ['soru_seti', 'soru_tipi', 'gerekli']
    ordering = ['soru_seti', 'sira']


@admin.register(AnketOturum)
class AnketOturumAdmin(admin.ModelAdmin):
    list_display = ['id', 'kullanici', 'soru_seti', 'durum', 'baslama_tarihi']
    list_filter = ['durum', 'soru_seti', 'baslama_tarihi']


@admin.register(BasariHikayesi)
class BasariHikayesiAdmin(admin.ModelAdmin):
    list_display = ['id', 'danisan', 'diyetisyen', 'baslangic_kilo', 'bitis_kilo', 'yayim_onayi']
    list_filter = ['yayim_onayi']


@admin.register(Dosya)
class DosyaAdmin(admin.ModelAdmin):
    list_display = ['id', 'dosya_adi', 'yukleyen_kullanici', 'baglanti_tipi', 'dosya_turu', 'olusturma_tarihi']
    list_filter = ['baglanti_tipi', 'dosya_turu', 'gizlilik', 'olusturma_tarihi']
    search_fields = ['dosya_adi', 'yukleyen_kullanici__ad']


# Basit admin kayıtları
admin.site.register(DanisanDiyetisyenEslesme)
admin.site.register(Musaitlik)
admin.site.register(DanisanSaglikVerisi)
admin.site.register(DiyetisyenUzmanlikAlani)
admin.site.register(Bildirim)
admin.site.register(AcilIletisim)
admin.site.register(AnalitikVeri)
admin.site.register(PlatformGeriBildirim)
admin.site.register(Referans)
admin.site.register(MakaleYorum)
admin.site.register(AdminYonlendirme)
admin.site.register(SoruSecenek)
admin.site.register(AnketCevap)
admin.site.register(AnketCokluSecim)
admin.site.register(DiyetisyenNot)
