"""
Auto-linking signals for CRM Lead Management
Automatically links enrollments and gifts to leads based on email/user matching
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    Lead,
    LeadTimeline,
    LeadEnrollmentLink,
    LeadGiftLink,
    CourseEnrollment,
    GiftPurchase,
)


@receiver(post_save, sender=CourseEnrollment)
def auto_link_enrollment_to_lead(sender, instance, created, **kwargs):
    """Automatically link enrollment to lead if email/user matches"""
    if not created:
        return
    
    lead = None
    
    # Try to find lead by linked_user
    if instance.user:
        try:
            lead = Lead.objects.get(linked_user=instance.user)
        except Lead.DoesNotExist:
            # Try to find by email
            try:
                lead = Lead.objects.get(email=instance.user.email)
                # Auto-link user if found by email
                if not lead.linked_user:
                    lead.linked_user = instance.user
                    lead.save()
            except Lead.DoesNotExist:
                pass
    
    # If lead found, create link
    if lead:
        link, created_link = LeadEnrollmentLink.objects.get_or_create(
            lead=lead,
            enrollment=instance,
            defaults={'created_by': instance.user}
        )
        
        if created_link:
            # Create timeline event
            LeadTimeline.objects.create(
                lead=lead,
                event_type='ENROLLMENT_CREATED',
                actor=instance.user,
                description=f"Enrollment created in {instance.course.name}",
                metadata={'enrollment_id': instance.id, 'course_id': instance.course.id}
            )
            
            # Auto-link enrollment to lead
            LeadTimeline.objects.create(
                lead=lead,
                event_type='ENROLLMENT_LINKED_TO_LEAD',
                actor=instance.user,
                description=f"Enrollment in {instance.course.name} automatically linked to lead",
                metadata={'enrollment_id': instance.id, 'auto_linked': True}
            )
            
            # Update lead status to enrolled if not already
            if lead.status != 'enrolled':
                old_status = lead.status
                lead.status = 'enrolled'
                lead.updated_at = timezone.now()
                lead.save()
                
                LeadTimeline.objects.create(
                    lead=lead,
                    event_type='LEAD_STATUS_CHANGED',
                    actor=instance.user,
                    description=f"Status automatically changed from {old_status} to enrolled (enrollment created)",
                    metadata={'old_status': old_status, 'new_status': 'enrolled', 'auto_changed': True}
                )


@receiver(post_save, sender=GiftPurchase)
def auto_link_gift_to_lead(sender, instance, created, **kwargs):
    """Automatically create lead from gift and link gift to lead"""
    if not created:
        return
    
    lead = None
    
    # Try to find existing lead by recipient email
    try:
        lead = Lead.objects.get(email=instance.recipient_email)
    except Lead.DoesNotExist:
        # Create new lead from gift data
        lead = Lead.objects.create(
            first_name=instance.recipient_name.split()[0] if instance.recipient_name else 'Gift',
            last_name=' '.join(instance.recipient_name.split()[1:]) if instance.recipient_name and len(instance.recipient_name.split()) > 1 else 'Recipient',
            email=instance.recipient_email,
            source='referral',  # Gift purchases are often referrals
            status='new',
            notes=f"Auto-created from gift purchase by {instance.purchaser.username}",
        )
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='LEAD_CREATED',
            actor=instance.purchaser,
            description=f"Lead auto-created from gift purchase",
            metadata={'gift_id': instance.id, 'purchaser_id': instance.purchaser.id, 'auto_created': True}
        )
    
    # Link gift to lead
    link, created_link = LeadGiftLink.objects.get_or_create(
        lead=lead,
        gift=instance,
        defaults={'created_by': instance.purchaser}
    )
    
    if created_link:
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='GIFT_LINKED_TO_LEAD',
            actor=instance.purchaser,
            description=f"Gift for {instance.course.name} automatically linked to lead",
            metadata={'gift_id': instance.id, 'course_id': instance.course.id, 'auto_linked': True}
        )

