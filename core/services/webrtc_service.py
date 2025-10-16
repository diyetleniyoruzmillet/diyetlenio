"""
WebRTC Video Call Service for Diyetlenio
Handles video calls between patients, dietitians, and admins
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import logging

from .base_service import BaseService, ServiceResult
from ..models import Kullanici, Randevu, Diyetisyen

logger = logging.getLogger(__name__)


class WebRTCCallStatus:
    """WebRTC call status constants"""
    INITIATED = 'initiated'
    RINGING = 'ringing'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ENDED = 'ended'
    FAILED = 'failed'
    REJECTED = 'rejected'


class WebRTCCallType:
    """WebRTC call type constants"""
    APPOINTMENT = 'appointment'
    EMERGENCY = 'emergency'
    CONSULTATION = 'consultation'
    ADMIN_SUPPORT = 'admin_support'


class WebRTCService(BaseService):
    """Service for managing WebRTC video calls"""
    
    def __init__(self):
        super().__init__()
        self.ice_servers = self._get_ice_servers()
        self.call_timeout = 300  # 5 minutes
    
    def _get_ice_servers(self) -> List[Dict]:
        """Get ICE servers configuration"""
        # Default ICE servers - in production, use your own TURN servers
        return [
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
            {
                'urls': 'turn:your-turn-server.com:3478',
                'username': getattr(settings, 'TURN_USERNAME', 'diyetlenio'),
                'credential': getattr(settings, 'TURN_PASSWORD', 'your-turn-password')
            }
        ]
    
    def initiate_call(self, data: Dict) -> ServiceResult:
        """Initiate a WebRTC call"""
        try:
            caller_id = data.get('caller_id')
            callee_id = data.get('callee_id')
            call_type = data.get('call_type', WebRTCCallType.CONSULTATION)
            randevu_id = data.get('randevu_id')
            
            # Validate users
            try:
                caller = Kullanici.objects.get(id=caller_id, aktif_mi=True)
                callee = Kullanici.objects.get(id=callee_id, aktif_mi=True)
            except Kullanici.DoesNotExist:
                return ServiceResult.error_result("Geçersiz kullanıcı ID'si")
            
            # Validate permissions
            if not self._can_initiate_call(caller, callee, call_type, randevu_id):
                return ServiceResult.error_result("Bu aramayı başlatma yetkiniz yok")
            
            # Generate call ID
            call_id = str(uuid.uuid4())
            
            # Create call session
            call_session = {
                'call_id': call_id,
                'caller_id': caller_id,
                'callee_id': callee_id,
                'call_type': call_type,
                'randevu_id': randevu_id,
                'status': WebRTCCallStatus.INITIATED,
                'created_at': timezone.now().isoformat(),
                'ice_servers': self.ice_servers,
                'offers': {},
                'answers': {},
                'ice_candidates': {'caller': [], 'callee': []},
                'participants': {
                    'caller': {
                        'user_id': caller_id,
                        'name': f"{caller.ad} {caller.soyad}",
                        'role': caller.rol.rol_adi,
                        'connected': False,
                        'joined_at': None
                    },
                    'callee': {
                        'user_id': callee_id,
                        'name': f"{callee.ad} {callee.soyad}",
                        'role': callee.rol.rol_adi,
                        'connected': False,
                        'joined_at': None
                    }
                }
            }
            
            # Store in cache with timeout
            cache.set(f'webrtc_call_{call_id}', call_session, self.call_timeout)
            
            # Send call notification to callee
            self._notify_incoming_call(callee, call_session)
            
            # Update appointment if provided
            if randevu_id:
                self._update_appointment_call_link(randevu_id, call_id)
            
            self.log_operation("WebRTC call initiated",
                             call_id=call_id,
                             caller_id=caller_id,
                             callee_id=callee_id,
                             call_type=call_type)
            
            return ServiceResult.success_result({
                'call_id': call_id,
                'call_session': call_session,
                'join_url': f"/video-call/{call_id}",
                'ice_servers': self.ice_servers
            })
            
        except Exception as e:
            self.log_error("Initiate WebRTC call", e)
            return ServiceResult.error_result(f"Arama başlatılırken hata: {str(e)}")
    
    def join_call(self, call_id: str, user_id: int) -> ServiceResult:
        """Join an existing WebRTC call"""
        try:
            # Get call session
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı veya süresi doldu")
            
            # Validate user can join
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Bu aramaya katılma yetkiniz yok")
            
            # Update participant status
            participant_key = 'caller' if user_id == call_session['caller_id'] else 'callee'
            call_session['participants'][participant_key]['connected'] = True
            call_session['participants'][participant_key]['joined_at'] = timezone.now().isoformat()
            
            # Update call status
            if call_session['status'] == WebRTCCallStatus.INITIATED:
                call_session['status'] = WebRTCCallStatus.RINGING
            elif all(p['connected'] for p in call_session['participants'].values()):
                call_session['status'] = WebRTCCallStatus.CONNECTED
                call_session['connected_at'] = timezone.now().isoformat()
            
            # Update cache
            cache.set(f'webrtc_call_{call_id}', call_session, self.call_timeout)
            
            self.log_operation("User joined WebRTC call",
                             call_id=call_id,
                             user_id=user_id,
                             participant_key=participant_key)
            
            return ServiceResult.success_result({
                'call_session': call_session,
                'participant_info': call_session['participants'][participant_key],
                'ice_servers': self.ice_servers
            })
            
        except Exception as e:
            self.log_error("Join WebRTC call", e)
            return ServiceResult.error_result(f"Aramaya katılırken hata: {str(e)}")
    
    def handle_offer(self, call_id: str, user_id: int, offer: Dict) -> ServiceResult:
        """Handle WebRTC offer"""
        try:
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı")
            
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Yetkiniz yok")
            
            # Store offer
            participant_key = 'caller' if user_id == call_session['caller_id'] else 'callee'
            call_session['offers'][participant_key] = {
                'sdp': offer,
                'timestamp': timezone.now().isoformat()
            }
            
            # Update status
            call_session['status'] = WebRTCCallStatus.CONNECTING
            
            # Update cache
            cache.set(f'webrtc_call_{call_id}', call_session, self.call_timeout)
            
            # Notify other participant
            other_user_id = call_session['callee_id'] if user_id == call_session['caller_id'] else call_session['caller_id']
            self._notify_webrtc_event(other_user_id, 'offer', {
                'call_id': call_id,
                'offer': offer,
                'from_user_id': user_id
            })
            
            return ServiceResult.success_result({'status': 'offer_sent'})
            
        except Exception as e:
            self.log_error("Handle WebRTC offer", e)
            return ServiceResult.error_result(f"Offer işlenirken hata: {str(e)}")
    
    def handle_answer(self, call_id: str, user_id: int, answer: Dict) -> ServiceResult:
        """Handle WebRTC answer"""
        try:
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı")
            
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Yetkiniz yok")
            
            # Store answer
            participant_key = 'caller' if user_id == call_session['caller_id'] else 'callee'
            call_session['answers'][participant_key] = {
                'sdp': answer,
                'timestamp': timezone.now().isoformat()
            }
            
            # Update cache
            cache.set(f'webrtc_call_{call_id}', call_session, self.call_timeout)
            
            # Notify other participant
            other_user_id = call_session['callee_id'] if user_id == call_session['caller_id'] else call_session['caller_id']
            self._notify_webrtc_event(other_user_id, 'answer', {
                'call_id': call_id,
                'answer': answer,
                'from_user_id': user_id
            })
            
            return ServiceResult.success_result({'status': 'answer_sent'})
            
        except Exception as e:
            self.log_error("Handle WebRTC answer", e)
            return ServiceResult.error_result(f"Answer işlenirken hata: {str(e)}")
    
    def handle_ice_candidate(self, call_id: str, user_id: int, candidate: Dict) -> ServiceResult:
        """Handle ICE candidate"""
        try:
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı")
            
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Yetkiniz yok")
            
            # Store ICE candidate
            participant_key = 'caller' if user_id == call_session['caller_id'] else 'callee'
            call_session['ice_candidates'][participant_key].append({
                'candidate': candidate,
                'timestamp': timezone.now().isoformat()
            })
            
            # Update cache
            cache.set(f'webrtc_call_{call_id}', call_session, self.call_timeout)
            
            # Notify other participant
            other_user_id = call_session['callee_id'] if user_id == call_session['caller_id'] else call_session['caller_id']
            self._notify_webrtc_event(other_user_id, 'ice_candidate', {
                'call_id': call_id,
                'candidate': candidate,
                'from_user_id': user_id
            })
            
            return ServiceResult.success_result({'status': 'candidate_sent'})
            
        except Exception as e:
            self.log_error("Handle ICE candidate", e)
            return ServiceResult.error_result(f"ICE candidate işlenirken hata: {str(e)}")
    
    def end_call(self, call_id: str, user_id: int, reason: str = None) -> ServiceResult:
        """End a WebRTC call"""
        try:
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı")
            
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Yetkiniz yok")
            
            # Update call status
            call_session['status'] = WebRTCCallStatus.ENDED
            call_session['ended_at'] = timezone.now().isoformat()
            call_session['ended_by'] = user_id
            call_session['end_reason'] = reason or 'user_ended'
            
            # Calculate call duration
            if 'connected_at' in call_session:
                connected_at = datetime.fromisoformat(call_session['connected_at'].replace('Z', '+00:00'))
                ended_at = timezone.now()
                duration = (ended_at - connected_at).total_seconds()
                call_session['duration_seconds'] = duration
            
            # Update cache with longer timeout for history
            cache.set(f'webrtc_call_{call_id}', call_session, 3600)  # Keep for 1 hour
            
            # Notify other participant
            other_user_id = call_session['callee_id'] if user_id == call_session['caller_id'] else call_session['caller_id']
            self._notify_webrtc_event(other_user_id, 'call_ended', {
                'call_id': call_id,
                'ended_by': user_id,
                'reason': reason
            })
            
            # Update appointment if exists
            if call_session.get('randevu_id'):
                self._update_appointment_after_call(call_session['randevu_id'], call_session)
            
            self.log_operation("WebRTC call ended",
                             call_id=call_id,
                             ended_by=user_id,
                             duration=call_session.get('duration_seconds', 0),
                             reason=reason)
            
            return ServiceResult.success_result({
                'call_ended': True,
                'duration': call_session.get('duration_seconds', 0),
                'call_summary': self._generate_call_summary(call_session)
            })
            
        except Exception as e:
            self.log_error("End WebRTC call", e)
            return ServiceResult.error_result(f"Arama sonlandırılırken hata: {str(e)}")
    
    def get_call_status(self, call_id: str, user_id: int) -> ServiceResult:
        """Get current call status"""
        try:
            call_session = cache.get(f'webrtc_call_{call_id}')
            if not call_session:
                return ServiceResult.error_result("Arama bulunamadı")
            
            if user_id not in [call_session['caller_id'], call_session['callee_id']]:
                return ServiceResult.error_result("Yetkiniz yok")
            
            return ServiceResult.success_result({
                'call_id': call_id,
                'status': call_session['status'],
                'participants': call_session['participants'],
                'duration': self._calculate_current_duration(call_session),
                'created_at': call_session['created_at']
            })
            
        except Exception as e:
            self.log_error("Get call status", e)
            return ServiceResult.error_result(f"Arama durumu alınırken hata: {str(e)}")
    
    def _can_initiate_call(self, caller: Kullanici, callee: Kullanici, 
                          call_type: str, randevu_id: Optional[int]) -> bool:
        """Check if caller can initiate call with callee"""
        try:
            # Admin can call anyone
            if caller.rol.rol_adi == 'admin':
                return True
            
            # Emergency calls allowed for patients
            if call_type == WebRTCCallType.EMERGENCY and caller.rol.rol_adi == 'danisan':
                return True
            
            # Appointment calls
            if call_type == WebRTCCallType.APPOINTMENT and randevu_id:
                try:
                    randevu = Randevu.objects.get(id=randevu_id)
                    return (
                        (caller.id == randevu.danisan.id and callee.id == randevu.diyetisyen.kullanici.id) or
                        (caller.id == randevu.diyetisyen.kullanici.id and callee.id == randevu.danisan.id)
                    )
                except Randevu.DoesNotExist:
                    return False
            
            # Dietitian-patient relationship check
            if caller.rol.rol_adi == 'diyetisyen' and callee.rol.rol_adi == 'danisan':
                from ..models import DanisanDiyetisyenEslesme
                return DanisanDiyetisyenEslesme.objects.filter(
                    diyetisyen__kullanici=caller,
                    danisan=callee
                ).exists()
            
            return False
            
        except Exception:
            return False
    
    def _notify_incoming_call(self, callee: Kullanici, call_session: Dict):
        """Notify user of incoming call"""
        # This would integrate with your notification service
        from .notification_service import AdvancedNotificationService
        
        notification_service = AdvancedNotificationService()
        caller_name = call_session['participants']['caller']['name']
        
        notification_data = {
            'alici_kullanici_id': callee.id,
            'mesaj': f"{caller_name} size görüntülü arama başlatıyor",
            'tur': 'INCOMING_CALL',
            'channels': ['IN_APP', 'PUSH'],
            'priority': 'HIGH',
            'call_data': {
                'call_id': call_session['call_id'],
                'caller_name': caller_name,
                'call_type': call_session['call_type']
            }
        }
        
        notification_service.send_notification(notification_data)
    
    def _notify_webrtc_event(self, user_id: int, event_type: str, data: Dict):
        """Send WebRTC event notification"""
        # This would use WebSocket or similar real-time communication
        logger.info(f"WebRTC event {event_type} sent to user {user_id}: {data}")
    
    def _update_appointment_call_link(self, randevu_id: int, call_id: str):
        """Update appointment with call link"""
        try:
            randevu = Randevu.objects.get(id=randevu_id)
            randevu.kamera_linki = f"/video-call/{call_id}"
            randevu.save()
        except Randevu.DoesNotExist:
            pass
    
    def _update_appointment_after_call(self, randevu_id: int, call_session: Dict):
        """Update appointment after call ends"""
        try:
            randevu = Randevu.objects.get(id=randevu_id)
            if call_session['status'] == WebRTCCallStatus.ENDED and 'connected_at' in call_session:
                randevu.baslangic_saati_gercek = datetime.fromisoformat(call_session['connected_at'].replace('Z', '+00:00'))
                randevu.bitis_saati_gercek = datetime.fromisoformat(call_session['ended_at'].replace('Z', '+00:00'))
                randevu.durum = 'TAMAMLANDI'
                randevu.save()
        except Randevu.DoesNotExist:
            pass
    
    def _calculate_current_duration(self, call_session: Dict) -> Optional[int]:
        """Calculate current call duration in seconds"""
        if 'connected_at' in call_session and call_session['status'] == WebRTCCallStatus.CONNECTED:
            connected_at = datetime.fromisoformat(call_session['connected_at'].replace('Z', '+00:00'))
            return int((timezone.now() - connected_at).total_seconds())
        return None
    
    def _generate_call_summary(self, call_session: Dict) -> Dict:
        """Generate call summary"""
        return {
            'call_id': call_session['call_id'],
            'participants': [p['name'] for p in call_session['participants'].values()],
            'duration': call_session.get('duration_seconds', 0),
            'call_type': call_session['call_type'],
            'status': call_session['status'],
            'started_at': call_session['created_at'],
            'ended_at': call_session.get('ended_at')
        }