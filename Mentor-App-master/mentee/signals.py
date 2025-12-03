from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (Profile, Mentor, Mentee, MentorMentee, InternshipPBL, StudentProfileOverview, PaperPublication,
                     SemesterResult, SportsCulturalEvent, CertificationCourse, OtherEvent, MentorMenteeInteraction,
                     Notification, ReminderLog)
from .ai_utils import generate_ai_summary
from django.core.mail import send_mail
from django.conf import settings

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, moodleID=instance.username, email=instance.email)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(post_save, sender=User)
def create_student_profile_overview(sender, instance, created, **kwargs):
    if created:
        StudentProfileOverview.objects.create(user=instance)

@receiver(post_save, sender=MentorMenteeInteraction)
def generate_summary(sender, instance, created, **kwargs):
    if instance.agenda and not instance.ai_summary:
        instance.ai_summary = generate_ai_summary(instance.agenda)
        instance.save(update_fields=["ai_summary"])


def notify_mentors_on_upload(user):
    """
    If there was a reminder in last 30 days, notify mentor that mentee has uploaded something.
    """
    try:
        mentee = Mentee.objects.get(user=user)
    except Mentee.DoesNotExist:
        return

    now = timezone.now()
    cutoff = now - timedelta(days=30)

    # Check if any reminder exists recently
    recent_reminders = ReminderLog.objects.filter(mentee=mentee, last_sent_at__gte=cutoff)

    if not recent_reminders.exists():
        return

    # For all mentors mapped to this mentee, notify
    mappings = MentorMentee.objects.filter(mentee=mentee).select_related("mentor__user")

    for mapping in mappings:
        mentor_user = mapping.mentor.user

        # In-app notification
        Notification.objects.create(
            user=mentor_user,
            message=f"✅ {user.username} - {user.profile.student_name} has uploaded/updated a document after your reminder."
        )

        # Email (optional)
        if mentor_user.email:
            send_mail(
                subject="Mentee Document Update",
                message=(
                    f"Dear {mentor_user.username},\n\n"
                    f"Your mentee {user.username} - {user.profile.student_name} has uploaded/updated a document after your reminder.\n\n"
                    f"Regards,\nMentorConnect Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[mentor_user.email],
                fail_silently=True,
            )


@receiver(post_save, sender=InternshipPBL)
def internship_uploaded(sender, instance, created, **kwargs):
    if instance.certificate:
        notify_mentors_on_upload(instance.user)


@receiver(post_save, sender=SemesterResult)
def marksheet_uploaded(sender, instance, created, **kwargs):
    if instance.marksheet:
        notify_mentors_on_upload(instance.user)


@receiver(post_save, sender=CertificationCourse)
def certcourse_uploaded(sender, instance, created, **kwargs):
    if instance.certificate:
        notify_mentors_on_upload(instance.user)


@receiver(post_save, sender=PaperPublication)
def publication_uploaded(sender, instance, created, **kwargs):
    if instance.certificate:
        notify_mentors_on_upload(instance.user)


@receiver(post_save, sender=SportsCulturalEvent)
def sports_uploaded(sender, instance, created, **kwargs):
    if instance.certificate:
        notify_mentors_on_upload(instance.user)


@receiver(post_save, sender=OtherEvent)
def other_uploaded(sender, instance, created, **kwargs):
    if instance.certificate:
        notify_mentors_on_upload(instance.user)