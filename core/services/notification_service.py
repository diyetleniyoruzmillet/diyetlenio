"""
Advanced notification business logic service with real-time capabilities.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from django.conf import settings

from .base_service import BaseService, ServiceResult
from .email_service import EmailService
from core.models import Bildirim, Kullanici, Diyetisyen, Randevu

logger = logging.getLogger(__name__)


class NotificationTypes:
    """Notification type constants"""
    WELCOME = 'HOSGELDIN'
    APPOINTMENT_NEW = 'YENI_RANDEVU'
    APPOINTMENT_APPROVED = 'RANDEVU_ONAYLANDI'
    APPOINTMENT_CANCELLED = 'RANDEVU_IPTAL'
    APPOINTMENT_REMINDER = 'RANDEVU_HATIRLATMA'
    PAYMENT_SUCCESS = 'ODEME_ONAY'
    PAYMENT_FAILED = 'ODEME_HATA'
    DIET_PLAN_READY = 'DIYET_HAZIR'
    DIETITIAN_APPROVED = 'DIYETISYEN_ONAY'
    SYSTEM_MAINTENANCE = 'SISTEM_BAKIM'
    GENERAL = 'GENEL'


class NotificationPriority:
    """Notification priority levels"""
    LOW = 'LOW'
    NORMAL = 'NORMAL'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class NotificationChannel:
    """Available notification channels"""
    IN_APP = 'IN_APP'
    EMAIL = 'EMAIL'
    SMS = 'SMS'
    PUSH = 'PUSH'


class AdvancedNotificationService(BaseService):
    """Enhanced notification service with multiple channels and real-time features"""
    
    def __init__(self):
        super().__init__()
        self.email_service = EmailService()
    
    def send_notification(self, data: Dict) -> ServiceResult:
        """Send enhanced notification with multiple channels"""
        required_fields = ['alici_kullanici_id', 'mesaj']
        validation = self.validate_input(data, required_fields)
        
        if not validation:
            return validation
        
        try:
            alici = Kullanici.objects.get(
                id=data['alici_kullanici_id'],
                aktif_mi=True
            )
            
            # Create in-app notification
            bildirim = Bildirim.objects.create(
                alici_kullanici=alici,
                baslik=data.get('baslik', 'Bildirim'),
                mesaj=data['mesaj'],
                tur=data.get('tur', NotificationTypes.GENERAL),
                oncelik=data.get('oncelik', 'NORMAL'),
                hedef_url=data.get('hedef_url'),
                randevu=data.get('randevu'),
                odeme_hareketi=data.get('odeme_hareketi'),
                okundu_mu=False
            )
            
            # Handle multiple channels
            channels = data.get('channels', [NotificationChannel.IN_APP])
            priority = data.get('priority', NotificationPriority.NORMAL)
            
            # Send email if requested
            if NotificationChannel.EMAIL in channels:
                self._send_email_notification(alici, data)
            
            # Send SMS if requested
            if NotificationChannel.SMS in channels:
                self._send_sms_notification(alici, data)
            
            # Send push notification if requested
            if NotificationChannel.PUSH in channels:
                self._send_push_notification(alici, data)
            
            # Update user notification cache
            self._update_user_notification_cache(alici.id)
            
            # Send real-time notification
            self._send_realtime_notification(alici.id, {
                'type': 'new_notification',
                'notification': {
                    'id': bildirim.id,
                    'message': bildirim.mesaj,
                    'type': bildirim.tur,
                    'created_at': bildirim.tarih.isoformat(),
                    'priority': priority
                }
            })
            
            self.log_operation("Enhanced notification sent",
                             bildirim_id=bildirim.id,
                             alici_id=alici.id,
                             tur=data.get('tur', NotificationTypes.GENERAL),
                             channels=channels,
                             priority=priority)
            
            return ServiceResult.success_result(bildirim)
            
        except Kullanici.DoesNotExist:
            return ServiceResult.error_result("Alıcı kullanıcı bulunamadı")
        except Exception as e:
            self.log_error("Send enhanced notification", e)
            return ServiceResult.error_result(f"Bildirim gönderilirken hata oluştu: {str(e)}")
    
    def send_appointment_reminder(self, randevu_id: int) -> ServiceResult:
        """Send appointment reminder notification"""
        try:
            randevu = Randevu.objects.select_related('danisan', 'diyetisyen__kullanici').get(id=randevu_id)
            
            # Send to patient
            patient_data = {
                'alici_kullanici_id': randevu.danisan.id,
                'mesaj': f"Yarın saat {randevu.randevu_tarih_saat.strftime('%H:%M')}'de Dyt. {randevu.diyetisyen.kullanici.ad} {randevu.diyetisyen.kullanici.soyad} ile randevunuz bulunmaktadır.",
                'tur': NotificationTypes.APPOINTMENT_REMINDER,
                'channels': [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                'priority': NotificationPriority.HIGH
            }
            
            # Send to dietitian
            dietitian_data = {
                'alici_kullanici_id': randevu.diyetisyen.kullanici.id,
                'mesaj': f"Yarın saat {randevu.randevu_tarih_saat.strftime('%H:%M')}'de {randevu.danisan.ad} {randevu.danisan.soyad} ile randevunuz bulunmaktadır.",
                'tur': NotificationTypes.APPOINTMENT_REMINDER,
                'channels': [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                'priority': NotificationPriority.HIGH
            }
            
            patient_result = self.send_notification(patient_data)
            dietitian_result = self.send_notification(dietitian_data)
            
            return ServiceResult.success_result({
                'patient_notification': patient_result.data,
                'dietitian_notification': dietitian_result.data
            })
            
        except Randevu.DoesNotExist:
            return ServiceResult.error_result("Randevu bulunamadı")
        except Exception as e:
            self.log_error("Send appointment reminder", e)
            return ServiceResult.error_result(f"Randevu hatırlatması gönderilirken hata oluştu: {str(e)}")
    
    def _send_email_notification(self, user: Kullanici, data: Dict) -> bool:
        """Send email notification"""
        try:
            notification_type = data.get('tur', NotificationTypes.GENERAL)
            
            if notification_type == NotificationTypes.APPOINTMENT_REMINDER:
                return self.email_service.send_appointment_reminder(data.get('randevu'))
            elif notification_type == NotificationTypes.APPOINTMENT_APPROVED:
                return self.email_service.send_appointment_confirmation(data.get('randevu'))
            elif notification_type == NotificationTypes.PAYMENT_SUCCESS:
                return self.email_service.send_payment_confirmation(data.get('odeme_hareketi'))
            else:
                # Generic email
                return self.email_service.send_bulk_email(
                    recipients=[user.e_posta],
                    subject="Diyetlenio Bildirimi",
                    message=data['mesaj']
                )
        except Exception as e:
            logger.error(f"Email notification failed: {str(e)}")
            return False
    
    def _send_sms_notification(self, user: Kullanici, data: Dict) -> bool:
        """Send SMS notification (placeholder)"""
        # TODO: Implement SMS service integration
        logger.info(f"SMS notification would be sent to {user.telefon}: {data['mesaj']}")
        return True
    
    def _send_push_notification(self, user: Kullanici, data: Dict) -> bool:
        """Send push notification (placeholder)"""
        # TODO: Implement push notification service
        logger.info(f"Push notification would be sent to user {user.id}: {data['mesaj']}")
        return True
    
    def _send_realtime_notification(self, user_id: int, data: Dict):
        """Send real-time notification via WebSocket (placeholder)"""
        # TODO: Implement WebSocket integration
        logger.info(f"Real-time notification would be sent to user {user_id}: {data}")
    
    def _update_user_notification_cache(self, user_id: int):
        """Update user notification count in cache"""
        try:
            unread_count = Bildirim.objects.filter(
                alici_kullanici_id=user_id,
                okundu_mu=False
            ).count()
            
            cache.set(f'user_notification_count_{user_id}', unread_count, 300)  # 5 minutes
        except Exception as e:
            logger.error(f"Failed to update notification cache for user {user_id}: {str(e)}")


class NotificationService(BaseService):
    """Service for notification-related business operations."""
    
    def send_notification(self, data: Dict) -> ServiceResult:
        """Send a notification to a user."""
        required_fields = ['alici_kullanici_id', 'mesaj']
        validation = self.validate_input(data, required_fields)
        
        if not validation:
            return validation
        
        try:
            # Get recipient user
            alici = Kullanici.objects.get(
                id=data['alici_kullanici_id'],
                aktif_mi=True
            )
            
            # Create notification
            bildirim = Bildirim.objects.create(
                alici_kullanici=alici,
                baslik=data.get('baslik', 'Bildirim'),
                mesaj=data['mesaj'],
                tur=data.get('tur', 'GENEL'),
                oncelik=data.get('oncelik', 'NORMAL'),
                hedef_url=data.get('hedef_url'),
                randevu=data.get('randevu'),
                odeme_hareketi=data.get('odeme_hareketi'),
                okundu_mu=False
            )
            
            self.log_operation("Notification sent",
                             bildirim_id=bildirim.id,
                             alici_id=alici.id,
                             tur=data.get('tur', 'GENEL'))
            
            return ServiceResult.success_result(bildirim)
            
        except Kullanici.DoesNotExist:
            return ServiceResult.error_result("Alıcı kullanıcı bulunamadı")
        except Exception as e:
            self.log_error("Send notification", e)
            return ServiceResult.error_result(f"Bildirim gönderilirken hata oluştu: {str(e)}")
    
    def send_bulk_notification(self, data: Dict) -> ServiceResult:
        """Send notification to multiple users."""
        required_fields = ['alici_kullanici_ids', 'mesaj']
        validation = self.validate_input(data, required_fields)
        
        if not validation:
            return validation
        
        try:
            # Get recipient users
            alicilar = Kullanici.objects.filter(
                id__in=data['alici_kullanici_ids'],
                aktif_mi=True
            )
            
            if not alicilar.exists():
                return ServiceResult.error_result("Hiç alıcı kullanıcı bulunamadı")
            
            # Create notifications in bulk
            bildirimler = []
            for alici in alicilar:
                bildirimler.append(
                    Bildirim(
                        alici_kullanici=alici,
                        baslik=data.get('baslik', 'Bildirim'),
                        mesaj=data['mesaj'],
                        tur=data.get('tur', 'GENEL'),
                        oncelik=data.get('oncelik', 'NORMAL'),
                        hedef_url=data.get('hedef_url'),
                        randevu=data.get('randevu'),
                        odeme_hareketi=data.get('odeme_hareketi'),
                        okundu_mu=False
                    )
                )
            
            created_notifications = Bildirim.objects.bulk_create(bildirimler)
            
            self.log_operation("Bulk notification sent",
                             count=len(created_notifications),
                             tur=data.get('tur', 'GENEL'))
            
            return ServiceResult.success_result({
                'created_count': len(created_notifications),
                'notifications': created_notifications
            })
            
        except Exception as e:
            self.log_error("Send bulk notification", e)
            return ServiceResult.error_result(f"Toplu bildirim gönderilirken hata oluştu: {str(e)}")
    
    def mark_as_read(self, bildirim_id: int, user: Kullanici) -> ServiceResult:
        """Mark notification as read."""
        try:
            bildirim = Bildirim.objects.get(
                id=bildirim_id,
                alici_kullanici=user
            )
            
            if not bildirim.okundu_mu:
                bildirim.okundu_mu = True
                bildirim.save()
                
                self.log_operation("Notification marked as read",
                                 bildirim_id=bildirim.id,
                                 user_id=user.id)
            
            return ServiceResult.success_result(bildirim)
            
        except Bildirim.DoesNotExist:
            return ServiceResult.error_result("Bildirim bulunamadı")
        except Exception as e:
            self.log_error("Mark notification as read", e)
            return ServiceResult.error_result("Bildirim okundu olarak işaretlenirken hata oluştu")
    
    def mark_all_as_read(self, user: Kullanici) -> ServiceResult:
        """Mark all user notifications as read."""
        try:
            updated_count = Bildirim.objects.filter(
                alici_kullanici=user,
                okundu_mu=False
            ).update(okundu_mu=True)
            
            self.log_operation("All notifications marked as read",
                             user_id=user.id,
                             updated_count=updated_count)
            
            return ServiceResult.success_result({
                'updated_count': updated_count
            })
            
        except Exception as e:
            self.log_error("Mark all notifications as read", e)
            return ServiceResult.error_result("Tüm bildirimler okundu olarak işaretlenirken hata oluştu")
    
    def get_user_notifications(self, user: Kullanici, unread_only: bool = False) -> ServiceResult:
        """Get user's notifications."""
        try:
            notifications = Bildirim.objects.filter(alici_kullanici=user)
            
            if unread_only:
                notifications = notifications.filter(okundu_mu=False)
            
            notifications = notifications.order_by('-tarih')
            
            return ServiceResult.success_result(notifications)
            
        except Exception as e:
            self.log_error("Get user notifications", e)
            return ServiceResult.error_result("Bildirimler alınırken hata oluştu")
    
    def delete_notification(self, bildirim_id: int, user: Kullanici) -> ServiceResult:
        """Delete a notification."""
        try:
            bildirim = Bildirim.objects.get(
                id=bildirim_id,
                alici_kullanici=user
            )
            
            bildirim.delete()
            
            self.log_operation("Notification deleted",
                             bildirim_id=bildirim_id,
                             user_id=user.id)
            
            return ServiceResult.success_result()
            
        except Bildirim.DoesNotExist:
            return ServiceResult.error_result("Bildirim bulunamadı")
        except Exception as e:
            self.log_error("Delete notification", e)
            return ServiceResult.error_result("Bildirim silinirken hata oluştu")