"""
Email utilities using Resend API
"""
import os
import requests
from django.conf import settings
from django.urls import reverse


def send_gift_email(gift_purchase):
    """
    Send gift notification email using Resend API
    
    Args:
        gift_purchase: GiftPurchase instance
        
    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    
    if not resend_api_key:
        return {
            'success': False,
            'message': 'RESEND_API_KEY not configured'
        }
    
    # Build redemption URL
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if not domain.startswith('http'):
        domain = f"https://{domain}" if not settings.DEBUG else f"http://{domain}"
    
    redemption_url = f"{domain}/gift/redeem/{gift_purchase.gift_token}/"
    
    # Email content
    purchaser_name = gift_purchase.purchaser.get_full_name() or gift_purchase.purchaser.username
    recipient_name = gift_purchase.recipient_name or gift_purchase.recipient_email.split('@')[0]
    course_name = gift_purchase.course.name
    
    subject = f"🎁 You've received a gift: {course_name}!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #52A8B5; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .message-box {{ background: white; padding: 20px; border-left: 4px solid #52A8B5; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎁 You've Received a Gift!</h1>
            </div>
            <div class="content">
                <p>Hi {recipient_name},</p>
                
                <p><strong>{purchaser_name}</strong> has gifted you access to:</p>
                
                <h2 style="color: #52A8B5;">{course_name}</h2>
                
                {f'<div class="message-box"><p><em>"{gift_purchase.gift_message}"</em></p><p style="text-align: right; margin-top: 10px;">— {purchaser_name}</p></div>' if gift_purchase.gift_message else ''}
                
                <p>Click the button below to claim your gift and start learning:</p>
                
                <div style="text-align: center;">
                    <a href="{redemption_url}" class="button">Claim Your Gift</a>
                </div>
                
                <p style="margin-top: 30px; font-size: 14px; color: #666;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{redemption_url}" style="color: #52A8B5; word-break: break-all;">{redemption_url}</a>
                </p>
                
                {f'<p style="font-size: 12px; color: #999; margin-top: 20px;">This gift expires on {gift_purchase.expires_at.strftime("%B %d, %Y")}.</p>' if gift_purchase.expires_at else ''}
            </div>
            <div class="footer">
                <p>This gift was sent from {domain}</p>
                <p>If you didn't expect this email, you can safely ignore it.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send via Resend API
    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': resend_from,
                'to': [gift_purchase.recipient_email],
                'reply_to': resend_reply_to,
                'subject': subject,
                'html': html_content,
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': 'Gift email sent successfully',
                'email_id': response.json().get('id')
            }
        else:
            return {
                'success': False,
                'message': f'Resend API error: {response.status_code} - {response.text}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }


def send_teacher_request_email(teacher_request):
    """
    Send confirmation email to teacher applicant
    
    Args:
        teacher_request: TeacherRequest instance
        
    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    
    if not resend_api_key:
        return {
            'success': False,
            'message': 'RESEND_API_KEY not configured'
        }
    
    subject = "🎓 Teacher Registration Request Received"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .message-box {{ background: white; padding: 20px; border-left: 4px solid #52A8B5; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎓 Thank You for Your Interest!</h1>
            </div>
            <div class="content">
                <p>Hi {teacher_request.first_name},</p>
                
                <p>Thank you for applying to become a teacher on our platform! We have received your registration request and our team will review it shortly.</p>
                
                <div class="message-box">
                    <p><strong>What happens next?</strong></p>
                    <p>Our admin team will carefully review your application, including your qualifications, teaching experience, and motivation. We will send you an email with our decision shortly.</p>
                </div>
                
                <p>We appreciate your patience and look forward to potentially welcoming you to our teaching community!</p>
                
                <p>Best regards,<br>The Teaching Team</p>
            </div>
            <div class="footer">
                <p>This is an automated confirmation email. Please do not reply to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send via Resend API
    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': resend_from,
                'to': [teacher_request.email],
                'reply_to': resend_reply_to,
                'subject': subject,
                'html': html_content,
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': 'Teacher request confirmation email sent successfully',
                'email_id': response.json().get('id')
            }
        else:
            return {
                'success': False,
                'message': f'Resend API error: {response.status_code} - {response.text}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }


def notify_admin_teacher_request(teacher_request):
    """
    Notify admins about a new teacher registration request
    
    Args:
        teacher_request: TeacherRequest instance
        
    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    
    if not resend_api_key:
        return {
            'success': False,
            'message': 'RESEND_API_KEY not configured'
        }
    
    # Get admin emails
    from django.contrib.auth.models import User
    admin_emails = list(User.objects.filter(is_staff=True, is_superuser=True).values_list('email', flat=True))
    
    if not admin_emails:
        return {
            'success': False,
            'message': 'No admin emails found'
        }
    
    # Build admin URL
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if not domain.startswith('http'):
        domain = f"https://{domain}" if not settings.DEBUG else f"http://{domain}"
    
    admin_url = f"{domain}/dashboard/teacher-requests/"
    
    subject = f"🎓 New Teacher Registration Request: {teacher_request.first_name} {teacher_request.last_name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .info-box {{ background: white; padding: 15px; margin: 15px 0; border-left: 4px solid #52A8B5; }}
            .button {{ display: inline-block; background: #52A8B5; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎓 New Teacher Request</h1>
            </div>
            <div class="content">
                <p>A new teacher registration request has been submitted:</p>
                
                <div class="info-box">
                    <p><strong>Name:</strong> {teacher_request.first_name} {teacher_request.last_name}</p>
                    <p><strong>Email:</strong> {teacher_request.email}</p>
                    <p><strong>Phone:</strong> {teacher_request.phone or 'Not provided'}</p>
                    <p><strong>Languages:</strong> {teacher_request.languages_spoken}</p>
                </div>
                
                <p><strong>Bio:</strong><br>{teacher_request.bio[:200]}...</p>
                
                <div style="text-align: center;">
                    <a href="{admin_url}" class="button">Review Request</a>
                </div>
            </div>
            <div class="footer">
                <p>Please review this request in the admin dashboard.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send via Resend API
    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': resend_from,
                'to': admin_emails,
                'reply_to': resend_reply_to,
                'subject': subject,
                'html': html_content,
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': 'Admin notification sent successfully',
                'email_id': response.json().get('id')
            }
        else:
            return {
                'success': False,
                'message': f'Resend API error: {response.status_code} - {response.text}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }


def send_teacher_approval_email(teacher_request):
    """Send approval email to teacher"""
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    
    if not resend_api_key:
        return {'success': False, 'message': 'RESEND_API_KEY not configured'}
    
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if not domain.startswith('http'):
        domain = f"https://{domain}" if not settings.DEBUG else f"http://{domain}"
    
    login_url = f"{domain}/login/"
    subject = "🎓 Congratulations! Your Teacher Application Has Been Approved"
    
    html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Arial,sans-serif;line-height:1.6;color:#333}}.container{{max-width:600px;margin:0 auto;padding:20px}}.header{{background:linear-gradient(135deg,#52A8B5 0%,#4492B3 100%);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0}}.content{{background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px}}.button{{display:inline-block;background:#52A8B5;color:white;padding:15px 30px;text-decoration:none;border-radius:5px;margin:20px 0}}.message-box{{background:white;padding:20px;border-left:4px solid #2C9F5F;margin:20px 0}}.footer{{text-align:center;margin-top:30px;color:#666;font-size:12px}}</style></head><body><div class="container"><div class="header"><h1>🎓 Welcome to Our Teaching Team!</h1></div><div class="content"><p>Hi {teacher_request.first_name},</p><div class="message-box"><p><strong>Great news!</strong> Your teacher application has been approved!</p><p>We're excited to welcome you to our teaching community. You can now log in and start creating courses and live sessions.</p></div><p>Click the button below to log in and access your teacher dashboard:</p><div style="text-align:center;"><a href="{login_url}" class="button">Log In to Teacher Dashboard</a></div><p>If you have any questions or need assistance, please don't hesitate to reach out to our support team.</p><p>Best regards,<br>The Teaching Team</p></div><div class="footer"><p>This is an automated email. Please do not reply to this message.</p></div></div></body></html>"""
    
    try:
        response = requests.post('https://api.resend.com/emails', headers={'Authorization': f'Bearer {resend_api_key}', 'Content-Type': 'application/json'}, json={'from': resend_from, 'to': [teacher_request.email], 'reply_to': resend_reply_to, 'subject': subject, 'html': html_content}, timeout=10)
        if response.status_code == 200:
            return {'success': True, 'message': 'Teacher approval email sent successfully', 'email_id': response.json().get('id')}
        else:
            return {'success': False, 'message': f'Resend API error: {response.status_code} - {response.text}'}
    except Exception as e:
        return {'success': False, 'message': f'Error sending email: {str(e)}'}


def send_teacher_rejection_email(teacher_request, rejection_reason=''):
    """Send rejection email to teacher"""
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    
    if not resend_api_key:
        return {'success': False, 'message': 'RESEND_API_KEY not configured'}
    
    subject = "Teacher Application Update"
    html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Arial,sans-serif;line-height:1.6;color:#333}}.container{{max-width:600px;margin:0 auto;padding:20px}}.header{{background:linear-gradient(135deg,#52A8B5 0%,#4492B3 100%);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0}}.content{{background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px}}.message-box{{background:white;padding:20px;border-left:4px solid #DE604D;margin:20px 0}}.footer{{text-align:center;margin-top:30px;color:#666;font-size:12px}}</style></head><body><div class="container"><div class="header"><h1>Teacher Application Update</h1></div><div class="content"><p>Hi {teacher_request.first_name},</p><p>Thank you for your interest in teaching on our platform. After careful review, we regret to inform you that we are unable to approve your application at this time.</p>{f'<div class="message-box"><p><strong>Note:</strong> {rejection_reason}</p></div>' if rejection_reason else ''}<p>We encourage you to continue developing your teaching skills and consider reapplying in the future.</p><p>Best regards,<br>The Teaching Team</p></div><div class="footer"><p>This is an automated email. Please do not reply to this message.</p></div></div></body></html>"""
    
    try:
        response = requests.post('https://api.resend.com/emails', headers={'Authorization': f'Bearer {resend_api_key}', 'Content-Type': 'application/json'}, json={'from': resend_from, 'to': [teacher_request.email], 'reply_to': resend_reply_to, 'subject': subject, 'html': html_content}, timeout=10)
        if response.status_code == 200:
            return {'success': True, 'message': 'Teacher rejection email sent successfully', 'email_id': response.json().get('id')}
        else:
            return {'success': False, 'message': f'Resend API error: {response.status_code} - {response.text}'}
    except Exception as e:
        return {'success': False, 'message': f'Error sending email: {str(e)}'}
