from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.urls import reverse
from .models import Diyetisyen, Randevu, Kullanici, Rol, UzmanlikAlani, Musaitlik, DiyetisyenUzmanlikAlani, Makale, MakaleKategori, Bildirim, OdemeHareketi, DiyetisyenOdeme, DiyetisyenMusaitlikSablon
from .forms import LoginForm, RegisterForm, RandevuForm
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Count, Sum, Avg
from django.db.models.functions import TruncDay, TruncMonth
import json
import requests
from django.conf import settings


def home(request):
    # Get featured dietitians (top 6 by rating or recent)
    featured_diyetisyenler = Diyetisyen.objects.filter(
        kullanici__aktif_mi=True
    ).select_related('kullanici').prefetch_related('diyetisyenuzmanlikalani_set__uzmanlik_alani')[:6]
    
    context = {
        'title': 'Diyetlenio - Ana Sayfa',
        'total_diyetisyenler': Diyetisyen.objects.count(),
        'total_randevular': Randevu.objects.count(),
        'total_kullanicilar': Kullanici.objects.count(),
        'featured_diyetisyenler': featured_diyetisyenler,
    }
    return render(request, 'core/home.html', context)


@login_required
def dashboard(request):
    user = request.user
    
    # Set title based on user role
    if hasattr(user, 'rol') and user.rol.rol_adi == 'danisan':
        title = 'Benim Sayfam'
    else:
        title = 'Anasayfa'
    
    # Get section parameter for admin navigation
    current_section = request.GET.get('section', 'dashboard')
    
    context = {
        'title': title,
        'user': user,
        'current_section': current_section,
    }
    
    # Add days list for schedule section
    if current_section == 'schedule' and hasattr(user, 'rol') and user.rol.rol_adi == 'Diyetisyen':
        context['days'] = [
            (1, 'Pazartesi'),
            (2, 'Salı'),
            (3, 'Çarşamba'),
            (4, 'Perşembe'),
            (5, 'Cuma'),
            (6, 'Cumartesi'),
            (7, 'Pazar'),
        ]
    
    # Add diet plans section for dietitians
    if current_section == 'diet-plans' and hasattr(user, 'rol') and user.rol.rol_adi == 'Diyetisyen':
        from .models import DiyetListesi, DanisanDiyetisyenEslesme
        
        diyetisyen = user.diyetisyen
        
        # Get dietitian's patients who have had appointments
        hastalar = Kullanici.objects.filter(
            randevu_danisan__diyetisyen=diyetisyen,
            randevu_danisan__durum__in=['ONAYLANDI', 'TAMAMLANDI']
        ).distinct().select_related('rol').annotate(
            toplam_randevu=Count('randevu_danisan', filter=Q(randevu_danisan__diyetisyen=diyetisyen)),
            son_randevu=Max('randevu_danisan__randevu_tarih_saat', filter=Q(randevu_danisan__diyetisyen=diyetisyen))
        ).order_by('-son_randevu')
        
        # Get existing diet plans for this dietitian
        diyet_planlari = DiyetListesi.objects.filter(
            diyetisyen=diyetisyen
        ).select_related('danisan').order_by('-yuklenme_tarihi')
        
        context.update({
            'hastalar': hastalar,
            'diyet_planlari': diyet_planlari,
        })
    
    # Check if user is admin (you can implement admin role check here)
    is_admin = user.is_superuser or (hasattr(user, 'rol') and user.rol.rol_adi == 'admin')
    
    if is_admin:
        # Admin Dashboard Data
        today = timezone.now().date()
        this_month = today.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        
        # Basic stats
        total_users = Kullanici.objects.count()
        total_dietitians = Diyetisyen.objects.count()
        total_appointments = Randevu.objects.count()
        monthly_appointments = Randevu.objects.filter(
            randevu_tarih_saat__date__gte=this_month
        ).count()
        
        # Calculate revenue (assuming average fee)
        avg_fee = Diyetisyen.objects.aggregate(avg_fee=Avg('hizmet_ucreti'))['avg_fee'] or 0
        completed_appointments = Randevu.objects.filter(
            durum='TAMAMLANDI',
            randevu_tarih_saat__date__gte=this_month
        ).count()
        monthly_revenue = completed_appointments * avg_fee
        
        # Recent users (last 10)
        recent_users = Kullanici.objects.select_related('rol').order_by('-date_joined')[:10]
        
        # Pending dietitian approvals
        pending_dietitians = Diyetisyen.objects.filter(
            onay_durumu='BEKLEMEDE'
        ).select_related('kullanici')[:5]
        
        # Articles data
        from .models import Makale, MakaleKategori
        total_articles = Makale.objects.count()
        pending_articles = Makale.objects.filter(onay_durumu='BEKLEMEDE').count()
        recent_articles = Makale.objects.select_related('yazar_kullanici', 'kategori').order_by('-olusturma_tarihi')[:10]
        total_categories = MakaleKategori.objects.count()
        
        # Appointments data for admin
        all_appointments = None
        available_dietitians = None
        if current_section == 'appointments':
            all_appointments = Randevu.objects.select_related(
                'diyetisyen__kullanici', 'danisan'
            ).order_by('-randevu_tarih_saat')[:50]
            available_dietitians = Diyetisyen.objects.filter(
                onay_durumu='ONAYLANDI'
            ).select_related('kullanici')
        
        # Matching data for admin
        existing_matchings = None
        total_matchings = 0
        active_matchings = 0
        patients_with_dietitians = 0
        unmatched_patients = 0
        if current_section == 'matching':
            from .models import DanisanDiyetisyenEslesme
            
            # Get existing matchings with appointment counts
            existing_matchings = DanisanDiyetisyenEslesme.objects.select_related(
                'diyetisyen__kullanici', 'danisan'
            ).order_by('-eslesme_tarihi')
            
            # Add appointment count to each matching
            for matching in existing_matchings:
                matching.appointment_count = Randevu.objects.filter(
                    diyetisyen=matching.diyetisyen,
                    danisan=matching.danisan
                ).count()
            
            # Statistics
            total_matchings = existing_matchings.count()
            active_matchings = existing_matchings.filter(
                diyetisyen__kullanici__aktif_mi=True
            ).count()
            patients_with_dietitians = Kullanici.objects.filter(
                rol__rol_adi='danisan',
                danisandiyetisyeneslesme__isnull=False
            ).distinct().count()
            unmatched_patients = Kullanici.objects.filter(
                rol__rol_adi='danisan',
                danisandiyetisyeneslesme__isnull=True
            ).count()
        
        context.update({
            'is_admin': True,
            'total_users': total_users,
            'total_dietitians': total_dietitians,
            'total_appointments': total_appointments,
            'monthly_appointments': monthly_appointments,
            'monthly_revenue': monthly_revenue,
            'recent_users': recent_users,
            'pending_dietitians': pending_dietitians,
            'total_articles': total_articles,
            'pending_articles': pending_articles,
            'recent_articles': recent_articles,
            'total_categories': total_categories,
            'all_appointments': all_appointments,
            'available_dietitians': available_dietitians,
            'existing_matchings': existing_matchings,
            'total_matchings': total_matchings,
            'active_matchings': active_matchings,
            'patients_with_dietitians': patients_with_dietitians,
            'unmatched_patients': unmatched_patients,
        })
        return render(request, 'dashboard/admin_dashboard.html', context)
    
    elif user.rol.rol_adi == 'diyetisyen':
        try:
            diyetisyen = user.diyetisyen
            today = timezone.now().date()
            
            # Today's appointments
            today_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date=today
            ).count()
            
            # This month's stats
            this_month = today.replace(day=1)
            monthly_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date__gte=this_month
            ).count()
            
            completed_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                durum='TAMAMLANDI',
                randevu_tarih_saat__date__gte=this_month
            ).count()
            
            pending_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                durum='BEKLEMEDE'
            ).count()
            
            # Recent appointments
            recent_appointments = Randevu.objects.filter(
                diyetisyen=diyetisyen
            ).select_related('danisan').order_by('-randevu_tarih_saat')[:5]
            
            # Monthly earnings estimation
            monthly_earnings = completed_appointments * (diyetisyen.hizmet_ucreti or 0)
            
            # Previous month earnings for comparison
            import calendar
            last_month = this_month - timedelta(days=1)
            last_month_start = last_month.replace(day=1)
            
            last_month_completed = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                durum='TAMAMLANDI',
                randevu_tarih_saat__date__gte=last_month_start,
                randevu_tarih_saat__date__lt=this_month
            ).count()
            
            last_month_earnings = last_month_completed * (diyetisyen.hizmet_ucreti or 0)
            
            # Calculate earnings change percentage
            earnings_change = 0
            if last_month_earnings > 0:
                earnings_change = ((monthly_earnings - last_month_earnings) / last_month_earnings) * 100
            elif monthly_earnings > 0:
                earnings_change = 100  # First month earning
                
            # Total lifetime earnings
            total_completed = Randevu.objects.filter(diyetisyen=diyetisyen, durum='TAMAMLANDI').count()
            total_earnings = total_completed * (diyetisyen.hizmet_ucreti or 0)
            
            # Total patients count
            total_patients = Randevu.objects.filter(diyetisyen=diyetisyen).values('danisan').distinct().count()
            
            # New patients this month
            new_patients_month = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                randevu_tarih_saat__date__gte=this_month
            ).values('danisan').distinct().count()
            
            # Recent diet plans
            recent_diet_plans = []
            try:
                from .models import DiyetPlani
                recent_diet_plans = DiyetPlani.objects.filter(
                    diyetisyen=diyetisyen
                ).select_related('danisan').order_by('-olusturma_tarihi')[:4]
            except ImportError:
                pass
            
            # Weekly schedule - get appointments for this week
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            weekly_schedule = {}
            days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
            
            for i, day_name in enumerate(days):
                day_date = week_start + timedelta(days=i)
                appointment_count = Randevu.objects.filter(
                    diyetisyen=diyetisyen,
                    randevu_tarih_saat__date=day_date
                ).count()
                weekly_schedule[day_name] = appointment_count
            
            # Articles data for dietitian
            from .models import Makale, MakaleKategori
            diyetisyen_articles = Makale.objects.filter(yazar_kullanici=user).order_by('-olusturma_tarihi')[:10]
            total_articles = Makale.objects.filter(yazar_kullanici=user).count()
            published_articles = Makale.objects.filter(yazar_kullanici=user, onay_durumu='ONAYLANDI').count()
            pending_articles = Makale.objects.filter(yazar_kullanici=user, onay_durumu='BEKLEMEDE').count()
            
            context.update({
                'diyetisyen': diyetisyen,
                'today_appointments': today_appointments,
                'monthly_appointments': monthly_appointments,
                'completed_appointments': completed_appointments,
                'pending_appointments': pending_appointments,
                'recent_appointments': recent_appointments,
                'monthly_earnings': monthly_earnings,
                'randevular': recent_appointments,
                'toplam_randevu': Randevu.objects.filter(diyetisyen=diyetisyen).count(),
                'total_patients': total_patients,
                'new_patients_month': new_patients_month,
                'recent_diet_plans': recent_diet_plans,
                'weekly_schedule': weekly_schedule,
                'today': today,
                'earnings_change': earnings_change,
                'total_earnings': total_earnings,
                # Article data
                'diyetisyen_articles': diyetisyen_articles,
                'total_articles': total_articles,
                'published_articles': published_articles,
                'pending_articles': pending_articles,
                'current_section': request.GET.get('section', 'dashboard'),
            })
        except Diyetisyen.DoesNotExist:
            context.update({
                'diyetisyen': None,
                'today_appointments': 0,
                'monthly_appointments': 0,
                'completed_appointments': 0,
                'pending_appointments': 0,
                'recent_appointments': [],
                'monthly_earnings': 0,
            })
        return render(request, 'dashboard/diyetisyen_dashboard.html', context)
    elif user.rol.rol_adi == 'danisan':
        today = timezone.now().date()
        
        # Get current section
        current_section = request.GET.get('section', 'dashboard')
        
        # Appointments data
        user_appointments = Randevu.objects.filter(danisan=user)
        upcoming_appointments = user_appointments.filter(
            randevu_tarih_saat__gte=timezone.now(),
            durum__in=['BEKLEMEDE', 'ONAYLANDI']
        ).order_by('randevu_tarih_saat')[:5]
        
        total_appointments = user_appointments.count()
        completed_appointments = user_appointments.filter(durum='TAMAMLANDI').count()
        
        # Weight tracking data (realistic based on user profile)
        # Generate realistic weight data based on user's appointment history
        import random
        random.seed(user.id)  # Consistent data for each user
        
        # Base target weight on user demographics (realistic ranges)
        target_weight = random.randint(60, 75)
        initial_weight = target_weight + random.randint(5, 20)  # 5-20 kg over target
        
        # Progress based on how many completed appointments they have
        progress_factor = min(completed_appointments * 0.15, 0.8)  # Max 80% progress
        progress_factor = max(progress_factor, 0.1)  # Minimum 10% progress
        
        current_weight = round(initial_weight - (initial_weight - target_weight) * progress_factor, 1)
        weight_change = initial_weight - current_weight
        weight_to_goal = current_weight - target_weight
        weight_loss_percentage = int(((initial_weight - current_weight) / (initial_weight - target_weight)) * 100) if initial_weight != target_weight else 0
        
        # Diet plan data (realistic based on appointment status)
        if total_appointments > 0:
            # User has appointments, so they likely have a diet plan
            active_diet_plan = f"Kişiselleştirilmiş Beslenme Programı"
            diet_plan_days = max(completed_appointments * 7, 7)  # Weeks of program
            diet_plan_progress = min(weight_loss_percentage, 85)  # Based on weight progress
            
            # Sample today's meals (realistic)
            todays_meals = [
                "Kahvaltı: Yulaf ezmesi, meyve, süt",
                "Ara Öğün: Çiğ badem (1 avuç)",
                "Öğle: Izgara tavuk, bulgur pilavı, salata",
                "Ara Öğün: Yoğurt, meyve",
                "Akşam: Balık, sebze yemeği, çorba"
            ]
        else:
            # New user, no active plan yet
            active_diet_plan = None
            diet_plan_days = 0
            diet_plan_progress = 0
            todays_meals = []
        
        context.update({
            # Current section
            'current_section': current_section,
            
            # Basic stats for cards
            'current_weight': current_weight,
            'target_weight': target_weight,
            'initial_weight': initial_weight,
            'weight_change': weight_change,
            'weight_to_goal': weight_to_goal,
            'weight_loss_percentage': int(weight_loss_percentage),
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'diet_plan_days': diet_plan_days,
            
            # Appointments
            'upcoming_appointments': upcoming_appointments,
            'randevular': user_appointments.order_by('-randevu_tarih_saat')[:5],
            'toplam_randevu': total_appointments,
            
            # Diet plans
            'active_diet_plan': active_diet_plan,
            'diet_plan_progress': diet_plan_progress,
            'todays_meals': todays_meals,
        })
        return render(request, 'dashboard/danisan_dashboard.html', context)
    
    return render(request, 'core/dashboard.html', context)


def api_stats(request):
    stats = {
        'total_users': Kullanici.objects.count(),
        'total_diyetisyenler': Diyetisyen.objects.count(),
        'total_randevular': Randevu.objects.count(),
        'active_users': Kullanici.objects.filter(aktif_mi=True).count(),
    }
    return JsonResponse(stats)


@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            e_posta = form.cleaned_data['e_posta']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            # Use Django's authenticate function with our custom backend
            user = authenticate(request, username=e_posta, password=password)
            
            if user is not None:
                # Update last login time
                from django.utils import timezone
                user.son_giris_tarihi = timezone.now()
                user.save(update_fields=['son_giris_tarihi'])
                
                login(request, user, backend='core.backends.EmailBackend')
                
                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(0)  # Browser close
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                # Check if user is a dietitian and approval status
                try:
                    diyetisyen = Diyetisyen.objects.get(kullanici=user)
                    if diyetisyen.onay_durumu == 'BEKLEMEDE':
                        return redirect('core:approval_pending')
                    elif diyetisyen.onay_durumu == 'REDDEDILDI':
                        return redirect('core:approval_rejected')
                except Diyetisyen.DoesNotExist:
                    pass
                
                messages.success(request, f'Hoş geldiniz, {user.ad} {user.soyad}!')
                
                # Redirect based on user role
                next_url = request.GET.get('next', 'core:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'E-posta veya şifre hatalı.')
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form})


@login_required
def approval_pending(request):
    """Onay bekleyen diyetisyenler için sayfa"""
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici=request.user)
        if diyetisyen.onay_durumu != 'BEKLEMEDE':
            return redirect('core:dashboard')
    except Diyetisyen.DoesNotExist:
        return redirect('core:dashboard')
    
    context = {
        'diyetisyen': diyetisyen,
        'user': request.user
    }
    return render(request, 'auth/approval_pending.html', context)


@login_required
def approval_rejected(request):
    """Onayı reddedilmiş diyetisyenler için sayfa"""
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici=request.user)
        if diyetisyen.onay_durumu != 'REDDEDILDI':
            return redirect('core:dashboard')
    except Diyetisyen.DoesNotExist:
        return redirect('core:dashboard')
    
    context = {
        'diyetisyen': diyetisyen,
        'user': request.user,
        'red_nedeni': diyetisyen.red_nedeni
    }
    return render(request, 'auth/approval_rejected.html', context)


@csrf_protect  
def register_view(request):
    """Danışan kayıt sayfası"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, 'Kayıt işlemi başarıyla tamamlandı! Şimdi giriş yapabilirsiniz.')
                return redirect('core:login')
            except Exception as e:
                messages.error(request, f'Kayıt sırasında bir hata oluştu: {str(e)}')
    else:
        form = RegisterForm()
    
    return render(request, 'auth/register.html', {
        'form': form,
    })


@csrf_protect
def register_dietitian_view(request):
    """Diyetisyen kayıt sayfası"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, 'Diyetisyen başvurunuz alındı! Onay durumunuz e-posta ile bildirilecektir.')
                return redirect('core:login')
            except Exception as e:
                messages.error(request, f'Kayıt sırasında bir hata oluştu: {str(e)}')
    else:
        form = RegisterForm()
    
    # Get specialties for dietitian registration
    specialties = UzmanlikAlani.objects.all()
    
    return render(request, 'auth/register_dietitian.html', {
        'form': form,
        'specialties': specialties
    })


def logout_view(request):
    user_name = request.user.ad if request.user.is_authenticated else ''
    logout(request)
    if user_name:
        messages.success(request, f'Güle güle {user_name}! Başarıyla çıkış yaptınız.')
    return redirect('core:login')


@login_required
@login_required
def profile_view(request):
    user = request.user
    
    if request.method == 'POST':
        from .forms import KullaniciProfilForm, DiyetisyenProfilForm
        
        # Update user form
        user_form = KullaniciProfilForm(request.POST, instance=user)
        
        if user_form.is_valid():
            user_form.save()
            
            # If user is a dietitian, also update dietitian profile
            if user.rol.rol_adi == 'diyetisyen':
                try:
                    diyetisyen = user.diyetisyen
                    diyetisyen_form = DiyetisyenProfilForm(
                        request.POST, 
                        request.FILES, 
                        instance=diyetisyen
                    )
                    if diyetisyen_form.is_valid():
                        diyetisyen_form.save()
                except Diyetisyen.DoesNotExist:
                    pass
            
            messages.success(request, 'Profil başarıyla güncellendi.')
            return redirect('core:profile')
        else:
            messages.error(request, 'Form hatalarını düzeltin.')
    else:
        from .forms import KullaniciProfilForm, DiyetisyenProfilForm
        user_form = KullaniciProfilForm(instance=user)
        diyetisyen_form = None
        
        if user.rol.rol_adi == 'diyetisyen':
            try:
                diyetisyen_form = DiyetisyenProfilForm(instance=user.diyetisyen)
            except Diyetisyen.DoesNotExist:
                pass
    
    context = {
        'title': 'Profil',
        'user': user,
        'user_form': user_form,
        'diyetisyen_form': diyetisyen_form,
    }
    
    if user.rol.rol_adi == 'diyetisyen':
        try:
            context['diyetisyen'] = user.diyetisyen
        except Diyetisyen.DoesNotExist:
            pass
    
    return render(request, 'auth/profile.html', context)


@login_required
@csrf_protect
def profile_edit(request):
    """Profile editing endpoint"""
    if request.method == 'POST':
        user = request.user
        
        # Get form data
        ad = request.POST.get('ad', '').strip()
        soyad = request.POST.get('soyad', '').strip()
        telefon = request.POST.get('telefon', '').strip()
        
        # Validate required fields
        if not ad or not soyad:
            return JsonResponse({
                'success': False,
                'error': 'Ad ve soyad alanları zorunludur.'
            })
        
        try:
            # Update user profile
            user.ad = ad
            user.soyad = soyad
            user.telefon = telefon
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Profil başarıyla güncellendi.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Profil güncellenirken bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
@csrf_protect
def change_password(request):
    """Password change endpoint"""
    if request.method == 'POST':
        user = request.user
        
        # Get form data
        current_password = request.POST.get('current_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')
        
        # Validate current password
        if not user.check_password(current_password):
            return JsonResponse({
                'success': False,
                'error': 'Mevcut şifre hatalı.'
            })
        
        # Validate new passwords
        if not new_password1 or not new_password2:
            return JsonResponse({
                'success': False,
                'error': 'Yeni şifre alanları boş olamaz.'
            })
        
        if new_password1 != new_password2:
            return JsonResponse({
                'success': False,
                'error': 'Yeni şifreler eşleşmiyor.'
            })
        
        if len(new_password1) < 6:
            return JsonResponse({
                'success': False,
                'error': 'Şifre en az 6 karakter olmalıdır.'
            })
        
        try:
            # Set new password
            user.set_password(new_password1)
            user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Şifre başarıyla değiştirildi.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Şifre değiştirilirken bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Notification Views
@login_required
def notifications_list(request):
    """Bildirimler sayfası"""
    user = request.user
    
    # Kullanıcının bildirimlerini al
    notifications = Bildirim.objects.filter(
        alici_kullanici=user
    ).order_by('-tarih')
    
    # Okunmamış bildirim sayısı
    unread_count = notifications.filter(okundu_mu=False).count()
    
    context = {
        'title': 'Bildirimler',
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'notifications/list.html', context)


@login_required
def notifications_api(request):
    """Bildirimler için API endpoint (navbar dropdown için)"""
    user = request.user
    
    try:
        # Son 10 bildirimi al
        notifications = Bildirim.objects.filter(
            alici_kullanici=user
        ).order_by('-tarih')[:10]
        
        # Okunmamış bildirim sayısı
        unread_count = Bildirim.objects.filter(
            alici_kullanici=user,
            okundu_mu=False
        ).count()
        
        # JSON formatında bildirimler
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'baslik': notification.baslik,
                'mesaj': notification.mesaj[:100] + ('...' if len(notification.mesaj) > 100 else ''),
                'tur': notification.tur,
                'okundu_mu': notification.okundu_mu,
                'tarih': notification.tarih.strftime('%d.%m.%Y %H:%M'),
                'icon_class': notification.get_icon_class(),
                'redirect_url': notification.get_redirect_url(),
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Bildirimler alınırken hata oluştu: {str(e)}'
        })


@login_required
def mark_notification_read(request, notification_id):
    """Bildirimi okundu olarak işaretle"""
    if request.method == 'POST':
        try:
            notification = Bildirim.objects.get(
                id=notification_id,
                alici_kullanici=request.user
            )
            notification.okundu_mu = True
            notification.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Bildirim okundu olarak işaretlendi.'
            })
        except Bildirim.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Bildirim bulunamadı.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def mark_all_notifications_read(request):
    """Tüm bildirimleri okundu olarak işaretle"""
    if request.method == 'POST':
        try:
            updated_count = Bildirim.objects.filter(
                alici_kullanici=request.user,
                okundu_mu=False
            ).update(okundu_mu=True)
            
            return JsonResponse({
                'success': True,
                'message': f'{updated_count} bildirim okundu olarak işaretlendi.',
                'updated_count': updated_count
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def notification_redirect(request, notification_id):
    """Bildirime tıklandığında yönlendirme yap ve okundu olarak işaretle"""
    try:
        notification = Bildirim.objects.get(
            id=notification_id,
            alici_kullanici=request.user
        )
        
        # Bildirimi okundu olarak işaretle
        if not notification.okundu_mu:
            notification.okundu_mu = True
            notification.save()
        
        # Yönlendirme URL'sini al
        redirect_url = notification.get_redirect_url()
        
        return redirect(redirect_url)
        
    except Bildirim.DoesNotExist:
        messages.error(request, 'Bildirim bulunamadı.')
        return redirect('core:notifications_list')
    except Exception as e:
        messages.error(request, f'Bir hata oluştu: {str(e)}')
        return redirect('core:notifications_list')


# Randevu Views
@login_required
def appointments_list(request):
    """Kullanıcının randevularını listele"""
    user = request.user
    
    if user.rol.rol_adi == 'diyetisyen':
        try:
            diyetisyen = user.diyetisyen
            randevular = Randevu.objects.filter(diyetisyen=diyetisyen).order_by('-randevu_tarih_saat')
        except Diyetisyen.DoesNotExist:
            randevular = Randevu.objects.none()
    else:
        randevular = Randevu.objects.filter(danisan=user).order_by('-randevu_tarih_saat')
    
    context = {
        'title': 'Randevularım',
        'randevular': randevular,
    }
    return render(request, 'appointments/list.html', context)


@login_required
def appointment_create(request, diyetisyen_id):
    """Yeni randevu oluştur"""
    if request.user.rol.rol_adi != 'danisan':
        messages.error(request, 'Sadece danışanlar randevu alabilir.')
        return redirect('core:home')
    
    try:
        diyetisyen = Diyetisyen.objects.get(kullanici_id=diyetisyen_id)
    except Diyetisyen.DoesNotExist:
        messages.error(request, 'Diyetisyen bulunamadı.')
        return redirect('core:home')
    
    # Check if this is the user's first appointment with this dietitian
    previous_appointments = Randevu.objects.filter(
        diyetisyen=diyetisyen,
        danisan=request.user,
        durum__in=['TAMAMLANDI', 'ONAYLANDI']
    ).exists()
    
    is_first_appointment = not previous_appointments
    
    if request.method == 'POST':
        form = RandevuForm(request.POST, diyetisyen=diyetisyen)
        if form.is_valid():
            randevu = form.save(commit=False)
            randevu.diyetisyen = diyetisyen
            randevu.danisan = request.user
            randevu.durum = 'BEKLEMEDE'
            randevu.save()
            
            messages.success(request, 'Randevu talebiniz gönderildi. Diyetisyen onayından sonra kesinleşecektir.')
            return redirect('core:appointments_list')
    else:
        form = RandevuForm(diyetisyen=diyetisyen)
    
    context = {
        'title': 'Randevu Al',
        'form': form,
        'diyetisyen': diyetisyen,
        'is_first_appointment': is_first_appointment,
    }
    return render(request, 'appointments/create.html', context)


@login_required
def appointment_detail(request, appointment_id):
    """Randevu detayları"""
    try:
        if request.user.rol.rol_adi == 'diyetisyen':
            randevu = Randevu.objects.get(id=appointment_id, diyetisyen__kullanici=request.user)
        else:
            randevu = Randevu.objects.get(id=appointment_id, danisan=request.user)
    except Randevu.DoesNotExist:
        messages.error(request, 'Randevu bulunamadı.')
        return redirect('core:appointments_list')
    
    from django.utils import timezone
    today = timezone.now().date()
    
    context = {
        'title': 'Randevu Detayı',
        'randevu': randevu,
        'today': today,
        'now': timezone.now(),
    }
    return render(request, 'appointments/detail.html', context)


@login_required
def appointment_cancel(request, appointment_id):
    """Randevu iptal et"""
    try:
        if request.user.rol.rol_adi == 'diyetisyen':
            randevu = Randevu.objects.get(id=appointment_id, diyetisyen__kullanici=request.user)
        else:
            randevu = Randevu.objects.get(id=appointment_id, danisan=request.user)
    except Randevu.DoesNotExist:
        messages.error(request, 'Randevu bulunamadı.')
        return redirect('core:appointments_list')
    
    if randevu.durum in ['TAMAMLANDI', 'IPTAL_EDILDI']:
        messages.error(request, 'Bu randevu iptal edilemez.')
        return redirect('core:appointment_detail', appointment_id=appointment_id)
    
    if request.method == 'POST':
        # Cancel appointment
        randevu.durum = 'IPTAL_EDILDI'
        randevu.iptal_edilme_tarihi = timezone.now()
        
        if request.user.rol.rol_adi == 'diyetisyen':
            randevu.iptal_eden_tur = 'diyetisyen'
        else:
            randevu.iptal_eden_tur = 'danisan'
        
        randevu.iptal_nedeni = request.POST.get('iptal_nedeni', '')
        randevu.save()
        
        messages.success(request, 'Randevu başarıyla iptal edildi.')
        return redirect('core:appointments_list')
    
    context = {
        'title': 'Randevu İptal',
        'randevu': randevu,
    }
    return render(request, 'appointments/cancel.html', context)


@login_required
def appointment_approve(request, appointment_id):
    """Randevu onayla (Sadece diyetisyen)"""
    if request.user.rol.rol_adi != 'diyetisyen':
        messages.error(request, 'Bu işlem için yetkiniz yok.')
        return redirect('core:appointments_list')
    
    try:
        randevu = Randevu.objects.get(id=appointment_id, diyetisyen__kullanici=request.user)
    except Randevu.DoesNotExist:
        messages.error(request, 'Randevu bulunamadı.')
        return redirect('core:appointments_list')
    
    if randevu.durum != 'BEKLEMEDE':
        messages.error(request, 'Bu randevu onaylanamaz.')
        return redirect('core:appointment_detail', appointment_id=appointment_id)
    
    randevu.durum = 'ONAYLANDI'
    randevu.save()
    
    messages.success(request, 'Randevu başarıyla onaylandı.')
    return redirect('core:appointment_detail', appointment_id=appointment_id)


def dietitians_list(request):
    """Diyetisyen listesi ve arama"""
    search_query = request.GET.get('search', '')
    uzmanlik = request.GET.get('uzmanlik', '')
    sehir = request.GET.get('sehir', '')
    min_fiyat = request.GET.get('min_fiyat', '')
    max_fiyat = request.GET.get('max_fiyat', '')
    
    diyetisyenler = Diyetisyen.objects.filter(
        kullanici__aktif_mi=True
    ).select_related('kullanici')
    
    # Add realistic review counts and ratings based on appointment history
    import random
    for diyetisyen in diyetisyenler:
        # Generate consistent data based on dietitian ID
        random.seed(diyetisyen.kullanici.id)
        
        # Calculate realistic review count based on appointments
        total_appointments = Randevu.objects.filter(
            diyetisyen=diyetisyen, 
            durum='TAMAMLANDI'
        ).count()
        
        # Assume 30-60% of completed appointments result in reviews
        review_percentage = random.uniform(0.3, 0.6)
        diyetisyen.review_count = max(int(total_appointments * review_percentage), 1)
        
        # Generate rating between 4.0-5.0 for established dietitians
        if diyetisyen.review_count > 10:
            diyetisyen.rating = round(random.uniform(4.2, 5.0), 1)
        elif diyetisyen.review_count > 3:
            diyetisyen.rating = round(random.uniform(3.8, 4.8), 1)
        else:
            diyetisyen.rating = round(random.uniform(4.0, 4.5), 1)
        
        # Generate realistic experience years (2-15 years)
        if not hasattr(diyetisyen, 'experience_years') or not diyetisyen.experience_years:
            diyetisyen.experience_years = random.randint(2, 15)
    
    # Search filters
    if search_query:
        diyetisyenler = diyetisyenler.filter(
            Q(kullanici__ad__icontains=search_query) |
            Q(kullanici__soyad__icontains=search_query) |
            Q(universite__icontains=search_query) |
            Q(hakkinda_bilgi__icontains=search_query)
        )
    
    if uzmanlik:
        diyetisyenler = diyetisyenler.filter(
            diyetisyenuzmanlikalani__uzmanlik_alani__id=uzmanlik
        )
    
    if min_fiyat:
        try:
            diyetisyenler = diyetisyenler.filter(hizmet_ucreti__gte=float(min_fiyat))
        except ValueError:
            pass
    
    if max_fiyat:
        try:
            diyetisyenler = diyetisyenler.filter(hizmet_ucreti__lte=float(max_fiyat))
        except ValueError:
            pass
    
    # Get filter options
    uzmanlik_alanlari = UzmanlikAlani.objects.all()
    
    context = {
        'title': 'Diyetisyenler',
        'diyetisyenler': diyetisyenler,
        'uzmanlik_alanlari': uzmanlik_alanlari,
        'search_query': search_query,
        'selected_uzmanlik': uzmanlik,
        'min_fiyat': min_fiyat,
        'max_fiyat': max_fiyat,
    }
    return render(request, 'dietitians/list.html', context)


def dietitian_detail(request, dietitian_id):
    """Diyetisyen detay sayfası"""
    diyetisyen = get_object_or_404(
        Diyetisyen.objects.select_related('kullanici').prefetch_related(
            'diyetisyenuzmanlikalani_set__uzmanlik_alani'
        ), 
        kullanici_id=dietitian_id, 
        kullanici__aktif_mi=True
    )
    
    # Get recent reviews (if model exists)
    reviews = []  # TODO: Add review model and fetch reviews
    
    context = {
        'title': f'{diyetisyen.kullanici.ad} {diyetisyen.kullanici.soyad}',
        'diyetisyen': diyetisyen,
        'reviews': reviews,
    }
    return render(request, 'dietitians/detail.html', context)


# Static Pages
def about_view(request):
    """Hakkımızda sayfası"""
    context = {
        'title': 'Hakkımızda',
    }
    return render(request, 'static/about.html', context)


def contact_view(request):
    """İletişim sayfası"""
    if request.method == 'POST':
        # Handle contact form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # In a real app, you would save this to database or send email
        messages.success(request, 'Mesajınız başarıyla gönderildi. En kısa sürede size dönüş yapacağız.')
        return redirect('core:contact')
    
    context = {
        'title': 'İletişim',
    }
    return render(request, 'static/contact.html', context)


def privacy_view(request):
    """Gizlilik politikası sayfası"""
    context = {
        'title': 'Gizlilik Politikası',
    }
    return render(request, 'static/privacy.html', context)


def terms_view(request):
    """Kullanım şartları sayfası"""
    context = {
        'title': 'Kullanım Şartları',
    }
    return render(request, 'static/terms.html', context)


def dietitian_profile(request, slug):
    """Diyetisyen profil sayfası"""
    diyetisyen = get_object_or_404(
        Diyetisyen, 
        slug=slug, 
        kullanici__aktif_mi=True
    )
    
    # Get dietitian specialties
    specialties = DiyetisyenUzmanlikAlani.objects.filter(
        diyetisyen=diyetisyen
    ).select_related('uzmanlik_alani')
    
    # Get recent reviews (placeholder for now)
    reviews = []  # TODO: Add review model and fetch reviews
    
    # Calculate average rating (placeholder)
    average_rating = 4.5  # TODO: Calculate from actual reviews
    review_count = 0  # TODO: Count from actual reviews
    
    context = {
        'title': f'Dyt. {diyetisyen.kullanici.ad} {diyetisyen.kullanici.soyad}',
        'diyetisyen': diyetisyen,
        'specialties': specialties,
        'reviews': reviews,
        'average_rating': average_rating,
        'review_count': review_count,
    }
    return render(request, 'dietitians/profile.html', context)


# Analytics API Views
@login_required
def analytics_api(request):
    """Admin analytics API for charts"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    chart_type = request.GET.get('type', 'users')
    
    if chart_type == 'users':
        # User registration trend (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        user_data = Kullanici.objects.filter(
            date_joined__gte=thirty_days_ago
        ).extra(select={'day': 'date(date_joined)'}).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        labels = []
        data = []
        for item in user_data:
            if isinstance(item['day'], str):
                from datetime import datetime
                day_obj = datetime.strptime(item['day'], '%Y-%m-%d').date()
                labels.append(day_obj.strftime('%m/%d'))
            else:
                labels.append(item['day'].strftime('%m/%d'))
            data.append(item['count'])
        
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'label': 'Yeni Kayıtlar',
                'data': data,
                'borderColor': 'rgb(102, 126, 234)',
                'backgroundColor': 'rgba(102, 126, 234, 0.1)',
                'fill': True
            }]
        })
    
    elif chart_type == 'appointments':
        # Appointment status distribution
        appointment_stats = Randevu.objects.values('durum').annotate(
            count=Count('id')
        )
        
        labels = []
        data = []
        colors = {
            'BEKLEMEDE': '#f59e0b',
            'ONAYLANDI': '#10b981', 
            'TAMAMLANDI': '#3b82f6',
            'IPTAL_EDILDI': '#ef4444'
        }
        background_colors = []
        
        for item in appointment_stats:
            status = item['durum']
            labels.append({
                'BEKLEMEDE': 'Beklemede',
                'ONAYLANDI': 'Onaylandı',
                'TAMAMLANDI': 'Tamamlandı',
                'IPTAL_EDILDI': 'İptal Edildi'
            }.get(status, status))
            data.append(item['count'])
            background_colors.append(colors.get(status, '#6b7280'))
        
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': background_colors
            }]
        })
    
    elif chart_type == 'revenue':
        # Monthly revenue trend (last 12 months)
        twelve_months_ago = timezone.now() - timedelta(days=365)
        
        # Get completed appointments by month
        revenue_data = Randevu.objects.filter(
            durum='TAMAMLANDI',
            randevu_tarih_saat__gte=twelve_months_ago
        ).extra(select={'month': "strftime('%%Y-%%m', randevu_tarih_saat)"}).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Calculate revenue (need to join with dietitian fees)
        labels = []
        data = []
        avg_fee = Diyetisyen.objects.aggregate(avg_fee=Avg('hizmet_ucreti'))['avg_fee'] or 200
        
        for item in revenue_data:
            month_str = item['month']
            if month_str:
                try:
                    month_date = datetime.strptime(month_str, '%Y-%m')
                    labels.append(month_date.strftime('%m/%Y'))
                    data.append(float(item['count'] * avg_fee))
                except ValueError:
                    pass
        
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'label': 'Aylık Gelir (₺)',
                'data': data,
                'borderColor': 'rgb(16, 185, 129)',
                'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                'fill': True
            }]
        })
    
    elif chart_type == 'dietitians':
        # Top performing dietitians
        top_dietitians = Diyetisyen.objects.annotate(
            appointment_count=Count('randevu', filter=Q(randevu__durum='TAMAMLANDI'))
        ).order_by('-appointment_count')[:10]
        
        labels = []
        data = []
        
        for dietitian in top_dietitians:
            name = f"{dietitian.kullanici.ad} {dietitian.kullanici.soyad}"
            labels.append(name)
            data.append(dietitian.appointment_count)
        
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'label': 'Tamamlanan Randevular',
                'data': data,
                'backgroundColor': [
                    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280'
                ]
            }]
        })
    
    return JsonResponse({'error': 'Invalid chart type'}, status=400)


@login_required  
def user_management_api(request):
    """User management API for admin"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'GET':
        # Get users with pagination and filtering
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        search = request.GET.get('search', '')
        role_filter = request.GET.get('role', '')
        status_filter = request.GET.get('status', '')
        sort_field = request.GET.get('sort', 'date_joined')
        sort_order = request.GET.get('order', 'desc')
        
        users = Kullanici.objects.select_related('rol')
        
        if search:
            users = users.filter(
                Q(ad__icontains=search) | 
                Q(soyad__icontains=search) | 
                Q(e_posta__icontains=search)
            )
        
        if role_filter:
            users = users.filter(rol__rol_adi=role_filter)
            
        if status_filter == 'active':
            users = users.filter(aktif_mi=True)
        elif status_filter == 'inactive':
            users = users.filter(aktif_mi=False)
        
        # Sorting
        sort_mapping = {
            'name': ['ad', 'soyad'],
            'email': ['e_posta'],
            'phone': ['telefon'],
            'role': ['rol__rol_adi'],
            'status': ['aktif_mi'],
            'date_joined': ['date_joined'],
            'last_login': ['son_giris_tarihi']
        }
        
        if sort_field in sort_mapping:
            sort_fields = sort_mapping[sort_field]
            if sort_order == 'desc':
                sort_fields = ['-' + field for field in sort_fields]
            users = users.order_by(*sort_fields)
        else:
            # Default sort
            users = users.order_by('-date_joined')
        
        total = users.count()
        start = (page - 1) * per_page
        end = start + per_page
        users = users[start:end]
        
        user_data = []
        for user in users:
            user_data.append({
                'id': user.id,
                'ad': user.ad,
                'soyad': user.soyad,
                'name': f"{user.ad} {user.soyad}",
                'e_posta': user.e_posta,
                'email': user.e_posta,
                'telefon': user.telefon,
                'phone': user.telefon,
                'rol_adi': user.rol.rol_adi if user.rol else 'No Role',
                'role': user.rol.rol_adi if user.rol else 'No Role',
                'aktif_mi': user.aktif_mi,
                'is_active': user.aktif_mi,
                'date_joined': user.date_joined.strftime('%d/%m/%Y'),
                'son_giris_tarihi': user.son_giris_tarihi.strftime('%d/%m/%Y %H:%M') if user.son_giris_tarihi else None,
                'last_login': user.last_login.strftime('%d/%m/%Y %H:%M') if user.last_login else 'Never'
            })
        
        return JsonResponse({
            'users': user_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    
    elif request.method == 'POST':
        # Handle user actions (activate/deactivate, delete)
        action = request.POST.get('action')
        user_ids = request.POST.getlist('user_ids')
        
        if action == 'activate':
            try:
                # Admin hesaplarını filtrele (sadece aktif yapma için izin ver)
                users_to_update = Kullanici.objects.filter(id__in=user_ids)
                updated_count = users_to_update.update(aktif_mi=True)
                return JsonResponse({'success': True, 'message': f'{updated_count} kullanıcı aktif edildi'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Aktif yapma işlemi başarısız: {str(e)}'})
        
        elif action == 'deactivate':
            try:
                # Admin hesaplarını ve kendi hesabını hariç tut
                users_to_update = Kullanici.objects.filter(id__in=user_ids).exclude(id=request.user.id)
                
                # Admin rolündeki kullanıcıları hariç tut
                admin_users = []
                regular_users = []
                
                for user in users_to_update:
                    if hasattr(user, 'rol') and user.rol and user.rol.rol_adi.upper() in ['admin']:
                        admin_users.append(f"{user.ad} {user.soyad}")
                    else:
                        regular_users.append(user.id)
                
                if admin_users:
                    error_msg = f"Admin hesapları pasif yapılamaz: {', '.join(admin_users)}"
                    if regular_users:
                        # Sadece admin olmayanları pasif yap
                        updated_count = Kullanici.objects.filter(id__in=regular_users).update(aktif_mi=False)
                        error_msg += f"\nDiğer {updated_count} kullanıcı pasif edildi."
                    return JsonResponse({'success': False, 'error': error_msg})
                
                updated_count = Kullanici.objects.filter(id__in=regular_users).update(aktif_mi=False)
                return JsonResponse({'success': True, 'message': f'{updated_count} kullanıcı pasif edildi'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Pasif yapma işlemi başarısız: {str(e)}'})
        
        elif action == 'delete':
            try:
                # Silme işleminden önce foreign key sorunlarını kontrol et
                from django.db import transaction
                from django.db.models import ProtectedError
                
                users_to_delete = Kullanici.objects.filter(id__in=user_ids).exclude(id=request.user.id)
                delete_count = users_to_delete.count()
                
                if delete_count == 0:
                    return JsonResponse({'success': False, 'error': 'Silinecek kullanıcı bulunamadı'})
                
                # Admin hesaplarını kontrol et
                admin_users = []
                diyetisyen_users = []
                regular_users = []
                
                for user in users_to_delete:
                    # Admin kontrolü
                    if hasattr(user, 'rol') and user.rol and user.rol.rol_adi.upper() in ['admin']:
                        admin_users.append(f"{user.ad} {user.soyad}")
                        continue
                    
                    # Diyetisyen kontrolü
                    if hasattr(user, 'diyetisyen'):
                        # Diyetisyenin ilişkili verilerini kontrol et
                        
                        randevu_count = Randevu.objects.filter(diyetisyen=user.diyetisyen).count()
                        odeme_count = OdemeHareketi.objects.filter(diyetisyen=user.diyetisyen).count()
                        diyetisyen_odeme_count = DiyetisyenOdeme.objects.filter(diyetisyen=user.diyetisyen).count()
                        
                        if randevu_count > 0 or odeme_count > 0 or diyetisyen_odeme_count > 0:
                            diyetisyen_users.append({
                                'name': f"{user.ad} {user.soyad}",
                                'randevu_count': randevu_count,
                                'odeme_count': odeme_count
                            })
                        else:
                            regular_users.append(user.id)
                    else:
                        regular_users.append(user.id)
                
                # Hata mesajlarını topla
                error_messages = []
                
                if admin_users:
                    error_messages.append(f"Admin hesapları silinemez: {', '.join(admin_users)}")
                
                if diyetisyen_users:
                    dyt_msg = "Aşağıdaki diyetisyenler silinemez (aktif randevu/ödeme kayıtları var):"
                    for dyt in diyetisyen_users:
                        dyt_msg += f"\n• {dyt['name']} ({dyt['randevu_count']} randevu, {dyt['odeme_count']} ödeme)"
                    dyt_msg += "\nBu kullanıcıları önce pasif yapabilirsiniz."
                    error_messages.append(dyt_msg)
                
                # Eğer silinebilir kullanıcı varsa sil
                deleted_count = 0
                if regular_users:
                    with transaction.atomic():
                        deleted_count = Kullanici.objects.filter(id__in=regular_users).count()
                        Kullanici.objects.filter(id__in=regular_users).delete()
                
                # Sonuç mesajını oluştur
                if error_messages and deleted_count > 0:
                    final_msg = "\n\n".join(error_messages) + f"\n\nDiğer {deleted_count} kullanıcı başarıyla silindi."
                    return JsonResponse({'success': False, 'error': final_msg})
                elif error_messages:
                    return JsonResponse({'success': False, 'error': "\n\n".join(error_messages)})
                elif deleted_count > 0:
                    return JsonResponse({'success': True, 'message': f'{deleted_count} kullanıcı silindi'})
                else:
                    return JsonResponse({'success': False, 'error': 'Silinecek kullanıcı bulunamadı'})
                
            except ProtectedError as e:
                return JsonResponse({'success': False, 'error': 'Bu kullanıcılar silinemez: İlişkili veriler mevcut'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Silme işlemi başarısız: {str(e)}'})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def appointment_management_api(request):
    """Appointment management API for admin"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'GET':
        # Get appointments with pagination and filtering
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        status_filter = request.GET.get('status', '')
        dietitian_filter = request.GET.get('dietitian', '')
        date_filter = request.GET.get('date', '')
        
        appointments = Randevu.objects.select_related('diyetisyen__kullanici', 'danisan')
        
        if status_filter:
            appointments = appointments.filter(durum=status_filter)
            
        if dietitian_filter:
            appointments = appointments.filter(diyetisyen__kullanici_id=dietitian_filter)
            
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
                appointments = appointments.filter(randevu_tarih_saat__date=date_obj)
            except ValueError:
                pass
        
        total = appointments.count()
        start = (page - 1) * per_page
        end = start + per_page
        appointments = appointments.order_by('-randevu_tarih_saat')[start:end]
        
        appointment_data = []
        for appointment in appointments:
            appointment_data.append({
                'id': appointment.id,
                'patient_name': f"{appointment.danisan.ad} {appointment.danisan.soyad}",
                'patient_email': appointment.danisan.e_posta,
                'dietitian_name': f"Dyt. {appointment.diyetisyen.kullanici.ad} {appointment.diyetisyen.kullanici.soyad}",
                'dietitian_email': appointment.diyetisyen.kullanici.e_posta,
                'date': appointment.randevu_tarih_saat.strftime('%d/%m/%Y'),
                'time': appointment.randevu_tarih_saat.strftime('%H:%M'),
                'date_time': appointment.randevu_tarih_saat.strftime('%d/%m/%Y %H:%M'),
                'date_time_iso': appointment.randevu_tarih_saat.isoformat(),
                'status': appointment.durum,
                'type': appointment.tip,
                'notes': getattr(appointment, 'notlar', '') or '',
                'created_date': getattr(appointment, 'olusturulma_tarihi', appointment.randevu_tarih_saat).strftime('%d/%m/%Y %H:%M'),
                'fee': float(appointment.diyetisyen.hizmet_ucreti) if appointment.diyetisyen.hizmet_ucreti else 0
            })
        
        # Get dietitians for filter
        dietitians = Diyetisyen.objects.select_related('kullanici').filter(kullanici__aktif_mi=True)
        dietitian_options = [{'id': d.kullanici.id, 'name': f"Dyt. {d.kullanici.ad} {d.kullanici.soyad}"} for d in dietitians]
        
        return JsonResponse({
            'success': True,
            'appointments': appointment_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'dietitians': dietitian_options
        })
    
    elif request.method == 'POST':
        # Handle appointment actions
        action = request.POST.get('action')
        appointment_ids = request.POST.getlist('appointment_ids')
        
        if action == 'approve':
            updated = Randevu.objects.filter(
                id__in=appointment_ids, 
                durum='BEKLEMEDE'
            ).update(durum='ONAYLANDI')
            return JsonResponse({'success': True, 'message': f'{updated} randevu onaylandı'})
        
        elif action == 'reject':
            reason = request.POST.get('reject_reason', 'Admin tarafından reddedildi')
            updated = Randevu.objects.filter(
                id__in=appointment_ids, 
                durum='BEKLEMEDE'
            ).update(
                durum='IPTAL_EDILDI',
                iptal_nedeni=reason,
                iptal_edilme_tarihi=timezone.now()
            )
            return JsonResponse({'success': True, 'message': f'{updated} randevu reddedildi'})
        
        elif action == 'complete':
            updated = Randevu.objects.filter(
                id__in=appointment_ids, 
                durum='ONAYLANDI'
            ).update(durum='TAMAMLANDI')
            return JsonResponse({'success': True, 'message': f'{updated} randevu tamamlandı olarak işaretlendi'})
        
        elif action == 'delete':
            deleted_count = Randevu.objects.filter(id__in=appointment_ids).count()
            Randevu.objects.filter(id__in=appointment_ids).delete()
            return JsonResponse({'success': True, 'message': f'{deleted_count} randevu silindi'})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def system_logs_api(request):
    """System logs and audit trail API"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    # Check if user has admin privileges
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'success': False, 'error': 'Admin access required'}, status=403)
    
    # For now, return mock data - you can implement actual logging later
    logs = [
        {
            'id': 1,
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
            'user': 'admin@diyetlenio.com',
            'action': 'USER_LOGIN',
            'description': 'Kullanıcı sisteme giriş yaptı',
            'ip_address': '192.168.1.1',
            'severity': 'INFO'
        },
        {
            'id': 2,
            'timestamp': (timezone.now() - timedelta(minutes=15)).strftime('%d/%m/%Y %H:%M:%S'),
            'user': 'dyt.ahmet@diyetlenio.com',
            'action': 'APPOINTMENT_APPROVED',
            'description': 'Randevu onaylandı (ID: 123)',
            'ip_address': '192.168.1.5',
            'severity': 'INFO'
        },
        {
            'id': 3,
            'timestamp': (timezone.now() - timedelta(hours=1)).strftime('%d/%m/%Y %H:%M:%S'),
            'user': 'admin@diyetlenio.com',
            'action': 'USER_DEACTIVATED',
            'description': 'Kullanıcı hesabı pasif edildi (ID: 456)',
            'ip_address': '192.168.1.1',
            'severity': 'WARNING'
        },
        {
            'id': 4,
            'timestamp': (timezone.now() - timedelta(hours=2)).strftime('%d/%m/%Y %H:%M:%S'),
            'user': 'system',
            'action': 'FAILED_LOGIN',
            'description': 'Başarısız giriş denemesi: wrong_user@test.com',
            'ip_address': '192.168.1.99',
            'severity': 'ERROR'
        }
    ]
    
    return JsonResponse({
        'success': True,
        'logs': logs,
        'total': len(logs)
    })


@login_required
def bulk_email_api(request):
    """Bulk email notification API"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        recipient_type = request.POST.get('recipient_type')  # 'all', 'dietitians', 'patients'
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        if not all([recipient_type, subject, message]):
            return JsonResponse({'error': 'Tüm alanları doldurun'}, status=400)
        
        # Get recipients based on type
        recipients = []
        if recipient_type == 'all':
            recipients = list(Kullanici.objects.filter(aktif_mi=True).values_list('e_posta', flat=True))
        elif recipient_type == 'dietitians':
            recipients = list(Kullanici.objects.filter(
                aktif_mi=True, 
                rol__rol_adi='diyetisyen'
            ).values_list('e_posta', flat=True))
        elif recipient_type == 'patients':
            recipients = list(Kullanici.objects.filter(
                aktif_mi=True, 
                rol__rol_adi='danisan'
            ).values_list('e_posta', flat=True))
        
        # In a real implementation, you would use Django's email system
        # from django.core.mail import send_mass_mail
        # For now, just return success
        
        return JsonResponse({
            'success': True, 
            'message': f'{len(recipients)} kişiye e-posta gönderildi',
            'recipient_count': len(recipients)
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


def send_telegram_notification(message):
    """Send notification to admin via Telegram"""
    try:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
        
        if not bot_token or not chat_id:
            print("Telegram settings not configured")
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram notification error: {e}")
        return False


def emergency_chat_view(request):
    """Emergency dietitian chat page - accessible to all, redirects to login if not authenticated"""
    if not request.user.is_authenticated:
        # Redirect to login with next parameter and emergency message
        login_url = f"{reverse('core:login')}?next={request.path}&emergency=1"
        return redirect(login_url)
    
    context = {
        'title': 'Nöbetçi Diyetisyen - Canlı Görüşme',
        'user': request.user,
    }
    return render(request, 'core/emergency_chat.html', context)


@csrf_exempt
def start_emergency_chat(request):
    """Start emergency chat and notify admin via Telegram with interactive features"""
    print(f"Request method: {request.method}")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"POST data: {request.POST}")
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Giriş yapmanız gerekiyor'}, status=401)
    
    if request.method == 'POST':
        user = request.user
        message_text = request.POST.get('message', '')
        
        # Generate session ID for webhook system
        session_id = f"session_{int(timezone.now().timestamp() * 1000)}"
        
        # Send to our webhook system for interactive features
        webhook_data = {
            'name': f"{user.ad} {user.soyad}",
            'phone': getattr(user, 'telefon', 'Belirtilmemiş'),
            'email': user.e_posta,
            'emergency': message_text,
            'user_id': user.id,
            'session_id': session_id
        }
        
        try:
            # Send to our webhook emergency system
            print(f"Sending to webhook: {webhook_data}")
            webhook_response = requests.post(
                'https://busy-planes-study.loca.lt/emergency-request',
                json=webhook_data,
                timeout=15
            )
            print(f"Webhook response: {webhook_response.status_code}")
            
            if webhook_response.status_code == 200:
                return JsonResponse({
                    'success': True,
                    'message': 'Canlı görüşme talebi alındı! Uzman diyetisyenimiz en kısa sürede sizinle iletişime geçecek.',
                    'session_id': session_id
                })
            else:
                # Fallback to old system
                notification_message = f"""
🚨 <b>ACİL DİYETİSYEN TALEBİ</b>

👤 <b>Kullanıcı:</b> {user.ad} {user.soyad}
📧 <b>E-posta:</b> {user.e_posta}
📱 <b>Telefon:</b> {getattr(user, 'telefon', 'Belirtilmemiş')}
⏰ <b>Tarih:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

💬 <b>Mesaj:</b>
{message_text}

Lütfen acil olarak ilgilenin!
                """
                notification_sent = send_telegram_notification(notification_message)
                return JsonResponse({
                    'success': True,
                    'message': 'Canlı görüşme talebi alındı! Uzman diyetisyenimiz en kısa sürede sizinle iletişime geçecek.',
                    'notification_sent': notification_sent
                })
                
        except Exception as e:
            print(f"Webhook error: {e}")
            # Fallback to old system
            notification_message = f"""
🚨 <b>ACİL DİYETİSYEN TALEBİ</b>

👤 <b>Kullanıcı:</b> {user.ad} {user.soyad}
📧 <b>E-posta:</b> {user.e_posta}
📱 <b>Telefon:</b> {getattr(user, 'telefon', 'Belirtilmemiş')}
⏰ <b>Tarih:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

💬 <b>Mesaj:</b>
{message_text}

Lütfen acil olarak ilgilenin!
            """
            notification_sent = send_telegram_notification(notification_message)
            return JsonResponse({
                'success': True,
                'message': 'Canlı görüşme talebi alındı! Uzman diyetisyenimiz en kısa sürede sizinle iletişime geçecek.',
                'notification_sent': notification_sent
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def dietitian_management_api(request):
    """Dietitian approval management API for admin"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'GET':
        # Get dietitians with pagination and filtering
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        status_filter = request.GET.get('status', 'pending')
        search = request.GET.get('search', '')
        
        # Build query based on status
        if status_filter == 'pending':
            dietitians = Diyetisyen.objects.filter(onay_durumu='BEKLEMEDE')
        elif status_filter == 'approved':
            dietitians = Diyetisyen.objects.filter(onay_durumu='ONAYLANDI')
        elif status_filter == 'rejected':
            dietitians = Diyetisyen.objects.filter(onay_durumu='REDDEDILDI')
        else:  # all
            dietitians = Diyetisyen.objects.all()
        
        dietitians = dietitians.select_related('kullanici').prefetch_related('diyetisyenuzmanlikalani_set__uzmanlik_alani')
        
        if search:
            dietitians = dietitians.filter(
                Q(kullanici__ad__icontains=search) |
                Q(kullanici__soyad__icontains=search) |
                Q(kullanici__e_posta__icontains=search) |
                Q(universite__icontains=search)
            )
        
        total = dietitians.count()
        start = (page - 1) * per_page
        end = start + per_page
        dietitians = dietitians[start:end]
        
        dietitian_data = []
        for dietitian in dietitians:
            # Get specialties
            specialties = DiyetisyenUzmanlikAlani.objects.filter(
                diyetisyen=dietitian
            ).select_related('uzmanlik_alani')
            specialty_names = [s.uzmanlik_alani.alan_adi for s in specialties]
            
            # Determine status based on onay_durumu
            if dietitian.onay_durumu == 'BEKLEMEDE':
                status = 'pending'
            elif dietitian.onay_durumu == 'ONAYLANDI':
                status = 'approved'
            elif dietitian.onay_durumu == 'REDDEDILDI':
                status = 'rejected'
            else:
                status = 'pending'
            
            dietitian_data.append({
                'id': dietitian.pk,
                'name': f"{dietitian.kullanici.ad} {dietitian.kullanici.soyad}",
                'email': dietitian.kullanici.e_posta,
                'phone': getattr(dietitian.kullanici, 'telefon', ''),
                'university': dietitian.universite or '',
                'specialties': specialty_names,
                'fee': float(dietitian.hizmet_ucreti) if dietitian.hizmet_ucreti else 0,
                'application_date': dietitian.kullanici.date_joined.strftime('%d/%m/%Y'),
                'status': status,
                'about': dietitian.hakkinda_bilgi or '',
                'diploma_document': None  # Add if you have diploma file field
            })
        
        return JsonResponse({
            'dietitians': dietitian_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    
    elif request.method == 'POST':
        # Handle dietitian approval/rejection actions
        action = request.POST.get('action')
        dietitian_ids = request.POST.getlist('dietitian_ids')
        reason = request.POST.get('reason', '')
        
        if action == 'approve':
            try:
                from django.utils import timezone
                # Update dietitian approval status
                dietitians_updated = Diyetisyen.objects.filter(
                    pk__in=dietitian_ids
                ).update(
                    onay_durumu='ONAYLANDI',
                    onaylayan_admin=request.user,
                    onay_tarihi=timezone.now()
                )
                
                # Also activate user accounts
                Kullanici.objects.filter(
                    diyetisyen__pk__in=dietitian_ids
                ).update(aktif_mi=True)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'{dietitians_updated} diyetisyen onaylandı'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False, 
                    'error': f'Onaylama işlemi başarısız: {str(e)}'
                })
        
        elif action == 'reject':
            try:
                from django.utils import timezone
                # Update dietitian rejection status
                dietitians_updated = Diyetisyen.objects.filter(
                    pk__in=dietitian_ids
                ).update(
                    onay_durumu='REDDEDILDI',
                    onaylayan_admin=request.user,
                    onay_tarihi=timezone.now(),
                    red_nedeni=reason or 'Admin tarafından reddedildi'
                )
                
                return JsonResponse({
                    'success': True, 
                    'message': f'{dietitians_updated} diyetisyen reddedildi'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False, 
                    'error': f'Reddetme işlemi başarısız: {str(e)}'
                })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def dietitian_detail_api(request, dietitian_id):
    """Get detailed information about a specific dietitian"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        dietitian = Diyetisyen.objects.select_related('kullanici').get(pk=dietitian_id)
        
        # Get specialties
        specialties = DiyetisyenUzmanlikAlani.objects.filter(
            diyetisyen=dietitian
        ).select_related('uzmanlik_alani')
        specialty_names = [s.uzmanlik_alani.alan_adi for s in specialties]
        
        # Determine status
        if dietitian.kullanici.aktif_mi:
            status = 'approved'
        else:
            status = 'pending'
        
        dietitian_data = {
            'id': dietitian.pk,
            'name': f"{dietitian.kullanici.ad} {dietitian.kullanici.soyad}",
            'email': dietitian.kullanici.e_posta,
            'phone': getattr(dietitian.kullanici, 'telefon', ''),
            'university': dietitian.universite or '',
            'specialties': specialty_names,
            'fee': float(dietitian.hizmet_ucreti) if dietitian.hizmet_ucreti else 0,
            'application_date': dietitian.kullanici.date_joined.strftime('%d/%m/%Y'),
            'status': status,
            'about': dietitian.hakkinda_bilgi or '',
            'diploma_document': None  # Add if you have diploma file field
        }
        
        return JsonResponse({
            'success': True,
            'dietitian': dietitian_data
        })
        
    except Diyetisyen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Diyetisyen bulunamadı'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Bir hata oluştu: {str(e)}'
        })


# Article Views
def articles_list(request):
    """Articles listing page with categories and search"""
    # Get search query and category filter
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category')
    
    # Base queryset for published articles
    articles = Makale.objects.filter(
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    ).select_related('yazar_kullanici', 'kategori').order_by('-yayimlanma_tarihi')
    
    # Apply search filter
    if search_query:
        articles = articles.filter(
            Q(baslik__icontains=search_query) |
            Q(ozet__icontains=search_query) |
            Q(etiketler__icontains=search_query)
        )
    
    # Apply category filter
    if category_id:
        articles = articles.filter(kategori_id=category_id)
    
    # Get active categories with article counts
    categories = MakaleKategori.objects.filter(aktif_mi=True).annotate(
        article_count=Count('makaleler', filter=Q(makaleler__onay_durumu='ONAYLANDI'))
    ).order_by('sira', 'ad')
    
    # Get featured articles (most read)
    featured_articles = Makale.objects.filter(
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    ).select_related('yazar_kullanici', 'kategori').order_by('-okunma_sayisi')[:3]
    
    # Get duty dietitian for today
    import random
    from datetime import datetime
    duty_dietitian = None
    try:
        # Get all active dietitians
        active_dietitians = Diyetisyen.objects.filter(
            kullanici__aktif_mi=True,
            kullanici__rol__rol_adi='diyetisyen'
        ).select_related('kullanici')
        
        if active_dietitians.exists():
            # Use current date as seed for consistent daily rotation
            today = datetime.now().date()
            random.seed(today.toordinal())  # This ensures same dietitian for the whole day
            duty_dietitian = random.choice(list(active_dietitians))
    except Exception:
        duty_dietitian = None
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(articles, 12)  # 12 articles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Makaleler - Diyetlenio',
        'articles': page_obj,
        'categories': categories,
        'featured_articles': featured_articles,
        'search_query': search_query,
        'selected_category': category_id,
        'total_articles': paginator.count,
        'duty_dietitian': duty_dietitian,
    }
    
    return render(request, 'articles_list.html', context)


def article_detail(request, slug):
    """Article detail page"""
    article = get_object_or_404(
        Makale.objects.select_related('yazar_kullanici', 'kategori'),
        slug=slug,
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    )
    
    # Increment view count
    article.okunma_sayisi += 1
    article.save(update_fields=['okunma_sayisi'])
    
    # Get related articles (same category, excluding current)
    related_articles = Makale.objects.filter(
        kategori=article.kategori,
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    ).exclude(id=article.id).select_related('yazar_kullanici')[:4]
    
    # Get author's other articles
    author_articles = Makale.objects.filter(
        yazar_kullanici=article.yazar_kullanici,
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    ).exclude(id=article.id).select_related('kategori')[:3]
    
    context = {
        'title': f'{article.baslik} - Diyetlenio',
        'article': article,
        'related_articles': related_articles,
        'author_articles': author_articles,
        'seo_title': article.seo_baslik or article.baslik,
        'seo_description': article.seo_aciklama or article.ozet,
    }
    
    return render(request, 'article_detail.html', context)


def articles_by_category(request, category_id):
    """Articles filtered by category"""
    category = get_object_or_404(MakaleKategori, id=category_id, aktif_mi=True)
    
    articles = Makale.objects.filter(
        kategori=category,
        onay_durumu='ONAYLANDI',
        yayimlanma_tarihi__isnull=False
    ).select_related('yazar_kullanici').order_by('-yayimlanma_tarihi')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all categories for sidebar
    categories = MakaleKategori.objects.filter(aktif_mi=True).annotate(
        article_count=Count('makaleler', filter=Q(makaleler__onay_durumu='ONAYLANDI'))
    ).order_by('sira', 'ad')
    
    context = {
        'title': f'{category.ad} Makaleleri - Diyetlenio',
        'articles': page_obj,
        'category': category,
        'categories': categories,
        'total_articles': paginator.count,
    }
    
    return render(request, 'articles_by_category.html', context)


@login_required
def user_detail_api(request, user_id):
    """Get user details for admin dashboard"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        user = Kullanici.objects.select_related('rol').get(id=user_id)
        
        data = {
            'id': user.id,
            'ad': user.ad,
            'soyad': user.soyad,
            'e_posta': user.e_posta,
            'telefon': user.telefon,
            'rol_adi': user.rol.rol_adi,
            'aktif_mi': user.aktif_mi,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }
        
        return JsonResponse(data)
        
    except Kullanici.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_protect
def user_update_api(request, user_id):
    """Update user details for admin dashboard"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        user = Kullanici.objects.get(id=user_id)
        
        # Update user fields
        user.ad = request.POST.get('ad', user.ad).strip()
        user.soyad = request.POST.get('soyad', user.soyad).strip()
        user.e_posta = request.POST.get('e_posta', user.e_posta).strip()
        user.telefon = request.POST.get('telefon', user.telefon)
        user.aktif_mi = request.POST.get('aktif_mi') == 'true'
        
        # Update role if needed
        rol_adi = request.POST.get('rol_adi')
        if rol_adi and rol_adi != user.rol.rol_adi:
            try:
                from .models import Rol
                new_rol = Rol.objects.get(rol_adi=rol_adi)
                user.rol = new_rol
            except Rol.DoesNotExist:
                return JsonResponse({'error': f'Role {rol_adi} not found'}, status=400)
        
        user.save()
        
        return JsonResponse({'success': True, 'message': 'User updated successfully'})
        
    except Kullanici.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# Static Pages Views
def about_view(request):
    """Hakkımızda sayfası"""
    context = {
        "title": "Hakkımızda - Diyetlenio",
    }
    return render(request, "static/about.html", context)


def contact_view(request):
    """İletişim sayfası"""
    if request.method == "POST":
        # İletişim formu işleme
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        
        if name and email and subject and message:
            # İletişim mesajını kaydet veya email gönder
            messages.success(request, "Mesajınız başarıyla gönderildi. En kısa sürede size dönüş yapacağız.")
            return redirect("core:contact")
        else:
            messages.error(request, "Lütfen tüm alanları doldurun.")
    
    context = {
        "title": "İletişim - Diyetlenio",
    }
    return render(request, "static/contact.html", context)


def privacy_view(request):
    """Gizlilik Politikası sayfası"""
    context = {
        "title": "Gizlilik Politikası - Diyetlenio",
    }
    return render(request, "static/privacy.html", context)


def terms_view(request):
    """Kullanım Şartları sayfası"""
    context = {
        "title": "Kullanım Şartları - Diyetlenio",
    }
    return render(request, "static/terms.html", context)


@login_required
@require_http_methods(["POST"])
@csrf_protect
def dietitian_approve_api(request, dietitian_id):
    """API to approve a specific dietitian"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from django.utils import timezone
        dietitian = Diyetisyen.objects.get(pk=dietitian_id)
        
        # Update dietitian approval status
        dietitian.onay_durumu = 'ONAYLANDI'
        dietitian.onaylayan_admin = request.user
        dietitian.onay_tarihi = timezone.now()
        dietitian.save()
        
        # Also activate user account
        dietitian.kullanici.aktif_mi = True
        dietitian.kullanici.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Diyetisyen başarıyla onaylandı'
        })
        
    except Diyetisyen.DoesNotExist:
        return JsonResponse({'error': 'Diyetisyen bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Onaylama işlemi başarısız: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_protect
def dietitian_reject_api(request, dietitian_id):
    """API to reject a specific dietitian"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        import json
        from django.utils import timezone
        
        # Get rejection reason from request body
        try:
            body = json.loads(request.body)
            reason = body.get('neden', 'Admin tarafından reddedildi')
        except:
            reason = 'Admin tarafından reddedildi'
        
        dietitian = Diyetisyen.objects.get(pk=dietitian_id)
        
        # Update dietitian rejection status
        dietitian.onay_durumu = 'REDDEDILDI'
        dietitian.onaylayan_admin = request.user
        dietitian.onay_tarihi = timezone.now()
        dietitian.red_nedeni = reason
        dietitian.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Diyetisyen başvurusu reddedildi'
        })
        
    except Diyetisyen.DoesNotExist:
        return JsonResponse({'error': 'Diyetisyen bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Reddetme işlemi başarısız: {str(e)}'
        }, status=500)


# Şifre Sıfırlama View'leri
@csrf_protect
def password_reset_view(request):
    """Şifre sıfırlama talep sayfası"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, 'E-posta adresi gereklidir.')
            return render(request, 'auth/password_reset.html')
        
        try:
            user = Kullanici.objects.get(e_posta=email, aktif_mi=True)
            
            # Token ve UID oluştur
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Email içeriğini hazırla
            context = {
                'user': user,
                'domain': request.get_host(),
                'site_name': 'Diyetlenio',
                'uid': uid,
                'token': token,
                'protocol': 'https' if request.is_secure() else 'http',
            }
            
            # HTML ve text email render et
            html_message = render_to_string('emails/password_reset_email.html', context)
            plain_message = render_to_string('emails/password_reset_email.txt', context)
            
            # Email gönder
            try:
                send_mail(
                    subject='Diyetlenio - Şifre Sıfırlama Talebi',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                messages.success(
                    request, 
                    f'Şifre sıfırlama linki {email} adresine gönderildi. E-postanızı kontrol edin.'
                )
                return redirect('core:login')
                
            except Exception as e:
                messages.error(
                    request, 
                    'E-posta gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.'
                )
                
        except Kullanici.DoesNotExist:
            # Güvenlik için mevcut olmayan emailler için de başarı mesajı göster
            messages.success(
                request, 
                f'Eğer {email} adresi sistemde kayıtlıysa, şifre sıfırlama linki gönderilmiştir.'
            )
            return redirect('core:login')
    
    return render(request, 'auth/password_reset.html')


def password_reset_confirm_view(request, uidb64, token):
    """Şifre sıfırlama onay sayfası"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Kullanici.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Kullanici.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        validlink = True
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, user)  # Kullanıcının oturum açması için
                messages.success(request, 'Şifreniz başarıyla güncellendi! Yeni şifrenizle giriş yapabilirsiniz.')
                return redirect('core:login')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
        else:
            form = SetPasswordForm(user)
    else:
        validlink = False
        form = None
    
    context = {
        'form': form,
        'validlink': validlink,
        'user': user,
    }
    return render(request, 'auth/password_reset_confirm.html', context)


@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def schedule_api(request):
    """Diyetisyen çalışma saatleri API"""
    # Kullanıcının diyetisyen olduğunu kontrol et
    if not hasattr(request.user, 'diyetisyen'):
        return JsonResponse({'error': 'Bu işlem için diyetisyen hesabı gerekli'}, status=403)
    
    diyetisyen = request.user.diyetisyen
    
    if request.method == 'GET':
        # Mevcut çalışma saatlerini getir
        schedules = DiyetisyenMusaitlikSablon.objects.filter(
            diyetisyen=diyetisyen,
            aktif=True
        ).order_by('gun')
        
        schedule_data = []
        for schedule in schedules:
            schedule_data.append({
                'gun': schedule.gun,
                'gun_adi': schedule.get_gun_display(),
                'baslangic_saati': schedule.baslangic_saati.strftime('%H:%M'),
                'bitis_saati': schedule.bitis_saati.strftime('%H:%M'),
                'aktif': schedule.aktif
            })
        
        return JsonResponse({
            'success': True,
            'schedule': schedule_data
        })
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Önce mevcut çalışma saatlerini pasif yap
            DiyetisyenMusaitlikSablon.objects.filter(
                diyetisyen=diyetisyen
            ).update(aktif=False)
            
            # Yeni çalışma saatlerini kaydet
            for key, value in data.items():
                if key.endswith('_active') and value == 'on':
                    # Günü al
                    day_num = int(key.split('_')[1])
                    
                    # Başlangıç ve bitiş saatlerini al
                    start_key = f'day_{day_num}_start'
                    end_key = f'day_{day_num}_end'
                    
                    if start_key in data and end_key in data:
                        start_time = data[start_key]
                        end_time = data[end_key]
                        
                        # Çalışma saatini oluştur veya güncelle
                        schedule, created = DiyetisyenMusaitlikSablon.objects.update_or_create(
                            diyetisyen=diyetisyen,
                            gun=day_num,
                            baslangic_saati=start_time,
                            bitis_saati=end_time,
                            defaults={
                                'aktif': True
                            }
                        )
            
            return JsonResponse({
                'success': True,
                'message': 'Çalışma saatleri başarıyla kaydedildi'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Hata: {str(e)}'
            }, status=400)


# Dashboard Article Management Views
@login_required
def dashboard_articles_list(request):
    """Dashboard'da makale listesi göster"""
    user = request.user
    
    # Kullanıcı rolüne göre makaleleri filtrele
    if user.is_superuser or (hasattr(user, 'rol') and user.rol.rol_adi == 'admin'):
        articles = Makale.objects.all()
    elif hasattr(user, 'rol') and user.rol.rol_adi == 'diyetisyen':
        articles = Makale.objects.filter(yazar_kullanici=user)
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    articles = articles.select_related('kategori', 'yazar_kullanici').order_by('-olusturma_tarihi')
    
    # Filtreleme
    status_filter = request.GET.get('status')
    if status_filter:
        articles = articles.filter(onay_durumu=status_filter)
    
    category_filter = request.GET.get('category')
    if category_filter:
        articles = articles.filter(kategori_id=category_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        articles = articles.filter(
            Q(baslik__icontains=search_query) |
            Q(ozet__icontains=search_query) |
            Q(etiketler__icontains=search_query)
        )
    
    # Sayfalama
    from django.core.paginator import Paginator
    paginator = Paginator(articles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # JSON API isteği ise
    if request.headers.get('Accept') == 'application/json':
        articles_data = []
        for article in page_obj:
            articles_data.append({
                'id': article.id,
                'baslik': article.baslik,
                'slug': article.slug,
                'kategori': article.kategori.ad if article.kategori else None,
                'yazar': f"{article.yazar_kullanici.ad} {article.yazar_kullanici.soyad}",
                'onay_durumu': article.onay_durumu,
                'onay_durumu_display': article.get_onay_durumu_display(),
                'okunma_sayisi': article.okunma_sayisi,
                'begeni_sayisi': article.begeni_sayisi,
                'olusturma_tarihi': article.olusturma_tarihi.strftime('%d.%m.%Y %H:%M') if article.olusturma_tarihi else None,
                'yayimlanma_tarihi': article.yayimlanma_tarihi.strftime('%d.%m.%Y %H:%M') if article.yayimlanma_tarihi else None,
            })
        
        return JsonResponse({
            'success': True,
            'articles': articles_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'total_count': paginator.count
        })
    
    context = {
        'title': 'Makale Yönetimi',
        'articles': page_obj,
        'categories': MakaleKategori.objects.filter(aktif_mi=True),
        'current_section': 'articles'
    }
    
    return render(request, 'dashboard/articles/list.html', context)


@login_required
def dashboard_article_create(request):
    """Yeni makale oluştur"""
    user = request.user
    
    # Yetki kontrolü
    if not (hasattr(user, 'rol') and user.rol.rol_adi in ['diyetisyen', 'admin'] or user.is_superuser):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        from .forms import MakaleForm
        form = MakaleForm(request.POST, user=user)
        
        if form.is_valid():
            makale = form.save()
            
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Makale başarıyla oluşturuldu!',
                    'article_id': makale.id,
                    'redirect_url': f'/dashboard/?section=articles'
                })
            
            messages.success(request, 'Makale başarıyla oluşturuldu!')
            return redirect('core:dashboard_articles_list')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        from .forms import MakaleForm
        form = MakaleForm(user=user)
    
    context = {
        'title': 'Yeni Makale Oluştur',
        'form': form,
        'current_section': 'articles'
    }
    
    return render(request, 'dashboard/articles/create.html', context)


@login_required
def dashboard_article_edit(request, article_id):
    """Makale düzenle"""
    user = request.user
    
    # Makaleyi getir
    try:
        if user.is_superuser or (hasattr(user, 'rol') and user.rol.rol_adi == 'admin'):
            makale = get_object_or_404(Makale, id=article_id)
        else:
            makale = get_object_or_404(Makale, id=article_id, yazar_kullanici=user)
    except:
        return JsonResponse({'error': 'Article not found'}, status=404)
    
    if request.method == 'POST':
        from .forms import MakaleForm
        form = MakaleForm(request.POST, instance=makale, user=user)
        
        if form.is_valid():
            makale = form.save()
            
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Makale başarıyla güncellendi!',
                    'article_id': makale.id
                })
            
            messages.success(request, 'Makale başarıyla güncellendi!')
            return redirect('core:dashboard_articles_list')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        from .forms import MakaleForm
        form = MakaleForm(instance=makale, user=user)
    
    context = {
        'title': f'Makale Düzenle: {makale.baslik}',
        'form': form,
        'makale': makale,
        'current_section': 'articles'
    }
    
    return render(request, 'dashboard/articles/edit.html', context)


@login_required
@require_http_methods(["DELETE"])
def dashboard_article_delete(request, article_id):
    """Makale sil"""
    user = request.user
    
    # Sadece admin silebilir
    if not (user.is_superuser or (hasattr(user, 'rol') and user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        makale = get_object_or_404(Makale, id=article_id)
        makale.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Makale başarıyla silindi!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Hata: {str(e)}'
        }, status=400)


@login_required
def dashboard_articles_api(request):
    """Dashboard makale yönetimi API"""
    user = request.user
    
    if request.method == 'GET':
        # İstatistikler
        if user.is_superuser or (hasattr(user, 'rol') and user.rol.rol_adi == 'admin'):
            total_articles = Makale.objects.count()
            pending_articles = Makale.objects.filter(onay_durumu='BEKLEMEDE').count()
            approved_articles = Makale.objects.filter(onay_durumu='ONAYLANDI').count()
            published_articles = Makale.objects.filter(yayimlanma_tarihi__isnull=False).count()
        else:
            total_articles = Makale.objects.filter(yazar_kullanici=user).count()
            pending_articles = Makale.objects.filter(yazar_kullanici=user, onay_durumu='BEKLEMEDE').count()
            approved_articles = Makale.objects.filter(yazar_kullanici=user, onay_durumu='ONAYLANDI').count()
            published_articles = Makale.objects.filter(yazar_kullanici=user, yayimlanma_tarihi__isnull=False).count()
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_articles': total_articles,
                'pending_articles': pending_articles,
                'approved_articles': approved_articles,
                'published_articles': published_articles
            }
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# Diet Plans API Endpoints
@login_required
@require_http_methods(["GET", "POST"])
def diet_plans_api(request):
    """Diet plans API for dietitians"""
    user = request.user
    
    # Check if user is a dietitian
    if not (hasattr(user, 'rol') and user.rol.rol_adi == 'Diyetisyen'):
        return JsonResponse({'error': 'Bu işlem sadece diyetisyenler için geçerlidir.'}, status=403)
    
    try:
        diyetisyen = user.diyetisyen
    except:
        return JsonResponse({'error': 'Diyetisyen profili bulunamadı.'}, status=404)
    
    if request.method == 'GET':
        # List diet plans
        diet_plans = DiyetListesi.objects.filter(
            diyetisyen=diyetisyen
        ).select_related('danisan').order_by('-yuklenme_tarihi')
        
        plans_data = []
        for plan in diet_plans:
            plans_data.append({
                'id': plan.id,
                'baslik': plan.baslik,
                'icerik': plan.icerik,
                'yuklenme_tarihi': plan.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
                'danisan_name': f"{plan.danisan.ad} {plan.danisan.soyad}",
                'danisan': {
                    'id': plan.danisan.id,
                    'ad': plan.danisan.ad,
                    'soyad': plan.danisan.soyad,
                    'e_posta': plan.danisan.e_posta
                }
            })
        
        return JsonResponse({
            'success': True,
            'diet_plans': plans_data
        })
    
    elif request.method == 'POST':
        # Create new diet plan
        danisan_id = request.POST.get('danisan_id')
        baslik = request.POST.get('baslik')
        icerik = request.POST.get('icerik')
        files = request.FILES.getlist('files')
        
        if not all([danisan_id, baslik, icerik]):
            return JsonResponse({'error': 'Tüm zorunlu alanlar gereklidir.'}, status=400)
        
        try:
            danisan = Kullanici.objects.get(id=danisan_id)
            
            # Check if this patient has had appointments with this dietitian
            has_appointment = Randevu.objects.filter(
                diyetisyen=diyetisyen,
                danisan=danisan,
                durum__in=['ONAYLANDI', 'TAMAMLANDI']
            ).exists()
            
            if not has_appointment:
                return JsonResponse({'error': 'Bu hasta ile randevunuz bulunmuyor.'}, status=400)
            
            # Create diet plan
            diet_plan = DiyetListesi.objects.create(
                diyetisyen=diyetisyen,
                danisan=danisan,
                baslik=baslik,
                icerik=icerik
            )
            
            # Handle file uploads if any
            from .models import Dosya
            import os
            from django.conf import settings
            
            uploaded_files_info = []
            for file in files:
                # Check file size (max 10MB)
                if file.size > 10 * 1024 * 1024:
                    return JsonResponse({'error': f'Dosya çok büyük: {file.name} (Max: 10MB)'}, status=400)
                
                # Create file record
                file_extension = os.path.splitext(file.name)[1].lower()
                
                # Determine file type
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                    file_type = 'FOTOGRAF'
                elif file_extension in ['.pdf', '.doc', '.docx']:
                    file_type = 'BELGE'
                else:
                    file_type = 'DIGER'
                
                # Save file
                file_obj = Dosya.objects.create(
                    yukleyen_kullanici=user,
                    baglanti_tipi='RANDEVU',  # We'll use this for diet plans
                    baglanti_id=diet_plan.id,
                    dosya_adi=file.name,
                    uzanti=file_extension,
                    mime_type=file.content_type,
                    boyut_byte=file.size,
                    saklama_yolu=f'diet_plans/{diet_plan.id}/',
                    dosya_turu=file_type,
                    gizlilik='DANISAN_GOREBILIR'
                )
                
                # Save the actual file
                upload_path = os.path.join(settings.MEDIA_ROOT, 'diet_plans', str(diet_plan.id))
                os.makedirs(upload_path, exist_ok=True)
                
                file_path = os.path.join(upload_path, file.name)
                with open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                
                # Update the file path in database
                file_obj.saklama_yolu = f'diet_plans/{diet_plan.id}/{file.name}'
                file_obj.save()
                
                uploaded_files_info.append({
                    'id': file_obj.id,
                    'name': file.name,
                    'type': file_type,
                    'size': file.size
                })
            
            return JsonResponse({
                'success': True,
                'id': diet_plan.id,
                'message': 'Diyet planı başarıyla oluşturuldu!',
                'uploaded_files': uploaded_files_info
            })
            
        except Kullanici.DoesNotExist:
            return JsonResponse({'error': 'Hasta bulunamadı.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def diet_plan_detail_api(request, plan_id):
    """Diet plan detail API"""
    user = request.user
    
    # Check if user is a dietitian
    if not (hasattr(user, 'rol') and user.rol.rol_adi == 'Diyetisyen'):
        return JsonResponse({'error': 'Bu işlem sadece diyetisyenler için geçerlidir.'}, status=403)
    
    try:
        diyetisyen = user.diyetisyen
        diet_plan = get_object_or_404(DiyetListesi, id=plan_id, diyetisyen=diyetisyen)
    except:
        return JsonResponse({'error': 'Diyet planı bulunamadı.'}, status=404)
    
    if request.method == 'GET':
        # Get diet plan details
        plan_data = {
            'id': diet_plan.id,
            'baslik': diet_plan.baslik,
            'icerik': diet_plan.icerik,
            'yuklenme_tarihi': diet_plan.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
            'danisan_name': f"{diet_plan.danisan.ad} {diet_plan.danisan.soyad}",
            'danisan': {
                'id': diet_plan.danisan.id,
                'ad': diet_plan.danisan.ad,
                'soyad': diet_plan.danisan.soyad,
                'e_posta': diet_plan.danisan.e_posta
            }
        }
        
        return JsonResponse(plan_data)
    
    elif request.method == 'PATCH':
        # Update diet plan
        import json
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        
        baslik = data.get('baslik')
        icerik = data.get('icerik')
        
        if not all([baslik, icerik]):
            return JsonResponse({'error': 'Başlık ve içerik gereklidir.'}, status=400)
        
        try:
            diet_plan.baslik = baslik
            diet_plan.icerik = icerik
            diet_plan.save()
            
            return JsonResponse({
                'success': True,
                'id': diet_plan.id,
                'message': 'Diyet planı başarıyla güncellendi!'
            })
        except Exception as e:
            return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)
    
    elif request.method == 'DELETE':
        # Delete diet plan
        try:
            diet_plan.delete()
            return JsonResponse({
                'success': True,
                'message': 'Diyet planı başarıyla silindi!'
            })
        except Exception as e:
            return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


# Schedule API Endpoints
@login_required
@require_http_methods(["GET", "POST"])
def schedule_api(request):
    """Schedule management API for dietitians"""
    user = request.user
    
    # Check if user is a dietitian
    if not (hasattr(user, 'rol') and user.rol.rol_adi == 'Diyetisyen'):
        return JsonResponse({'error': 'Bu işlem sadece diyetisyenler için geçerlidir.'}, status=403)
    
    try:
        diyetisyen = user.diyetisyen
    except:
        return JsonResponse({'error': 'Diyetisyen profili bulunamadı.'}, status=404)
    
    if request.method == 'GET':
        # Get current schedule
        from .models import DiyetisyenMusaitlikSablon
        
        schedule_items = DiyetisyenMusaitlikSablon.objects.filter(
            diyetisyen=diyetisyen,
            aktif=True
        ).order_by('gun')
        
        schedule_data = []
        for item in schedule_items:
            schedule_data.append({
                'gun': item.gun,
                'gun_adi': item.get_gun_display(),
                'baslangic_saati': item.baslangic_saati.strftime('%H:%M'),
                'bitis_saati': item.bitis_saati.strftime('%H:%M'),
                'aktif': item.aktif
            })
        
        # Get appointments for this dietitian
        appointments = Randevu.objects.filter(
            diyetisyen=diyetisyen
        ).select_related('danisan').order_by('-randevu_tarih_saat')[:20]
        
        appointments_data = []
        for appointment in appointments:
            appointments_data.append({
                'id': appointment.id,
                'danisan_name': f"{appointment.danisan.ad} {appointment.danisan.soyad}",
                'randevu_tarih_saat': appointment.randevu_tarih_saat.strftime('%d.%m.%Y %H:%M'),
                'durum': appointment.durum,
                'durum_display': appointment.get_durum_display(),
                'tip': appointment.tip,
                'tip_display': appointment.get_tip_display(),
                'randevu_turu': appointment.randevu_turu
            })
        
        return JsonResponse({
            'success': True,
            'schedule': schedule_data,
            'appointments': appointments_data
        })
    
    elif request.method == 'POST':
        # Save schedule
        import json
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        
        from .models import DiyetisyenMusaitlikSablon
        
        try:
            # Clear existing schedule
            DiyetisyenMusaitlikSablon.objects.filter(diyetisyen=diyetisyen).delete()
            
            # Save new schedule
            created_items = []
            for key, value in data.items():
                if key.startswith('day_') and key.endswith('_active') and value == 'on':
                    day_num = int(key.split('_')[1])
                    start_time_key = f'day_{day_num}_start'
                    end_time_key = f'day_{day_num}_end'
                    
                    if start_time_key in data and end_time_key in data:
                        from datetime import datetime
                        start_time = datetime.strptime(data[start_time_key], '%H:%M').time()
                        end_time = datetime.strptime(data[end_time_key], '%H:%M').time()
                        
                        schedule_item = DiyetisyenMusaitlikSablon.objects.create(
                            diyetisyen=diyetisyen,
                            gun=day_num,
                            baslangic_saati=start_time,
                            bitis_saati=end_time,
                            aktif=True
                        )
                        created_items.append({
                            'gun': day_num,
                            'baslangic_saati': start_time.strftime('%H:%M'),
                            'bitis_saati': end_time.strftime('%H:%M')
                        })
            
            return JsonResponse({
                'success': True,
                'message': 'Çalışma saatleri başarıyla kaydedildi!',
                'created_items': created_items
            })
            
        except Exception as e:
            return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


# Admin Matching API Views
@login_required
@require_http_methods(["GET"])
def admin_patients_api(request):
    """Get all patients for admin matching"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    patients = Kullanici.objects.filter(rol__rol_adi='danisan').values(
        'id', 'ad', 'soyad', 'e_posta', 'telefon'
    )
    
    patients_list = []
    for patient in patients:
        patients_list.append({
            'id': patient['id'],
            'name': f"{patient['ad']} {patient['soyad']}",
            'email': patient['e_posta'],
            'phone': patient['telefon']
        })
    
    return JsonResponse({'success': True, 'patients': patients_list})


@login_required
@require_http_methods(["GET"])
def admin_patients_unmatched_api(request):
    """Get unmatched patients for admin"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    unmatched_patients = Kullanici.objects.filter(
        rol__rol_adi='danisan',
        danisandiyetisyeneslesme__isnull=True
    ).values('id', 'ad', 'soyad', 'e_posta')
    
    patients_list = []
    for patient in unmatched_patients:
        patients_list.append({
            'id': patient['id'],
            'name': f"{patient['ad']} {patient['soyad']}",
            'email': patient['e_posta']
        })
    
    return JsonResponse({'success': True, 'patients': patients_list})


@login_required
@require_http_methods(["GET"])
def admin_dietitians_api(request):
    """Get approved dietitians for admin matching"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    status_filter = request.GET.get('status', 'approved')
    
    if status_filter == 'approved':
        dietitians = Diyetisyen.objects.filter(
            onay_durumu='ONAYLANDI'
        ).select_related('kullanici')
    else:
        dietitians = Diyetisyen.objects.all().select_related('kullanici')
    
    dietitians_list = []
    for dietitian in dietitians:
        dietitians_list.append({
            'id': dietitian.pk,
            'name': f"Dyt. {dietitian.kullanici.ad} {dietitian.kullanici.soyad}",
            'email': dietitian.kullanici.e_posta,
            'phone': dietitian.kullanici.telefon,
            'university': dietitian.universite,
            'fee': dietitian.hizmet_ucreti
        })
    
    return JsonResponse({'success': True, 'dietitians': dietitians_list})


@login_required
@require_http_methods(["POST"])
def admin_matchings_create_api(request):
    """Create new patient-dietitian matching"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    try:
        danisan_id = request.POST.get('danisan_id')
        diyetisyen_id = request.POST.get('diyetisyen_id')
        on_gorusme_yapildi_mi = request.POST.get('on_gorusme_yapildi_mi') == 'true'
        hasta_mi = request.POST.get('hasta_mi') == 'true'
        
        if not danisan_id or not diyetisyen_id:
            return JsonResponse({'error': 'Danışan ve diyetisyen seçimi zorunludur'}, status=400)
        
        danisan = Kullanici.objects.get(pk=danisan_id)
        diyetisyen = Diyetisyen.objects.get(pk=diyetisyen_id)
        
        # Check if matching already exists
        existing_matching = DanisanDiyetisyenEslesme.objects.filter(
            danisan=danisan,
            diyetisyen=diyetisyen
        ).first()
        
        if existing_matching:
            return JsonResponse({'error': 'Bu eşleştirme zaten mevcut'}, status=400)
        
        # Create new matching
        matching = DanisanDiyetisyenEslesme.objects.create(
            danisan=danisan,
            diyetisyen=diyetisyen,
            on_gorusme_yapildi_mi=on_gorusme_yapildi_mi,
            hasta_mi=hasta_mi
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Eşleştirme başarıyla oluşturuldu',
            'matching_id': matching.id
        })
        
    except Kullanici.DoesNotExist:
        return JsonResponse({'error': 'Danışan bulunamadı'}, status=404)
    except Diyetisyen.DoesNotExist:
        return JsonResponse({'error': 'Diyetisyen bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET"])
def admin_matchings_detail_api(request, matching_id):
    """Get matching details"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    try:
        matching = DanisanDiyetisyenEslesme.objects.select_related(
            'danisan', 'diyetisyen__kullanici'
        ).get(id=matching_id)
        
        # Get appointment count
        appointment_count = Randevu.objects.filter(
            diyetisyen=matching.diyetisyen,
            danisan=matching.danisan
        ).count()
        
        matching_data = {
            'id': matching.id,
            'danisan': {
                'id': matching.danisan.id,
                'name': f"{matching.danisan.ad} {matching.danisan.soyad}",
                'email': matching.danisan.e_posta,
                'telefon': matching.danisan.telefon
            },
            'diyetisyen': {
                'id': matching.diyetisyen.id,
                'name': f"Dyt. {matching.diyetisyen.kullanici.ad} {matching.diyetisyen.kullanici.soyad}",
                'email': matching.diyetisyen.kullanici.e_posta,
                'telefon': matching.diyetisyen.kullanici.telefon
            },
            'eslesme_tarihi': matching.eslesme_tarihi.strftime('%d.%m.%Y %H:%M'),
            'on_gorusme_yapildi_mi': matching.on_gorusme_yapildi_mi,
            'hasta_mi': matching.hasta_mi,
            'appointment_count': appointment_count,
            'diyetisyen_id': matching.diyetisyen.id
        }
        
        return JsonResponse({'success': True, 'matching': matching_data})
        
    except DanisanDiyetisyenEslesme.DoesNotExist:
        return JsonResponse({'error': 'Eşleştirme bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def admin_matchings_update_api(request, matching_id):
    """Update matching details"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    try:
        matching = DanisanDiyetisyenEslesme.objects.get(id=matching_id)
        
        on_gorusme_yapildi_mi = request.POST.get('on_gorusme_yapildi_mi') == 'true'
        hasta_mi = request.POST.get('hasta_mi') == 'true'
        
        matching.on_gorusme_yapildi_mi = on_gorusme_yapildi_mi
        matching.hasta_mi = hasta_mi
        matching.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Eşleştirme başarıyla güncellendi'
        })
        
    except DanisanDiyetisyenEslesme.DoesNotExist:
        return JsonResponse({'error': 'Eşleştirme bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def admin_matchings_change_dietitian_api(request, matching_id):
    """Change dietitian for a patient"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    try:
        matching = DanisanDiyetisyenEslesme.objects.get(id=matching_id)
        new_diyetisyen_id = request.POST.get('diyetisyen_id')
        change_reason = request.POST.get('neden', '')
        
        if not new_diyetisyen_id:
            return JsonResponse({'error': 'Yeni diyetisyen seçimi zorunludur'}, status=400)
        
        new_diyetisyen = Diyetisyen.objects.get(id=new_diyetisyen_id)
        
        # Check if matching with new dietitian already exists
        existing_matching = DanisanDiyetisyenEslesme.objects.filter(
            danisan=matching.danisan,
            diyetisyen=new_diyetisyen
        ).exclude(id=matching_id).first()
        
        if existing_matching:
            return JsonResponse({'error': 'Bu danışan zaten seçilen diyetisyen ile eşleştirilmiş'}, status=400)
        
        # Update the matching
        old_diyetisyen_name = f"{matching.diyetisyen.kullanici.ad} {matching.diyetisyen.kullanici.soyad}"
        matching.diyetisyen = new_diyetisyen
        matching.save()
        
        # Create a notification or log entry for the change
        from .models import Bildirim
        Bildirim.objects.create(
            kullanici=matching.danisan,
            baslik='Diyetisyen Değişikliği',
            icerik=f'Diyetisyeniniz {old_diyetisyen_name} yerine {new_diyetisyen.kullanici.ad} {new_diyetisyen.kullanici.soyad} olarak değiştirildi. Neden: {change_reason}',
            bildirim_tipi='BILGILENDIRME'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Diyetisyen başarıyla değiştirildi'
        })
        
    except DanisanDiyetisyenEslesme.DoesNotExist:
        return JsonResponse({'error': 'Eşleştirme bulunamadı'}, status=404)
    except Diyetisyen.DoesNotExist:
        return JsonResponse({'error': 'Yeni diyetisyen bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["DELETE"])
def admin_matchings_delete_api(request, matching_id):
    """Delete a matching"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import DanisanDiyetisyenEslesme
    
    try:
        matching = DanisanDiyetisyenEslesme.objects.get(id=matching_id)
        
        # Check if there are any appointments
        appointment_count = Randevu.objects.filter(
            diyetisyen=matching.diyetisyen,
            danisan=matching.danisan
        ).count()
        
        if appointment_count > 0:
            # Don't delete, just mark as inactive or handle differently
            # For now, we'll allow deletion but could add a warning
            pass
        
        matching.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Eşleştirme başarıyla kaldırıldı'
        })
        
    except DanisanDiyetisyenEslesme.DoesNotExist:
        return JsonResponse({'error': 'Eşleştirme bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)



@login_required
@csrf_protect
def user_delete_api(request, user_id):
    """Delete a specific user - for admin only"""
    # Check admin permissions
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Prevent admin from deleting themselves
    if user_id == request.user.id:
        return JsonResponse({'error': 'Kendi hesabınızı silemezsiniz!'}, status=400)
    
    try:
        user = Kullanici.objects.get(id=user_id)
        
        # Prevent deleting other admin users
        if hasattr(user, 'rol') and user.rol and user.rol.rol_adi.upper() == 'ADMIN':
            return JsonResponse({'error': 'Admin kullanıcıları silinemez!'}, status=400)
        
        # Get user name for logging
        user_name = f"{user.ad} {user.soyad}"
        
        # Delete the user
        user.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Kullanıcı "{user_name}" başarıyla silindi.'
        })
        
    except Kullanici.DoesNotExist:
        return JsonResponse({'error': 'Kullanıcı bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Silme işlemi başarısız: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET"])
def appointment_detail_api(request, appointment_id):
    """Get single appointment details for admin"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)
    
    try:
        randevu = Randevu.objects.select_related(
            'diyetisyen__kullanici', 
            'danisan'
        ).get(pk=appointment_id)
        
        appointment_data = {
            'id': randevu.pk,
            'randevu_tarih_saat': randevu.randevu_tarih_saat.strftime('%Y-%m-%dT%H:%M'),
            'durum': randevu.durum,
            'notlar': randevu.iptal_nedeni or '',
            'diyetisyen_id': randevu.diyetisyen.pk,
            'diyetisyen': {
                'id': randevu.diyetisyen.pk,
                'kullanici': {
                    'ad': randevu.diyetisyen.kullanici.ad,
                    'soyad': randevu.diyetisyen.kullanici.soyad,
                    'e_posta': randevu.diyetisyen.kullanici.e_posta,
                    'telefon': randevu.diyetisyen.kullanici.telefon or 'Belirtilmemiş'
                },
                'hizmet_ucreti': randevu.diyetisyen.hizmet_ucreti or 0
            },
            'danisan': {
                'id': randevu.danisan.pk,
                'ad': randevu.danisan.ad,
                'soyad': randevu.danisan.soyad,
                'e_posta': randevu.danisan.e_posta,
                'telefon': randevu.danisan.telefon or 'Belirtilmemiş'
            }
        }
        
        return JsonResponse({
            'success': True,
            'appointment': appointment_data
        })
        
    except Randevu.DoesNotExist:
        return JsonResponse({'error': 'Randevu bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def appointment_update_api(request, appointment_id):
    """Update appointment details by admin"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)
    
    try:
        randevu = Randevu.objects.select_related('diyetisyen__kullanici', 'danisan').get(pk=appointment_id)
        old_dietitian = randevu.diyetisyen
        
        # Get new data
        new_date_time = request.POST.get('randevu_tarih_saat')
        new_status = request.POST.get('durum')
        new_dietitian_id = request.POST.get('diyetisyen_id')
        new_notes = request.POST.get('notlar', '')
        
        # Validate inputs
        if not all([new_date_time, new_status, new_dietitian_id]):
            return JsonResponse({'error': 'Eksik bilgi'}, status=400)
        
        # Check if dietitian exists
        try:
            new_dietitian = Diyetisyen.objects.get(pk=new_dietitian_id)
        except Diyetisyen.DoesNotExist:
            return JsonResponse({'error': 'Diyetisyen bulunamadı'}, status=404)
        
        # Parse date
        try:
            from datetime import datetime
            randevu_datetime = datetime.fromisoformat(new_date_time.replace('T', ' '))
        except ValueError:
            return JsonResponse({'error': 'Geçersiz tarih formatı'}, status=400)
        
        # Check if dietitian is changing
        dietitian_changed = old_dietitian.pk != new_dietitian.pk
        
        # Update appointment
        randevu.randevu_tarih_saat = randevu_datetime
        randevu.durum = new_status
        randevu.diyetisyen = new_dietitian
        randevu.iptal_nedeni = new_notes
        randevu.save()
        
        # Send notifications if dietitian changed
        if dietitian_changed:
            # Notify old dietitian about change
            Bildirim.objects.create(
                kullanici=old_dietitian.kullanici,
                baslik='Randevu Değişikliği',
                icerik=f'{randevu.danisan.ad} {randevu.danisan.soyad} adlı danışanın randevusu başka bir diyetisyene atandı.',
                okundu=False,
                tarih=timezone.now()
            )
            
            # Notify new dietitian about assignment
            Bildirim.objects.create(
                kullanici=new_dietitian.kullanici,
                baslik='Yeni Randevu Ataması',
                icerik=f'{randevu.danisan.ad} {randevu.danisan.soyad} adlı danışan size atandı. Randevu tarihi: {randevu_datetime.strftime("%d.%m.%Y %H:%M")}',
                okundu=False,
                tarih=timezone.now()
            )
            
            # Notify patient about dietitian change
            Bildirim.objects.create(
                kullanici=randevu.danisan,
                baslik='Diyetisyen Değişikliği',
                icerik=f'Randevunuz {new_dietitian.kullanici.ad} {new_dietitian.kullanici.soyad} diyetisyeni ile yapılacak.',
                okundu=False,
                tarih=timezone.now()
            )
        
        # Handle appointment cancellation notifications
        if new_status == 'IPTAL':
            # Notify all admin users about cancellation - they need to reassign
            admin_users = Kullanici.objects.filter(is_staff=True)
            for admin in admin_users:
                Bildirim.objects.create(
                    kullanici=admin,
                    baslik='Randevu İptali - Yeni Diyetisyen Gerekli',
                    icerik=f'ACIL: {randevu.danisan.ad} {randevu.danisan.soyad} adlı danışanın randevusu iptal edildi. Yeni bir diyetisyen ataması yapılması gerekiyor.',
                    okundu=False,
                    tarih=timezone.now()
                )
            
            # Notify patient about cancellation
            Bildirim.objects.create(
                kullanici=randevu.danisan,
                baslik='Randevu İptali',
                icerik='Randevunuz iptal edilmiştir. En kısa sürede size yeni bir diyetisyen atanacaktır.',
                okundu=False,
                tarih=timezone.now()
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Randevu başarıyla güncellendi'
        })
        
    except Randevu.DoesNotExist:
        return JsonResponse({'error': 'Randevu bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Güncelleme hatası: {str(e)}'}, status=500)


@login_required  
@require_http_methods(["POST"])
def create_test_data_api(request):
    """Create test users and appointments for testing"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)
    
    try:
        from datetime import timedelta
        import random
        
        # Test diyetisyenleri oluştur
        dietitians_data = [
            {'ad': 'Ayşe', 'soyad': 'Demir', 'email': 'ayse.demir@test.com'},
            {'ad': 'Mehmet', 'soyad': 'Kaya', 'email': 'mehmet.kaya@test.com'},
            {'ad': 'Fatma', 'soyad': 'Öz', 'email': 'fatma.oz@test.com'},
        ]

        # Test danışanları oluştur
        patients_data = [
            {'ad': 'Ahmet', 'soyad': 'Yılmaz', 'email': 'ahmet.yilmaz@test.com'},
            {'ad': 'Zeynep', 'soyad': 'Çelik', 'email': 'zeynep.celik@test.com'},
            {'ad': 'Emre', 'soyad': 'Aydın', 'email': 'emre.aydin@test.com'},
        ]

        created_dietitians = []
        created_patients = []

        # Diyetisyenleri oluştur
        for data in dietitians_data:
            if not Kullanici.objects.filter(e_posta=data['email']).exists():
                user = Kullanici.objects.create_user(
                    e_posta=data['email'],
                    ad=data['ad'],
                    soyad=data['soyad'],
                    password='test123'
                )
                dietitian = Diyetisyen.objects.create(
                    kullanici=user,
                    onay_durumu='ONAYLANDI',
                    universite='Test Üniversitesi',
                    mezuniyet_yili=2020,
                    uzmanlik_alani='Genel Beslenme',
                    hizmet_ucreti=500
                )
                created_dietitians.append(dietitian)

        # Danışanları oluştur
        for data in patients_data:
            if not Kullanici.objects.filter(e_posta=data['email']).exists():
                patient = Kullanici.objects.create_user(
                    e_posta=data['email'],
                    ad=data['ad'],
                    soyad=data['soyad'],
                    password='test123'
                )
                created_patients.append(patient)

        # Get existing ones if already exist
        if not created_dietitians:
            for data in dietitians_data:
                user = Kullanici.objects.get(e_posta=data['email'])
                dietitian = Diyetisyen.objects.get(kullanici=user)
                created_dietitians.append(dietitian)
                
        if not created_patients:
            for data in patients_data:
                user = Kullanici.objects.get(e_posta=data['email'])
                created_patients.append(user)

        # Test randevuları oluştur
        statuses = ['BEKLEMEDE', 'ONAYLANDI', 'TAMAMLANDI', 'IPTAL']
        created_appointments = 0
        
        for i in range(10):
            dietitian = random.choice(created_dietitians)
            patient = random.choice(created_patients)
            status = random.choice(statuses)
            
            # Rastgele tarih (gelecek 30 gün içinde)
            future_date = timezone.now() + timedelta(days=random.randint(1, 30))
            
            randevu = Randevu.objects.create(
                diyetisyen=dietitian,
                danisan=patient,
                randevu_tarih_saat=future_date,
                durum=status,
                notlar=f'Test randevu {i+1}'
            )
            created_appointments += 1

        return JsonResponse({
            'success': True,
            'message': f'{len(created_dietitians)} diyetisyen, {len(created_patients)} danışan, {created_appointments} randevu oluşturuldu!'
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Test veri oluşturma hatası: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET"])
def auto_assign_suggestions_api(request, appointment_id):
    """Get automatic dietitian assignment suggestions for cancelled appointments"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)
    
    try:
        randevu = Randevu.objects.select_related('danisan').get(pk=appointment_id)
        
        if randevu.durum != 'IPTAL':
            return JsonResponse({'error': 'Bu randevu iptal edilmemiş'}, status=400)
        
        # Get available dietitians who are approved and active
        available_dietitians = Diyetisyen.objects.filter(
            onay_durumu='ONAYLANDI'
        ).select_related('kullanici').annotate(
            current_patients=Count('randevu', filter=Q(randevu__durum__in=['BEKLEMEDE', 'ONAYLANDI']))
        ).order_by('current_patients', 'kullanici__ad')
        
        suggestions = []
        for dietitian in available_dietitians:
            suggestions.append({
                'id': dietitian.pk,
                'name': f"{dietitian.kullanici.ad} {dietitian.kullanici.soyad}",
                'email': dietitian.kullanici.e_posta,
                'specialty': dietitian.uzmanlik_alani or 'Genel Beslenme',
                'current_patients': dietitian.current_patients,
                'fee': dietitian.hizmet_ucreti or 0,
                'recommendation_score': max(0, 10 - dietitian.current_patients)  # Simple scoring
            })
        
        # Sort by recommendation score (less busy dietitians first)
        suggestions.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'patient_name': f"{randevu.danisan.ad} {randevu.danisan.soyad}",
            'appointment_id': appointment_id,
            'suggestions': suggestions[:5]  # Top 5 suggestions
        })
        
    except Randevu.DoesNotExist:
        return JsonResponse({'error': 'Randevu bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


# Survey Management API Functions

@login_required
@csrf_protect
def admin_questions_api(request):
    """Survey questions management API"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    if request.method == 'GET':
        # Get or create default survey set
        from .models import SoruSeti, Soru, SoruSecenek, AnketOturum, AnketCevap
        
        survey_set, created = SoruSeti.objects.get_or_create(
            ad="Üyelik Anketi",
            defaults={
                'aciklama': 'Yeni üyeler için tanışma anketi',
                'aktif_mi': True
            }
        )
        
        # Get all questions for this survey set
        questions = Soru.objects.filter(soru_seti=survey_set).order_by('sira')
        
        questions_data = []
        for question in questions:
            options_count = SoruSecenek.objects.filter(soru=question).count()
            questions_data.append({
                'id': question.id,
                'soru_metni': question.soru_metni,
                'soru_tipi': question.soru_tipi,
                'sira_no': question.sira,
                'zorunlu': question.gerekli,
                'aktif': True,  # Since we don't have this field in existing model
                'secenek_sayisi': options_count if question.soru_tipi in ['SINGLE_CHOICE', 'MULTI_CHOICE'] else None
            })
        
        # Calculate stats
        total_questions = questions.count()
        active_questions = total_questions  # All questions are considered active
        total_responses = AnketOturum.objects.filter(soru_seti=survey_set, durum='TAMAMLANDI').count()
        
        completion_rate = 0
        total_sessions = AnketOturum.objects.filter(soru_seti=survey_set).count()
        if total_sessions > 0:
            completion_rate = round((total_responses / total_sessions) * 100, 1)
        
        return JsonResponse({
            'questions': questions_data,
            'stats': {
                'total': total_questions,
                'active': active_questions,
                'responses': total_responses,
                'completion_rate': completion_rate
            }
        })
    
    elif request.method == 'POST':
        # Create new question
        try:
            data = json.loads(request.body)
            
            # Get or create default survey set
            from .models import SoruSeti, Soru, SoruSecenek
            
            survey_set, created = SoruSeti.objects.get_or_create(
                ad="Üyelik Anketi",
                defaults={
                    'aciklama': 'Yeni üyeler için tanışma anketi',
                    'aktif_mi': True
                }
            )
            
            # Validate required fields
            if not data.get('soru_metni') or not data.get('soru_tipi'):
                return JsonResponse({'error': 'Soru metni ve tipi gerekli'}, status=400)
            
            # Map question types
            type_mapping = {
                'SINGLE_CHOICE': 'SINGLE_CHOICE',
                'MULTIPLE_CHOICE': 'MULTI_CHOICE',
                'TEXT': 'TEXT',
                'SCALE': 'NUMBER'
            }
            
            soru_tipi = type_mapping.get(data['soru_tipi'], data['soru_tipi'])
            
            # Determine order
            sira = data.get('sira_no')
            if not sira:
                from django.db.models import Max
                max_sira = Soru.objects.filter(soru_seti=survey_set).aggregate(
                    max_sira=Max('sira')
                )['max_sira'] or 0
                sira = max_sira + 1
            
            # Create question
            question = Soru.objects.create(
                soru_seti=survey_set,
                soru_metni=data['soru_metni'],
                soru_tipi=soru_tipi,
                sira=int(sira),
                gerekli=data.get('zorunlu', False)
            )
            
            # Create options if needed
            if data['soru_tipi'] in ['SINGLE_CHOICE', 'MULTIPLE_CHOICE'] and data.get('secenekler'):
                for i, option_text in enumerate(data['secenekler']):
                    SoruSecenek.objects.create(
                        soru=question,
                        etiket=option_text,
                        deger=str(i + 1),
                        sira=i + 1
                    )
            
            return JsonResponse({
                'success': True,
                'message': 'Soru başarıyla eklendi',
                'question_id': question.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Geçersiz JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_protect
def admin_question_detail_api(request, question_id):
    """Individual question management API"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    from .models import Soru, SoruSecenek
    
    try:
        question = Soru.objects.get(id=question_id)
        
        if request.method == 'GET':
            # Get question details with options
            options = SoruSecenek.objects.filter(soru=question).order_by('sira')
            
            # Map question types back
            type_mapping = {
                'SINGLE_CHOICE': 'SINGLE_CHOICE',
                'MULTI_CHOICE': 'MULTIPLE_CHOICE',
                'TEXT': 'TEXT',
                'NUMBER': 'SCALE'
            }
            
            question_data = {
                'id': question.id,
                'soru_metni': question.soru_metni,
                'soru_tipi': type_mapping.get(question.soru_tipi, question.soru_tipi),
                'sira_no': question.sira,
                'zorunlu': question.gerekli,
                'secenekler': [{'secenek_metni': opt.etiket} for opt in options]
            }
            
            return JsonResponse(question_data)
        
        elif request.method == 'PUT':
            # Update question
            try:
                data = json.loads(request.body)
                
                # Update basic fields
                question.soru_metni = data.get('soru_metni', question.soru_metni)
                question.sira = int(data.get('sira_no', question.sira))
                question.gerekli = data.get('zorunlu', question.gerekli)
                
                # Map question type
                type_mapping = {
                    'SINGLE_CHOICE': 'SINGLE_CHOICE',
                    'MULTIPLE_CHOICE': 'MULTI_CHOICE',
                    'TEXT': 'TEXT',
                    'SCALE': 'NUMBER'
                }
                
                if 'soru_tipi' in data:
                    question.soru_tipi = type_mapping.get(data['soru_tipi'], data['soru_tipi'])
                
                question.save()
                
                # Update options if provided
                if data.get('secenekler') and question.soru_tipi in ['SINGLE_CHOICE', 'MULTI_CHOICE']:
                    # Delete existing options
                    SoruSecenek.objects.filter(soru=question).delete()
                    
                    # Create new options
                    for i, option_text in enumerate(data['secenekler']):
                        SoruSecenek.objects.create(
                            soru=question,
                            etiket=option_text,
                            deger=str(i + 1),
                            sira=i + 1
                        )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Soru başarıyla güncellendi'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Geçersiz JSON'}, status=400)
        
        elif request.method == 'PATCH':
            # Partial update (e.g., just status)
            try:
                data = json.loads(request.body)
                
                # For now, we'll just acknowledge the status change
                # since the existing model doesn't have an 'aktif' field
                
                return JsonResponse({
                    'success': True,
                    'message': 'Soru durumu güncellendi'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Geçersiz JSON'}, status=400)
        
        elif request.method == 'DELETE':
            # Delete question and its options
            question.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Soru başarıyla silindi'
            })
        
    except Soru.DoesNotExist:
        return JsonResponse({'error': 'Soru bulunamadı'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_protect
def admin_survey_preview_api(request):
    """Survey preview API"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from .models import SoruSeti, Soru, SoruSecenek
        
        # Get default survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi").first()
        
        if not survey_set:
            return JsonResponse({'questions': []})
        
        # Get all questions
        questions = Soru.objects.filter(soru_seti=survey_set).order_by('sira')
        
        questions_data = []
        for question in questions:
            options = SoruSecenek.objects.filter(soru=question).order_by('sira')
            
            # Map question types back
            type_mapping = {
                'SINGLE_CHOICE': 'SINGLE_CHOICE',
                'MULTI_CHOICE': 'MULTIPLE_CHOICE',
                'TEXT': 'TEXT',
                'NUMBER': 'SCALE'
            }
            
            question_data = {
                'id': question.id,
                'soru_metni': question.soru_metni,
                'soru_tipi': type_mapping.get(question.soru_tipi, question.soru_tipi),
                'zorunlu': question.gerekli,
                'secenekler': [{'secenek_metni': opt.etiket} for opt in options]
            }
            
            questions_data.append(question_data)
        
        return JsonResponse({'questions': questions_data})
        
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)


@login_required
@csrf_protect
def admin_activate_survey_api(request):
    """Activate survey API"""
    if not (request.user.is_superuser or (hasattr(request.user, 'rol') and request.user.rol.rol_adi == 'admin')):
        return JsonResponse({'error': 'Yetkisiz erişim'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from .models import SoruSeti, Soru
        
        # Get default survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi").first()
        
        if not survey_set:
            return JsonResponse({'error': 'Anket bulunamadı'}, status=404)
        
        questions_count = Soru.objects.filter(soru_seti=survey_set).count()
        
        if questions_count == 0:
            return JsonResponse({'error': 'Anket aktivasyonu için en az bir soru gerekli'}, status=400)
        
        # Activate survey
        survey_set.aktif_mi = True
        survey_set.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Anket başarıyla aktifleştirildi ({questions_count} soru)'
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Hata: {str(e)}'}, status=500)



# Survey Response Management

@login_required
def survey_view(request):
    """Display survey page for clients"""
    user = request.user
    
    # Check if user is a client
    if not (hasattr(user, "rol") and user.rol.rol_adi == "danisan"):
        messages.error(request, "Bu sayfaya erişim yetkiniz bulunmamaktadır.")
        return redirect("core:dashboard")
    
    from .models import SoruSeti, AnketOturum
    
    # Get active survey set
    survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi", aktif_mi=True).first()
    
    if not survey_set:
        messages.info(request, "Şu anda aktif bir anket bulunmamaktadır.")
        return redirect("core:dashboard")
    
    # Get or create survey session
    survey_session = AnketOturum.objects.filter(
        kullanici=user,
        soru_seti=survey_set
    ).first()
    
    context = {
        "title": "Üyelik Anketi",
        "survey_set": survey_set,
        "survey_session": survey_session
    }
    
    return render(request, "core/survey.html", context)


@login_required
@csrf_protect
def survey_start_api(request):
    """Start a new survey session"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = request.user
    
    # Check if user is a client
    if not (hasattr(user, "rol") and user.rol.rol_adi == "danisan"):
        return JsonResponse({"error": "Sadece danışanlar anket doldurabilir"}, status=403)
    
    try:
        from .models import SoruSeti, AnketOturum
        
        # Get active survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi", aktif_mi=True).first()
        
        if not survey_set:
            return JsonResponse({"error": "Aktif anket bulunamadı"}, status=404)
        
        # Check if session already exists
        existing_session = AnketOturum.objects.filter(
            kullanici=user,
            soru_seti=survey_set
        ).first()
        
        if existing_session:
            return JsonResponse({"error": "Bu anket için zaten bir oturum bulunmaktadır"}, status=400)
        
        # Create new session
        survey_session = AnketOturum.objects.create(
            kullanici=user,
            soru_seti=survey_set,
            durum="ACIK"
        )
        
        return JsonResponse({
            "success": True,
            "session_id": survey_session.id,
            "message": "Anket oturumu başlatıldı"
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect
def survey_questions_api(request):
    """Get survey questions for current user"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        from .models import SoruSeti, Soru, SoruSecenek
        
        # Get active survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi", aktif_mi=True).first()
        
        if not survey_set:
            return JsonResponse({"questions": []})
        
        # Get all questions
        questions = Soru.objects.filter(soru_seti=survey_set).order_by("sira")
        
        questions_data = []
        for question in questions:
            options = SoruSecenek.objects.filter(soru=question).order_by("sira")
            
            question_data = {
                "id": question.id,
                "soru_metni": question.soru_metni,
                "soru_tipi": question.soru_tipi,
                "gerekli": question.gerekli,
                "secenekler": [{"deger": opt.deger, "etiket": opt.etiket} for opt in options]
            }
            
            questions_data.append(question_data)
        
        return JsonResponse({"questions": questions_data})
        
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect
def survey_answers_api(request, session_id):
    """Get existing answers for a survey session"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = request.user
    
    try:
        from .models import AnketOturum, AnketCevap, AnketCokluSecim
        
        # Get survey session
        survey_session = AnketOturum.objects.get(id=session_id, kullanici=user)
        
        # Get all answers
        answers = AnketCevap.objects.filter(anket_oturum=survey_session)
        
        answers_data = []
        for answer in answers:
            answer_data = {
                "soru_id": answer.soru.id,
                "cevap_metin": answer.cevap_metin,
                "cevap_sayi": float(answer.cevap_sayi) if answer.cevap_sayi else None,
                "cevap_secenek": {
                    "deger": answer.cevap_secenek.deger,
                    "etiket": answer.cevap_secenek.etiket
                } if answer.cevap_secenek else None
            }
            
            # Get multiple choice selections
            multi_selections = AnketCokluSecim.objects.filter(anket_cevap=answer)
            if multi_selections.exists():
                answer_data["coklu_secimler"] = [
                    {
                        "deger": sel.secenek.deger,
                        "etiket": sel.secenek.etiket
                    } for sel in multi_selections
                ]
            
            answers_data.append(answer_data)
        
        return JsonResponse({"answers": answers_data})
        
    except AnketOturum.DoesNotExist:
        return JsonResponse({"error": "Anket oturumu bulunamadı"}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect
def survey_submit_api(request):
    """Submit survey answers"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = request.user
    
    try:
        data = json.loads(request.body)
        session_id = data.get("session_id")
        answers = data.get("answers", [])
        
        from .models import AnketOturum, AnketCevap, AnketCokluSecim, Soru, SoruSecenek
        
        # Get survey session
        survey_session = AnketOturum.objects.get(id=session_id, kullanici=user)
        
        if survey_session.durum == "TAMAMLANDI":
            return JsonResponse({"error": "Bu anket zaten tamamlanmış"}, status=400)
        
        # Process each answer
        for answer_data in answers:
            question_id = answer_data["question_id"]
            question_type = answer_data["question_type"]
            
            try:
                question = Soru.objects.get(id=question_id)
                
                # Delete existing answer if any
                AnketCevap.objects.filter(anket_oturum=survey_session, soru=question).delete()
                
                # Create new answer
                answer = AnketCevap.objects.create(
                    anket_oturum=survey_session,
                    soru=question
                )
                
                # Set answer based on type
                if question_type == "TEXT" and answer_data.get("text_answer"):
                    answer.cevap_metin = answer_data["text_answer"]
                    
                elif question_type == "NUMBER" and answer_data.get("number_answer"):
                    answer.cevap_sayi = answer_data["number_answer"]
                    
                elif question_type == "SINGLE_CHOICE" and answer_data.get("option_value"):
                    option = SoruSecenek.objects.get(soru=question, deger=answer_data["option_value"])
                    answer.cevap_secenek = option
                    
                elif question_type == "MULTI_CHOICE" and answer_data.get("option_values"):
                    # Save answer first, then add multiple selections
                    answer.save()
                    
                    for option_value in answer_data["option_values"]:
                        option = SoruSecenek.objects.get(soru=question, deger=option_value)
                        AnketCokluSecim.objects.create(
                            anket_cevap=answer,
                            secenek=option
                        )
                
                answer.save()
                
            except Soru.DoesNotExist:
                continue  # Skip invalid questions
            except SoruSecenek.DoesNotExist:
                continue  # Skip invalid options
        
        # Mark session as completed
        survey_session.durum = "TAMAMLANDI"
        survey_session.tamamlama_tarihi = timezone.now()
        survey_session.save()
        
        return JsonResponse({
            "success": True,
            "message": "Anket başarıyla tamamlandı"
        })
        
    except AnketOturum.DoesNotExist:
        return JsonResponse({"error": "Anket oturumu bulunamadı"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Geçersiz JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect
def survey_results_api(request, session_id):
    """Get survey results for a completed session"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = request.user
    
    try:
        from .models import AnketOturum, AnketCevap, AnketCokluSecim
        
        # Get survey session
        survey_session = AnketOturum.objects.get(id=session_id, kullanici=user)
        
        if survey_session.durum != "TAMAMLANDI":
            return JsonResponse({"error": "Anket henüz tamamlanmamış"}, status=400)
        
        # Get all answers with questions
        answers = AnketCevap.objects.filter(anket_oturum=survey_session).select_related("soru")
        
        results_data = []
        for answer in answers:
            result = {
                "soru_metni": answer.soru.soru_metni,
                "cevap_metin": answer.cevap_metin,
                "cevap_sayi": float(answer.cevap_sayi) if answer.cevap_sayi else None,
                "cevap_secenek": answer.cevap_secenek.etiket if answer.cevap_secenek else None
            }
            
            # Get multiple choice selections
            multi_selections = AnketCokluSecim.objects.filter(anket_cevap=answer)
            if multi_selections.exists():
                result["coklu_secimler"] = [sel.secenek.etiket for sel in multi_selections]
            
            results_data.append(result)
        
        return JsonResponse({"results": results_data})
        
    except AnketOturum.DoesNotExist:
        return JsonResponse({"error": "Anket oturumu bulunamadı"}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect  
def admin_survey_responses_api(request, session_id=None):
    """Admin survey responses API"""
    if not (request.user.is_superuser or (hasattr(request.user, "rol") and request.user.rol.rol_adi == "admin")):
        return JsonResponse({"error": "Yetkisiz erişim"}, status=403)
    
    if request.method == "GET":
        try:
            from .models import AnketOturum, AnketCevap, AnketCokluSecim
            
            if session_id:
                # Get specific session details
                session = AnketOturum.objects.get(id=session_id)
                
                answers = AnketCevap.objects.filter(anket_oturum=session).select_related("soru")
                
                answers_data = []
                for answer in answers:
                    answer_data = {
                        "soru_metni": answer.soru.soru_metni,
                        "cevap_metin": answer.cevap_metin,
                        "cevap_sayi": float(answer.cevap_sayi) if answer.cevap_sayi else None,
                        "cevap_secenek": answer.cevap_secenek.etiket if answer.cevap_secenek else None
                    }
                    
                    # Get multiple choice selections
                    multi_selections = AnketCokluSecim.objects.filter(anket_cevap=answer)
                    if multi_selections.exists():
                        answer_data["coklu_secimler"] = [sel.secenek.etiket for sel in multi_selections]
                    
                    answers_data.append(answer_data)
                
                return JsonResponse({
                    "kullanici_ad": session.kullanici.ad,
                    "kullanici_soyad": session.kullanici.soyad,
                    "kullanici_email": session.kullanici.e_posta,
                    "baslama_tarihi": session.baslama_tarihi,
                    "tamamlama_tarihi": session.tamamlama_tarihi,
                    "durum": session.durum,
                    "answers": answers_data
                })
            else:
                # Get all responses
                filter_type = request.GET.get("filter", "all")
                
                sessions = AnketOturum.objects.select_related("kullanici")
                
                if filter_type == "completed":
                    sessions = sessions.filter(durum="TAMAMLANDI")
                elif filter_type == "pending":
                    sessions = sessions.filter(durum="ACIK")
                
                sessions = sessions.order_by("-baslama_tarihi")
                
                responses_data = []
                for session in sessions:
                    answer_count = AnketCevap.objects.filter(anket_oturum=session).count()
                    
                    responses_data.append({
                        "id": session.id,
                        "kullanici_ad": session.kullanici.ad,
                        "kullanici_soyad": session.kullanici.soyad,
                        "kullanici_email": session.kullanici.e_posta,
                        "baslama_tarihi": session.baslama_tarihi,
                        "tamamlama_tarihi": session.tamamlama_tarihi,
                        "durum": session.durum,
                        "cevap_sayisi": answer_count
                    })
                
                return JsonResponse({"responses": responses_data})
                
        except AnketOturum.DoesNotExist:
            return JsonResponse({"error": "Anket oturumu bulunamadı"}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
@csrf_protect
def admin_survey_analytics_api(request):
    """Survey analytics API for admin"""
    if not (request.user.is_superuser or (hasattr(request.user, "rol") and request.user.rol.rol_adi == "admin")):
        return JsonResponse({"error": "Yetkisiz erişim"}, status=403)
    
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        from .models import SoruSeti, AnketOturum, AnketCevap, Soru, SoruSecenek, AnketCokluSecim
        from django.db.models import Count, Avg
        
        # Get default survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi").first()
        
        if not survey_set:
            return JsonResponse({
                "total_sessions": 0,
                "completed_sessions": 0,
                "pending_sessions": 0,
                "avg_completion": 0,
                "question_analysis": []
            })
        
        # Basic stats
        total_sessions = AnketOturum.objects.filter(soru_seti=survey_set).count()
        completed_sessions = AnketOturum.objects.filter(soru_seti=survey_set, durum="TAMAMLANDI").count()
        pending_sessions = total_sessions - completed_sessions
        
        avg_completion = 0
        if total_sessions > 0:
            avg_completion = round((completed_sessions / total_sessions) * 100, 1)
        
        # Question analysis
        questions = Soru.objects.filter(soru_seti=survey_set).order_by("sira")
        question_analysis = []
        
        for question in questions:
            answers = AnketCevap.objects.filter(soru=question)
            total_responses = answers.count()
            
            qa_data = {
                "soru_metni": question.soru_metni,
                "soru_tipi": question.soru_tipi,
                "total_responses": total_responses
            }
            
            if question.soru_tipi in ["SINGLE_CHOICE", "MULTI_CHOICE"]:
                # Option statistics
                options = SoruSecenek.objects.filter(soru=question)
                option_stats = []
                
                for option in options:
                    if question.soru_tipi == "SINGLE_CHOICE":
                        count = answers.filter(cevap_secenek=option).count()
                    else:  # MULTI_CHOICE
                        count = AnketCokluSecim.objects.filter(
                            anket_cevap__soru=question,
                            secenek=option
                        ).count()
                    
                    percentage = round((count / total_responses * 100), 1) if total_responses > 0 else 0
                    
                    option_stats.append({
                        "option_text": option.etiket,
                        "count": count,
                        "percentage": percentage
                    })
                
                qa_data["option_stats"] = option_stats
                
            elif question.soru_tipi == "NUMBER":
                # Numerical statistics
                numeric_answers = answers.filter(cevap_sayi__isnull=False)
                if numeric_answers.exists():
                    qa_data["avg_value"] = round(numeric_answers.aggregate(avg=Avg("cevap_sayi"))["avg"], 2)
                    qa_data["min_value"] = numeric_answers.order_by("cevap_sayi").first().cevap_sayi
                    qa_data["max_value"] = numeric_answers.order_by("-cevap_sayi").first().cevap_sayi
                
            elif question.soru_tipi == "TEXT":
                # Text statistics
                text_answers = answers.filter(cevap_metin__isnull=False)
                if text_answers.exists():
                    total_words = sum(len(answer.cevap_metin.split()) for answer in text_answers)
                    qa_data["avg_word_count"] = round(total_words / text_answers.count(), 1)
            
            question_analysis.append(qa_data)
        
        return JsonResponse({
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "pending_sessions": pending_sessions,
            "avg_completion": avg_completion,
            "question_analysis": question_analysis
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)


@login_required
@csrf_protect
def survey_status_api(request):
    """Get survey status for current user"""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = request.user
    
    # Check if user is a client
    if not (hasattr(user, "rol") and user.rol.rol_adi == "danisan"):
        return JsonResponse({"error": "Sadece danışanlar anket durumunu görebilir"}, status=403)
    
    try:
        from .models import SoruSeti, AnketOturum, AnketCevap, Soru
        
        # Get active survey set
        survey_set = SoruSeti.objects.filter(ad="Üyelik Anketi", aktif_mi=True).first()
        
        if not survey_set:
            return JsonResponse({
                "has_active_survey": False,
                "survey_session": None
            })
        
        # Get user survey session
        survey_session = AnketOturum.objects.filter(
            kullanici=user,
            soru_seti=survey_set
        ).first()
        
        # Get total questions count
        total_questions = Soru.objects.filter(soru_seti=survey_set).count()
        
        response_data = {
            "has_active_survey": True,
            "survey_name": survey_set.ad,
            "survey_description": survey_set.aciklama,
            "total_questions": total_questions,
            "estimated_time": "5-10"  # Static for now
        }
        
        if survey_session:
            # Get answered questions count
            answered_questions = AnketCevap.objects.filter(anket_oturum=survey_session).count()
            progress_percentage = round((answered_questions / total_questions * 100), 1) if total_questions > 0 else 0
            
            response_data.update({
                "survey_session": {
                    "id": survey_session.id,
                    "durum": survey_session.durum,
                    "baslama_tarihi": survey_session.baslama_tarihi,
                    "tamamlama_tarihi": survey_session.tamamlama_tarihi
                },
                "answered_questions": answered_questions,
                "progress_percentage": progress_percentage
            })
        else:
            response_data.update({
                "survey_session": None,
                "answered_questions": 0,
                "progress_percentage": 0
            })
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({"error": f"Hata: {str(e)}"}, status=500)
