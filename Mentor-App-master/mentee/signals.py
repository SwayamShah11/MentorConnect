from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile, MentorMenteeInteraction
from .ai_utils import generate_ai_summary


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, moodleID=instance.username, email=instance.email)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=MentorMenteeInteraction)
def generate_summary(sender, instance, created, **kwargs):
    if instance.agenda and not instance.ai_summary:
        instance.ai_summary = generate_ai_summary(instance.agenda)
        instance.save(update_fields=["ai_summary"])