"""
Email service for sending various types of emails
"""
import logging
from typing import List, Dict, Optional
from django.core.mail import send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class EmailService:
    """Comprehensive email service"""
    
    @staticmethod
    def send_welcome_email(user):
        """Hoş geldin e-postası gönder"""
        try:
            subject = f"Hoş geldiniz {user.ad}!"
            
            context = {
                'user': user,
                'platform_name': 'Diyetlenio'
            }
            
            html_message = render_to_string('emails/welcome.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.e_posta],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Welcome email sending failed for {user.e_posta}: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_confirmation(randevu):
        """Randevu onay e-postası gönder"""
        try:
            subject = "Randevunuz Onaylandı!"
            
            context = {
                'randevu': randevu,
                'danisan': randevu.danisan,
                'diyetisyen': randevu.diyetisyen
            }
            
            html_message = render_to_string('emails/appointment_confirmed.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[randevu.danisan.e_posta],
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Appointment confirmation email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_reminder(randevu):
        """Randevu hatırlatma e-postası"""
        try:
            subject = "Randevu Hatırlatması"
            
            context = {
                'randevu': randevu,
                'danisan': randevu.danisan,
                'diyetisyen': randevu.diyetisyen
            }
            
            html_message = render_to_string('emails/appointment_reminder.html', context)
            plain_message = strip_tags(html_message)
            
            # Hem danışana hem diyetisyene gönder
            recipients = [randevu.danisan.e_posta, randevu.diyetisyen.kullanici.e_posta]
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Appointment reminder email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_cancellation(randevu):
        """Randevu iptal e-postası"""
        try:
            subject = "Randevu İptal Edildi"
            
            context = {
                'randevu': randevu,
                'reason': randevu.iptal_nedeni
            }
            
            html_message = render_to_string('emails/appointment_cancelled.html', context)
            plain_message = strip_tags(html_message)
            
            # Hem danışana hem diyetisyene gönder
            recipients = [randevu.danisan.e_posta, randevu.diyetisyen.kullanici.e_posta]
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Appointment cancellation email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_payment_confirmation(odeme_hareketi):
        """Ödeme onay e-postası"""
        try:
            subject = "Ödemeniz Başarıyla İşlendi"
            
            context = {
                'odeme': odeme_hareketi,
                'danisan': odeme_hareketi.danisan
            }
            
            html_message = render_to_string('emails/payment_confirmed.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[odeme_hareketi.danisan.e_posta],
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Payment confirmation email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_dietitian_approval(diyetisyen):
        """Diyetisyen onay e-postası"""
        try:
            subject = "Diyetisyen Başvurunuz Onaylandı!"
            
            context = {
                'diyetisyen': diyetisyen,
                'login_url': f"{settings.SITE_URL}/login/"
            }
            
            html_message = render_to_string('emails/dietitian_approved.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[diyetisyen.kullanici.e_posta],
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Dietitian approval email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_bulk_email(recipients: List[str], subject: str, message: str, html_message: str = None):
        """Toplu e-posta gönder"""
        try:
            if not recipients:
                return False
            
            if html_message is None:
                html_message = message
            
            return send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Bulk email sending failed: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_email(user, reset_url):
        """Şifre sıfırlama e-postası"""
        try:
            subject = "Şifre Sıfırlama Talebi"
            
            context = {
                'user': user,
                'reset_url': reset_url
            }
            
            html_message = render_to_string('emails/password_reset.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.e_posta],
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Password reset email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_diet_plan_email(diyet_listesi):
        """Diyet listesi e-postası"""
        try:
            subject = "Yeni Diyet Planınız Hazır!"
            
            context = {
                'diyet_listesi': diyet_listesi,
                'danisan': diyet_listesi.danisan,
                'diyetisyen': diyet_listesi.diyetisyen
            }
            
            html_message = render_to_string('emails/diet_plan.html', context)
            plain_message = strip_tags(html_message)
            
            return send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[diyet_listesi.danisan.e_posta],
                html_message=html_message
            )
        except Exception as e:
            logger.error(f"Diet plan email failed: {str(e)}")
            return False
    
    @staticmethod
    def send_admin_notification(subject: str, message: str):
        """Admin'e bildirim e-postası"""
        try:
            admin_emails = getattr(settings, 'ADMIN_EMAIL_LIST', ['admin@diyetlenio.com'])
            
            return send_mail(
                subject=f"[Diyetlenio Admin] {subject}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails
            )
        except Exception as e:
            logger.error(f"Admin notification email failed: {str(e)}")
            return False


class EmailTemplateService:
    """Email template management service"""
    
    @staticmethod
    def validate_template(template_name: str) -> bool:
        """Template'in varlığını kontrol et"""
        try:
            render_to_string(template_name, {})
            return True
        except:
            return False
    
    @staticmethod
    def get_template_context(template_type: str, **kwargs) -> Dict:
        """Template için context oluştur"""
        base_context = {
            'site_name': 'Diyetlenio',
            'site_url': getattr(settings, 'SITE_URL', 'https://diyetlenio.com'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'destek@diyetlenio.com')
        }
        
        base_context.update(kwargs)
        return base_context


class EmailQueue:
    """Email queue management for better performance"""
    
    def __init__(self):
        self.queue = []
    
    def add_to_queue(self, email_data: Dict):
        """E-postayı kuyruğa ekle"""
        self.queue.append(email_data)
    
    def process_queue(self):
        """Kuyruktaki e-postaları işle"""
        success_count = 0
        failed_count = 0
        
        for email_data in self.queue:
            try:
                result = send_mail(**email_data)
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Email queue processing failed: {str(e)}")
                failed_count += 1
        
        self.queue.clear()
        return success_count, failed_count