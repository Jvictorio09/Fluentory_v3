"""
Email utilities using Resend API
"""
import os
import requests
from email.utils import parseaddr, formataddr
from dotenv import load_dotenv
from django.conf import settings
from django.urls import reverse

load_dotenv()


def _resend_emails_endpoint():
    base_url = os.getenv('RESEND_BASE_URL', 'https://api.resend.com').rstrip('/')
    return f'{base_url}/emails'


def _send_resend_email(to_emails, subject, html_content):
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = os.getenv('RESEND_FROM', 'noreply@example.com')
    resend_reply_to = os.getenv('RESEND_REPLY_TO', resend_from)
    resend_from = _normalize_sender_address(resend_from)
    resend_reply_to = _normalize_sender_address(resend_reply_to)

    if not resend_api_key:
        return {
            'success': False,
            'message': 'RESEND_API_KEY not configured'
        }

    try:
        response = requests.post(
            _resend_emails_endpoint(),
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': resend_from,
                'to': to_emails,
                'reply_to': resend_reply_to,
                'subject': subject,
                'html': html_content,
            },
            timeout=10
        )

        if response.status_code in (200, 201, 202):
            return {
                'success': True,
                'message': 'Email sent successfully',
                'email_id': response.json().get('id')
            }
        return {
            'success': False,
            'message': f'Resend API error: {response.status_code} - {response.text}'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }


def _normalize_sender_address(raw_address):
    """
    Normalize sender domain casing for providers that strictly compare domains.
    Example: "Fluentory <noreply@Fluentory.me>" -> "Fluentory <noreply@fluentory.me>"
    """
    display_name, email_addr = parseaddr(raw_address or '')
    if not email_addr or '@' not in email_addr:
        return raw_address
    local_part, domain = email_addr.rsplit('@', 1)
    normalized_email = f'{local_part}@{domain.lower()}'
    if display_name:
        return formataddr((display_name, normalized_email))
    return normalized_email


def _get_public_domain():
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if not domain.startswith('http'):
        domain = f"https://{domain}" if not settings.DEBUG else f"http://{domain}"
    return domain


def send_password_reset_email(user, reset_url):
    """Send password reset email using Resend."""
    if not user.email:
        return {
            'success': False,
            'message': 'User email is missing'
        }

    display_name = user.get_full_name() or user.username or 'there'
    subject = 'Reset your Fluentory password'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 24px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 24px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #52A8B5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
        .note {{ font-size: 12px; color: #666; margin-top: 18px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Password Reset Request</h1>
        </div>
        <div class="content">
          <p>Hi {display_name},</p>
          <p>We received a request to reset your Fluentory password.</p>
          <p>
            <a href="{reset_url}" class="button">Reset Password</a>
          </p>
          <p>If the button does not work, copy and paste this URL into your browser:</p>
          <p><a href="{reset_url}" style="word-break: break-all;">{reset_url}</a></p>
          <p class="note">If you did not request this, you can safely ignore this email.</p>
        </div>
      </div>
    </body>
    </html>
    """
    return _send_resend_email([user.email], subject, html_content)


def send_teacher_invite_email(user, set_password_url, invited_by_name='Admin Team'):
    """Send teacher onboarding invite with first-time password setup link."""
    if not user.email:
        return {
            'success': False,
            'message': 'User email is missing'
        }

    display_name = user.get_full_name() or user.username or 'there'
    subject = 'You are invited to teach on Fluentory'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 24px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 24px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #52A8B5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
        .note {{ font-size: 12px; color: #666; margin-top: 18px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Welcome to Fluentory</h1>
        </div>
        <div class="content">
          <p>Hi {display_name},</p>
          <p>{invited_by_name} invited you to join Fluentory as a teacher.</p>
          <p>To activate your account, create your password using the secure link below:</p>
          <p>
            <a href="{set_password_url}" class="button">Create Your Password</a>
          </p>
          <p>If the button does not work, copy and paste this URL into your browser:</p>
          <p><a href="{set_password_url}" style="word-break: break-all;">{set_password_url}</a></p>
          <p class="note">For your security, this link can expire. If needed, ask an admin to send a new invite.</p>
        </div>
      </div>
    </body>
    </html>
    """
    return _send_resend_email([user.email], subject, html_content)


def send_gift_email(gift_purchase):
    """
    Send gift notification email using Resend API
    
    Args:
        gift_purchase: GiftPurchase instance
        
    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    # Build redemption URL
    domain = _get_public_domain()
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
    
    result = _send_resend_email([gift_purchase.recipient_email], subject, html_content)
    if result.get('success'):
        result['message'] = 'Gift email sent successfully'
    return result


def send_gift_purchaser_confirmation_email(gift_purchase):
    """
    Send purchase confirmation email to the user who gifted the course.
    """
    domain = _get_public_domain()
    purchaser_name = gift_purchase.purchaser.get_full_name() or gift_purchase.purchaser.username
    recipient_name = gift_purchase.recipient_name or gift_purchase.recipient_email
    course_name = gift_purchase.course.name
    status_text = gift_purchase.get_status_display()
    manage_url = f"{domain}{reverse('gift_success', args=[gift_purchase.gift_token])}"

    subject = f"Thank you! Your gift order for {course_name} is confirmed"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 24px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 24px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #52A8B5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
        .box {{ background: white; border-left: 4px solid #52A8B5; padding: 16px; margin: 18px 0; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header"><h1>Thank You for Your Gift Purchase</h1></div>
        <div class="content">
          <p>Hi {purchaser_name},</p>
          <p>Your gift order is confirmed.</p>
          <div class="box">
            <p><strong>Course:</strong> {course_name}</p>
            <p><strong>Recipient:</strong> {recipient_name} ({gift_purchase.recipient_email})</p>
            <p><strong>Status:</strong> {status_text}</p>
          </div>
          <p>You can view this gift anytime from the page below:</p>
          <p><a href="{manage_url}" class="button">Open Gift Thank You Page</a></p>
        </div>
      </div>
    </body>
    </html>
    """

    purchaser_email = (gift_purchase.purchaser.email or '').strip()
    if not purchaser_email:
        return {
            'success': False,
            'message': 'Purchaser email is missing'
        }

    result = _send_resend_email([purchaser_email], subject, html_content)
    if result.get('success'):
        result['message'] = 'Gift purchaser confirmation email sent successfully'
    return result


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


def send_verification_email(user, verify_url):
    """Send an account email-verification link using Resend."""
    if not user.email:
        return {'success': False, 'message': 'User email is missing'}

    display_name = user.get_full_name() or user.username or 'there'
    subject = 'Confirm your email for Fluentory'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 24px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 24px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #52A8B5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
        .note {{ font-size: 12px; color: #666; margin-top: 18px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Confirm your email</h1>
        </div>
        <div class="content">
          <p>Hi {display_name},</p>
          <p>Welcome to Fluentory! Please confirm your email address to activate your account.</p>
          <p>
            <a href="{verify_url}" class="button">Confirm Email</a>
          </p>
          <p>If the button does not work, copy and paste this URL into your browser:</p>
          <p><a href="{verify_url}" style="word-break: break-all;">{verify_url}</a></p>
          <p class="note">This link will expire in a few days. If you did not create a Fluentory account, you can safely ignore this email.</p>
        </div>
      </div>
    </body>
    </html>
    """
    return _send_resend_email([user.email], subject, html_content)


def _contact_inbox():
    """The inbox that should receive contact-form submissions."""
    return os.getenv('CONTACT_INBOX') or os.getenv('RESEND_REPLY_TO') or 'Fluentory.me@gmail.com'


def send_contact_message_email(name, email, subject, message):
    """Send a contact-form submission to the team inbox, with reply-to set to the sender."""
    resend_api_key = os.getenv('RESEND_API_KEY')
    resend_from = _normalize_sender_address(os.getenv('RESEND_FROM', 'noreply@example.com'))

    if not resend_api_key:
        return {'success': False, 'message': 'RESEND_API_KEY not configured'}

    safe_name = (name or 'Website visitor').strip()
    safe_subject = (subject or 'New contact message').strip()
    # Render the message preserving line breaks, escaping handled by caller/templating context.
    body_html = (message or '').replace('\n', '<br>')

    full_subject = f'[Contact] {safe_subject}'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
      <div style="max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#1B3A5C;">New contact form submission</h2>
        <p><strong>Name:</strong> {safe_name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Subject:</strong> {safe_subject}</p>
        <p><strong>Message:</strong></p>
        <div style="background:#f7fafb;border-left:4px solid #2A8FA8;padding:14px 16px;border-radius:6px;">{body_html}</div>
      </div>
    </body>
    </html>
    """

    try:
        response = requests.post(
            _resend_emails_endpoint(),
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': resend_from,
                'to': [_contact_inbox()],
                'reply_to': email,
                'subject': full_subject,
                'html': html_content,
            },
            timeout=10,
        )
        if response.status_code in (200, 201, 202):
            return {'success': True, 'message': 'Contact message sent', 'email_id': response.json().get('id')}
        return {'success': False, 'message': f'Resend API error: {response.status_code} - {response.text}'}
    except Exception as e:
        return {'success': False, 'message': f'Error sending email: {str(e)}'}


def send_course_access_email(user, course, amount=None, currency=None):
    """Send a confirmation email after a user gains access to a course.

    When `amount` is provided the email reads as a purchase receipt; otherwise it
    reads as an enrollment confirmation (free courses).
    """
    if not user or not getattr(user, 'email', ''):
        return {'success': False, 'message': 'User email is missing'}

    display_name = user.get_full_name() or user.username or 'there'
    course_name = getattr(course, 'name', 'your course')
    domain = _get_public_domain()
    try:
        course_url = f"{domain}{reverse('course_detail', kwargs={'course_slug': course.slug})}"
    except Exception:
        course_url = domain
    dashboard_url = f"{domain}/my-dashboard/"

    is_purchase = amount is not None
    if is_purchase:
        subject = f'Your Fluentory purchase is confirmed — {course_name}'
        heading = 'Purchase confirmed 🎉'
        amount_row = (
            f'<p><strong>Amount paid:</strong> {currency or ""} {amount}</p>'
        )
        intro = f'Thank you for your purchase! You now have full access to <strong>{course_name}</strong>.'
    else:
        subject = f"You're enrolled in {course_name} — Fluentory"
        heading = "You're enrolled 🎉"
        amount_row = ''
        intro = f'You now have access to <strong>{course_name}</strong>. Time to start learning!'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #52A8B5 0%, #4492B3 100%); color: white; padding: 24px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 24px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #52A8B5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
        .detail-box {{ background: #fff; border-left: 4px solid #52A8B5; padding: 14px 16px; border-radius: 6px; margin: 16px 0; }}
        .note {{ font-size: 12px; color: #666; margin-top: 18px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>{heading}</h1>
        </div>
        <div class="content">
          <p>Hi {display_name},</p>
          <p>{intro}</p>
          <div class="detail-box">
            <p><strong>Course:</strong> {course_name}</p>
            {amount_row}
          </div>
          <p>
            <a href="{dashboard_url}" class="button">Go to My Dashboard</a>
          </p>
          <p>Or jump straight into the course: <a href="{course_url}">{course_name}</a></p>
          <p class="note">If you have any questions, just reply to this email or contact us at {_contact_inbox()}.</p>
        </div>
      </div>
    </body>
    </html>
    """
    return _send_resend_email([user.email], subject, html_content)
