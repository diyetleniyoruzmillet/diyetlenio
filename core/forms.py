from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from .models import Kullanici, Diyetisyen, UzmanlikAlani, Rol, Randevu, Musaitlik, Makale, MakaleKategori


class LoginForm(forms.Form):
    e_posta = forms.EmailField(
        required=True,
        error_messages={'required': 'E-posta adresi gereklidir.'},
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'E-posta adresinizi girin'
        })
    )
    password = forms.CharField(
        required=True,
        error_messages={'required': 'Şifre gereklidir.'},
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifrenizi girin'
        })
    )
    remember_me = forms.BooleanField(required=False)


class RegisterForm(forms.Form):
    USER_TYPE_CHOICES = [
        ('danisan', 'Danışan'),
        ('diyetisyen', 'Diyetisyen'),
    ]

    # Common fields
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, widget=forms.HiddenInput())
    ad = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Adınızı girin'
        })
    )
    soyad = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Soyadınızı girin'
        })
    )
    e_posta = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'E-posta adresinizi girin'
        })
    )
    telefon = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+90 555 123 4567',
            'autocomplete': 'off'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifrenizi girin'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifrenizi tekrar girin'
        })
    )

    # Dietitian specific fields
    universite = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Üniversite adını girin'
        })
    )
    hizmet_ucreti = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '200.00'
        })
    )
    uzmanlik_alanlari = forms.ModelMultipleChoiceField(
        queryset=UzmanlikAlani.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    hakkinda_bilgi = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Kendinizi tanıtın...'
        })
    )
    profil_fotografi = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.webp'
        })
    )
    diploma_belgesi = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )

    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'Kullanım şartlarını kabul etmelisiniz.'}
    )

    def clean_e_posta(self):
        e_posta = self.cleaned_data['e_posta']
        if Kullanici.objects.filter(e_posta=e_posta).exists():
            raise ValidationError("Bu e-posta adresi zaten kullanılıyor.")
        return e_posta

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Şifreler eşleşmiyor.")
        
        if len(password1) < 8:
            raise ValidationError("Şifre en az 8 karakter olmalıdır.")
        
        return password2

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        
        if user_type == 'diyetisyen':
            # Dietitian required fields
            universite = cleaned_data.get('universite')
            hizmet_ucreti = cleaned_data.get('hizmet_ucreti')
            
            if not universite:
                self.add_error('universite', 'Bu alan zorunludur.')
            if not hizmet_ucreti:
                self.add_error('hizmet_ucreti', 'Bu alan zorunludur.')
        
        return cleaned_data

    def save(self):
        cleaned_data = self.cleaned_data
        user_type = cleaned_data['user_type']
        
        # Get or create roles
        if user_type == 'diyetisyen':
            rol, created = Rol.objects.get_or_create(rol_adi='diyetisyen')
        else:
            rol, created = Rol.objects.get_or_create(rol_adi='danisan')
        
        # Create user with proper name capitalization
        # All users should be active, dietitians will have approval status separately
        aktif_mi = True
        
        user = Kullanici.objects.create_user(
            e_posta=cleaned_data['e_posta'],
            ad=cleaned_data['ad'].title(),
            soyad=cleaned_data['soyad'].title(),
            telefon=cleaned_data.get('telefon', ''),
            rol=rol,
            password=cleaned_data['password1'],
            aktif_mi=aktif_mi
        )
        
        # Create dietitian profile if needed
        if user_type == 'diyetisyen':
            diyetisyen = Diyetisyen.objects.create(
                kullanici=user,
                universite=cleaned_data['universite'],
                hizmet_ucreti=cleaned_data['hizmet_ucreti'],
                hakkinda_bilgi=cleaned_data.get('hakkinda_bilgi', ''),
                profil_fotografi=cleaned_data.get('profil_fotografi', None)
            )
            
            # Add specialties
            uzmanlik_alanlari = cleaned_data.get('uzmanlik_alanlari')
            if uzmanlik_alanlari:
                from .models import DiyetisyenUzmanlikAlani
                for uzmanlik in uzmanlik_alanlari:
                    DiyetisyenUzmanlikAlani.objects.create(
                        diyetisyen=diyetisyen,
                        uzmanlik_alani=uzmanlik
                    )
            
            # Create notification for all admin users
            self._notify_admins_new_dietitian(user, diyetisyen)
        
        return user
    
    def _notify_admins_new_dietitian(self, user, diyetisyen):
        """Create notifications for admin users about new dietitian registration"""
        try:
            from .models import Bildirim
            from django.utils import timezone
            
            # Get all admin users
            admin_users = Kullanici.objects.filter(
                Q(is_superuser=True) | Q(rol__rol_adi='admin'),
                aktif_mi=True
            )
            
            # Create notification for each admin
            for admin in admin_users:
                Bildirim.objects.create(
                    alici_kullanici=admin,
                    baslik='Yeni Diyetisyen Başvurusu',
                    mesaj=f'{user.ad} {user.soyad} ({user.e_posta}) adlı diyetisyen onay bekliyor. Üniversite: {diyetisyen.universite}',
                    tur='DIYETISYEN_BASVURU',
                    okundu_mu=False,
                    tarih=timezone.now(),
                    redirect_url='/dashboard/?section=dietitians'
                )
        except Exception as e:
            # Don't break registration if notification fails
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create admin notification for dietitian registration: {str(e)}")


class RandevuForm(forms.ModelForm):
    class Meta:
        model = Randevu
        fields = ['randevu_tarih_saat', 'tip']
        widgets = {
            'randevu_tarih_saat': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control'
                }
            ),
            'tip': forms.Select(
                attrs={'class': 'form-select'}
            )
        }

    def __init__(self, *args, **kwargs):
        self.diyetisyen = kwargs.pop('diyetisyen', None)
        super().__init__(*args, **kwargs)
        
        # Set minimum date to today
        today = timezone.now().strftime('%Y-%m-%dT%H:%M')
        self.fields['randevu_tarih_saat'].widget.attrs['min'] = today

    def clean_randevu_tarih_saat(self):
        tarih_saat = self.cleaned_data['randevu_tarih_saat']
        
        if tarih_saat < timezone.now():
            raise ValidationError("Geçmiş bir tarih seçemezsiniz.")
        
        # Check if appointment time is in working hours (9-18)
        if tarih_saat.hour < 9 or tarih_saat.hour >= 18:
            raise ValidationError("Randevu saati 09:00-18:00 arasında olmalıdır.")
        
        # Check if the time slot is available
        if self.diyetisyen:
            existing_appointment = Randevu.objects.filter(
                diyetisyen=self.diyetisyen,
                randevu_tarih_saat=tarih_saat,
                durum__in=['BEKLEMEDE', 'ONAYLANDI']
            ).exists()
            
            if existing_appointment:
                raise ValidationError("Bu saat için randevu mevcuttur.")
        
        return tarih_saat


class DiyetisyenProfilForm(forms.ModelForm):
    """Diyetisyen profil güncelleme formu"""
    
    class Meta:
        model = Diyetisyen
        fields = ['universite', 'hakkinda_bilgi', 'hizmet_ucreti', 'profil_fotografi']
        widgets = {
            'universite': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Üniversite adınızı girin'
            }),
            'hakkinda_bilgi': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Kendinizden bahsedin...'
            }),
            'hizmet_ucreti': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '200.00',
                'step': '0.01'
            }),
            'profil_fotografi': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.webp'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profil_fotografi'].help_text = 'JPG, JPEG, PNG veya WEBP formatında fotoğraf yükleyebilirsiniz.'


class KullaniciProfilForm(forms.ModelForm):
    """Kullanıcı profil güncelleme formu"""
    
    class Meta:
        model = Kullanici
        fields = ['ad', 'soyad', 'telefon']
        widgets = {
            'ad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adınızı girin'
            }),
            'soyad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Soyadınızı girin'
            }),
            'telefon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+90 555 123 4567'
            })
        }


class MakaleForm(forms.ModelForm):
    class Meta:
        model = Makale
        fields = [
            'baslik', 'slug', 'kategori', 'ozet', 'icerik', 
            'kapak_resmi', 'etiketler', 'seo_baslik', 'seo_aciklama'
        ]
        widgets = {
            'baslik': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Makale başlığını giriniz...',
                'maxlength': 255
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL slug (otomatik oluşturulur)',
                'readonly': True
            }),
            'kategori': forms.Select(attrs={
                'class': 'form-control'
            }),
            'ozet': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Makale özetini yazınız... (160 karakter önerilir)',
                'rows': 3,
                'maxlength': 500
            }),
            'icerik': forms.Textarea(attrs={
                'class': 'form-control tinymce-editor',
                'placeholder': 'Makale içeriğini yazınız...',
                'rows': 15
            }),
            'kapak_resmi': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kapak resmi URL\'si (opsiyonel)'
            }),
            'etiketler': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Etiketler (virgülle ayırın)',
                'data-bs-toggle': 'tooltip',
                'title': 'Örnek: beslenme, diyet, sağlık'
            }),
            'seo_baslik': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO başlığı (60 karakter önerilir)',
                'maxlength': 60
            }),
            'seo_aciklama': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'SEO açıklaması (160 karakter önerilir)',
                'rows': 2,
                'maxlength': 160
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Kategori seçeneklerini aktif olanlarla sınırla
        self.fields['kategori'].queryset = MakaleKategori.objects.filter(aktif_mi=True).order_by('sira', 'ad')
        self.fields['kategori'].empty_label = "Kategori seçiniz"
        
        # Eğer diyetisyen ise bazı alanları gizle
        if self.user and hasattr(self.user, 'rol') and self.user.rol.rol_adi == 'diyetisyen':
            # Slug'ı readonly yap
            self.fields['slug'].widget.attrs['readonly'] = True
            self.fields['slug'].help_text = 'URL otomatik olarak oluşturulacaktır'

    def clean_baslik(self):
        baslik = self.cleaned_data.get('baslik')
        if baslik:
            if len(baslik) < 10:
                raise forms.ValidationError('Başlık en az 10 karakter olmalıdır.')
            if len(baslik) > 255:
                raise forms.ValidationError('Başlık en fazla 255 karakter olabilir.')
        return baslik

    def clean_ozet(self):
        ozet = self.cleaned_data.get('ozet')
        if ozet and len(ozet) < 50:
            raise forms.ValidationError('Özet en az 50 karakter olmalıdır.')
        return ozet

    def clean_icerik(self):
        icerik = self.cleaned_data.get('icerik')
        if icerik:
            if len(icerik) < 200:
                raise forms.ValidationError('İçerik en az 200 karakter olmalıdır.')
        return icerik

    def clean_etiketler(self):
        etiketler = self.cleaned_data.get('etiketler', '')
        if etiketler:
            # Etiketleri temizle ve kontrol et
            etiket_listesi = [tag.strip().lower() for tag in etiketler.split(',') if tag.strip()]
            if len(etiket_listesi) > 10:
                raise forms.ValidationError('En fazla 10 etiket ekleyebilirsiniz.')
            return ', '.join(etiket_listesi)
        return etiketler

    def save(self, commit=True):
        makale = super().save(commit=False)
        
        # Slug oluştur
        if not makale.slug and makale.baslik:
            from django.utils.text import slugify
            import uuid
            
            base_slug = slugify(makale.baslik)
            if not base_slug:
                base_slug = str(uuid.uuid4())[:8]
            
            # Benzersizlik kontrolü
            original_slug = base_slug
            counter = 1
            while Makale.objects.filter(slug=base_slug).exclude(pk=makale.pk).exists():
                base_slug = f"{original_slug}-{counter}"
                counter += 1
            
            makale.slug = base_slug
        
        # SEO alanlarını otomatik doldur
        if not makale.seo_baslik and makale.baslik:
            makale.seo_baslik = makale.baslik[:60]
        
        if not makale.seo_aciklama and makale.ozet:
            makale.seo_aciklama = makale.ozet[:160]
        
        # Kullanıcı bilgisini set et
        if self.user and not makale.yazar_kullanici:
            makale.yazar_kullanici = self.user
        
        # Diyetisyen makaleleri onay bekler
        if self.user and hasattr(self.user, 'rol') and self.user.rol.rol_adi == 'diyetisyen':
            makale.onay_durumu = 'BEKLEMEDE'
        
        if commit:
            makale.save()
        
        return makale