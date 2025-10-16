"""
WebRTC template views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.core.cache import cache

from .models import Kullanici, Randevu
from .permissions import PermissionChecker


@login_required
def video_call_view(request, call_id):
    """Video call page"""
    
    # Verify call exists and user has access
    call_session = cache.get(f'webrtc_call_{call_id}')
    if not call_session:
        raise Http404("Arama bulunamadı veya süresi doldu")
    
    # Check if user is participant
    if request.user.id not in [call_session['caller_id'], call_session['callee_id']]:
        raise Http404("Bu aramaya erişim yetkiniz yok")
    
    # Get participant info
    is_caller = request.user.id == call_session['caller_id']
    participant_key = 'caller' if is_caller else 'callee'
    participant_info = call_session['participants'][participant_key]
    other_participant = call_session['participants']['callee' if is_caller else 'caller']
    
    context = {
        'call_id': call_id,
        'call_session': call_session,
        'participant_info': participant_info,
        'other_participant': other_participant,
        'is_caller': is_caller,
        'title': f'Video Görüşme - {other_participant["name"]}'
    }
    
    return render(request, 'video_call.html', context)


@login_required 
def emergency_call_view(request):
    """Emergency call initiation page"""
    
    # Check if user can make emergency calls
    if request.user.rol.rol_adi not in ['danisan', 'diyetisyen']:
        raise Http404("Acil arama yetkiniz yok")
    
    context = {
        'title': 'Acil Diyetisyen Görüşmesi',
        'user': request.user
    }
    
    return render(request, 'emergency_call.html', context)


@login_required
def appointment_video_call(request, randevu_id):
    """Video call for a specific appointment"""
    
    # Get appointment
    randevu = get_object_or_404(Randevu, id=randevu_id)
    
    # Check access permissions
    if not PermissionChecker.can_access_appointment(request.user, randevu):
        raise Http404("Bu randevuya erişim yetkiniz yok")
    
    # Check if appointment is today and within time window
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    appointment_time = randevu.randevu_tarih_saat
    
    # Allow access 15 minutes before and up to 2 hours after appointment
    access_start = appointment_time - timedelta(minutes=15)
    access_end = appointment_time + timedelta(hours=2)
    
    if not (access_start <= now <= access_end):
        context = {
            'error': 'Randevu saati henüz gelmedi veya çok geçti',
            'appointment_time': appointment_time,
            'current_time': now,
            'title': 'Video Görüşme'
        }
        return render(request, 'appointment_call_error.html', context)
    
    # Check if call already exists for this appointment
    if randevu.kamera_linki and '/video-call/' in randevu.kamera_linki:
        call_id = randevu.kamera_linki.split('/')[-1]
        call_session = cache.get(f'webrtc_call_{call_id}')
        
        if call_session:
            return video_call_view(request, call_id)
    
    # Create new call for appointment
    from .services.webrtc_service import WebRTCService
    
    webrtc_service = WebRTCService()
    
    # Determine caller and callee
    if request.user.id == randevu.danisan.id:
        callee_id = randevu.diyetisyen.kullanici.id
    else:
        callee_id = randevu.danisan.id
    
    call_data = {
        'caller_id': request.user.id,
        'callee_id': callee_id,
        'call_type': 'appointment',
        'randevu_id': randevu_id
    }
    
    result = webrtc_service.initiate_call(call_data)
    
    if result.is_success:
        call_id = result.data['call_id']
        return video_call_view(request, call_id)
    else:
        context = {
            'error': f'Video görüşme başlatılamadı: {result.error_message}',
            'randevu': randevu,
            'title': 'Video Görüşme Hatası'
        }
        return render(request, 'appointment_call_error.html', context)