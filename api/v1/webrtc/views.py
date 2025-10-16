"""
WebRTC API Views for video calling
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

from core.services.webrtc_service import WebRTCService
from core.permissions import PermissionChecker, UserRole


@extend_schema(
    summary="Initiate WebRTC Call",
    description="Start a new video call between users",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'callee_id': {'type': 'integer', 'description': 'ID of user to call'},
                'call_type': {'type': 'string', 'enum': ['appointment', 'emergency', 'consultation', 'admin_support']},
                'randevu_id': {'type': 'integer', 'description': 'Optional appointment ID', 'nullable': True}
            },
            'required': ['callee_id']
        }
    },
    responses={
        201: OpenApiResponse(description="Call initiated successfully"),
        400: OpenApiResponse(description="Invalid request data"),
        403: OpenApiResponse(description="Permission denied")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_call(request):
    """Initiate a WebRTC video call"""
    webrtc_service = WebRTCService()
    
    data = {
        'caller_id': request.user.id,
        'callee_id': request.data.get('callee_id'),
        'call_type': request.data.get('call_type', 'consultation'),
        'randevu_id': request.data.get('randevu_id')
    }
    
    result = webrtc_service.initiate_call(data)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Join WebRTC Call",
    description="Join an existing video call",
    responses={
        200: OpenApiResponse(description="Successfully joined call"),
        404: OpenApiResponse(description="Call not found"),
        403: OpenApiResponse(description="Permission denied")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_call(request, call_id):
    """Join an existing WebRTC call"""
    webrtc_service = WebRTCService()
    
    result = webrtc_service.join_call(call_id, request.user.id)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Send WebRTC Offer",
    description="Send WebRTC offer to peer",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'offer': {
                    'type': 'object',
                    'description': 'WebRTC SDP offer',
                    'properties': {
                        'type': {'type': 'string'},
                        'sdp': {'type': 'string'}
                    }
                }
            },
            'required': ['offer']
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_offer(request, call_id):
    """Send WebRTC offer"""
    webrtc_service = WebRTCService()
    
    offer = request.data.get('offer')
    if not offer:
        return Response({
            'error': 'Offer is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = webrtc_service.handle_offer(call_id, request.user.id, offer)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Send WebRTC Answer",
    description="Send WebRTC answer to peer",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'answer': {
                    'type': 'object',
                    'description': 'WebRTC SDP answer',
                    'properties': {
                        'type': {'type': 'string'},
                        'sdp': {'type': 'string'}
                    }
                }
            },
            'required': ['answer']
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_answer(request, call_id):
    """Send WebRTC answer"""
    webrtc_service = WebRTCService()
    
    answer = request.data.get('answer')
    if not answer:
        return Response({
            'error': 'Answer is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = webrtc_service.handle_answer(call_id, request.user.id, answer)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Send ICE Candidate",
    description="Send ICE candidate to peer",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'candidate': {
                    'type': 'object',
                    'description': 'ICE candidate data'
                }
            },
            'required': ['candidate']
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_ice_candidate(request, call_id):
    """Send ICE candidate"""
    webrtc_service = WebRTCService()
    
    candidate = request.data.get('candidate')
    if not candidate:
        return Response({
            'error': 'Candidate is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = webrtc_service.handle_ice_candidate(call_id, request.user.id, candidate)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="End WebRTC Call",
    description="End an active video call",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'description': 'Reason for ending call'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_call(request, call_id):
    """End WebRTC call"""
    webrtc_service = WebRTCService()
    
    reason = request.data.get('reason')
    result = webrtc_service.end_call(call_id, request.user.id, reason)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Get Call Status",
    description="Get current status of a video call",
    responses={
        200: OpenApiResponse(description="Call status retrieved"),
        404: OpenApiResponse(description="Call not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_call_status(request, call_id):
    """Get call status"""
    webrtc_service = WebRTCService()
    
    result = webrtc_service.get_call_status(call_id, request.user.id)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Emergency Call",
    description="Initiate emergency call to available admin/dietitian",
    responses={
        201: OpenApiResponse(description="Emergency call initiated"),
        503: OpenApiResponse(description="No staff available")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_call(request):
    """Initiate emergency call"""
    webrtc_service = WebRTCService()
    
    # Find available admin or dietitian
    from core.models import Kullanici
    
    # Try to find online admin first
    available_admin = Kullanici.objects.filter(
        rol__rol_adi='admin',
        aktif_mi=True,
        is_staff=True
    ).first()
    
    if not available_admin:
        # Try to find available dietitian
        available_diyetisyen = Kullanici.objects.filter(
            rol__rol_adi='diyetisyen',
            aktif_mi=True
        ).first()
        available_admin = available_diyetisyen
    
    if not available_admin:
        return Response({
            'error': 'Şu anda müsait personel bulunmamaktadır. Lütfen daha sonra tekrar deneyin.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    data = {
        'caller_id': request.user.id,
        'callee_id': available_admin.id,
        'call_type': 'emergency'
    }
    
    result = webrtc_service.initiate_call(data)
    
    if result.is_success:
        return Response(result.data, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'error': result.error_message
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Get WebRTC Configuration",
    description="Get WebRTC configuration including ICE servers",
    responses={
        200: OpenApiResponse(description="Configuration retrieved")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_webrtc_config(request):
    """Get WebRTC configuration"""
    webrtc_service = WebRTCService()
    
    return Response({
        'ice_servers': webrtc_service.ice_servers,
        'constraints': {
            'video': {
                'width': {'min': 640, 'ideal': 1280, 'max': 1920},
                'height': {'min': 480, 'ideal': 720, 'max': 1080},
                'frameRate': {'min': 10, 'ideal': 30, 'max': 60}
            },
            'audio': {
                'echoCancellation': True,
                'noiseSuppression': True,
                'autoGainControl': True
            }
        },
        'settings': {
            'call_timeout': 300,
            'max_participants': 2,
            'recording_enabled': False
        }
    })


# WebSocket-like endpoint for real-time signaling
@csrf_exempt
def webrtc_signaling(request, call_id):
    """Handle WebRTC signaling (would be replaced with WebSocket in production)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            signal_type = data.get('type')
            
            webrtc_service = WebRTCService()
            
            if signal_type == 'offer':
                result = webrtc_service.handle_offer(call_id, request.user.id, data.get('offer'))
            elif signal_type == 'answer':
                result = webrtc_service.handle_answer(call_id, request.user.id, data.get('answer'))
            elif signal_type == 'ice_candidate':
                result = webrtc_service.handle_ice_candidate(call_id, request.user.id, data.get('candidate'))
            else:
                return JsonResponse({'error': 'Invalid signal type'}, status=400)
            
            if result.is_success:
                return JsonResponse(result.data)
            else:
                return JsonResponse({'error': result.error_message}, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)