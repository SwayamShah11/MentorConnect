from random import choices

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser, BaseUserManager
from PIL import Image
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime
from django.urls import reverse
from django.utils.timezone import now


class User(AbstractUser):
    is_mentee = models.BooleanField(default=False)
    is_mentor = models.BooleanField(default=False)


class UserInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    interest = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.user.username


class Mentee(models.Model):
    """Mentee models"""

    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)

    # interests = models.OneToOneField(Subject, related_name='mentees', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.user.username


class Mentor(models.Model):
    """Mentor models"""

    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)

    # interests = models.OneToOneField(Subject, related_name='mentors', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.user.username

class Profile(models.Model):
    """Extended Profile Model"""

    SEMESTER_CHOICES = [
        ('I', 'I'),
        ('II', 'II'),
        ('III', 'III'),
        ('IV', 'IV'),
        ('V', 'V'),
        ('VI', 'VI'),
        ('VII', 'VII'),
        ('VIII', 'VIII'),
    ]

    YEAR_CHOICES = [
        ('FE', 'FE'),  # First Year
        ('SE', 'SE'),  # Second Year
        ('TE', 'TE'),  # Third Year
        ('BE', 'BE'),  # Final Year
    ]

    BRANCH_CHOICES = [
        ('IT', 'Information Technology'),
        ('CSE', 'Computer Science'),
        ('AIML', 'Computer Science - Artificial Intelligence & Machine Learning'),
        ('DS', 'Computer Science - Data Science'),
        ('EXTC', 'Electronics & Telecommunication'),
        ('EEE', 'Electrical & Electronics'),
        ('ME', 'Mechanical Engineering'),
        ('CE', 'Civil Engineering'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')

    # --- Personal Details ---
    moodle_id = models.CharField(max_length=20, blank=True, null=True)
    student_name = models.CharField(max_length=200, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES, blank=True, null=True)
    year = models.CharField(max_length=10, choices=YEAR_CHOICES, blank=True, null=True)
    branch = models.CharField(max_length=100, choices=BRANCH_CHOICES, blank=True, null=True)
    career_domain = models.CharField(max_length=200, blank=True)

    address = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    hobby = models.TextField(blank=True, null=True)
    about_me = models.TextField(blank=True, null=True)

    # --- Family Details ---
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    mother_occupation = models.CharField(max_length=100, blank=True, null=True)
    mother_contact = models.CharField(max_length=15, blank=True, null=True)

    father_name = models.CharField(max_length=100, blank=True, null=True)
    father_occupation = models.CharField(max_length=100, blank=True, null=True)
    father_contact = models.CharField(max_length=15, blank=True, null=True)

    sibling1_name = models.CharField(max_length=100, blank=True, null=True)
    sibling2_name = models.CharField(max_length=100, blank=True, null=True)


    def __str__(self):
        if self.user:
            return f"{self.user.username}'s Profile"
        return "Profile (no user)"

    def save(self, **kwargs):
        super().save()
        img = Image.open(self.image.path)

        if img.height > 300 or img.width > 300:
            output_size = (300, 300)
            img.thumbnail(output_size)
            img.save(self.image.path)

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, moodle_id=instance.username)  # 👈 auto set moodle_id

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()


class InternshipPBL(models.Model):
    SEMESTER = [
        ('I', 'I'), ('II', 'II'), ('III', 'III'), ('IV', 'IV'),
        ('V', 'V'), ('VI', 'VI'), ('VII', 'VII'), ('VIII', 'VIII'),
    ]

    TYPE_CHOICES = [
        ("Internship in Industry", "Internship in Industry"),
        ("Internship through APSIT SKILLS Platform", "Internship through APSIT SKILLS Platform"),
        ("Internship through AICTE Virtual Internship Platform", "Internship through AICTE Virtual Internship Platform"),
        ("PBL", "PBL"),
        ("Other", "Other"),
    ]

    AY = [
        ('2017-18', '2017-18'),
        ('2018-19', '2018-19'),
        ('2019-20', '2019-20'),
        ('2020-21', '2020-21'),
        ('2021-22', '2021-22'),
        ('2022-23', '2022-23'),
        ('2023-24', '2023-24'),
        ('2024-25', '2024-25'),
        ('2025-26', '2025-26'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    type = models.CharField(max_length=200, choices=TYPE_CHOICES, blank=True, null=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    details = models.TextField(max_length=500, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    no_of_days = models.IntegerField(blank=True, null=True)
    certificate = models.FileField(upload_to="certificates/", blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            delta = (self.end_date - self.start_date).days + 1
            self.no_of_days = delta if delta > 0 else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.academic_year})"


class Project(models.Model):
    SEMESTER_CHOICES = [
        ("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV"),
        ("V", "V"), ("VI", "VI"), ("VII", "VII"), ("VIII", "VIII"),
    ]
    TYPE_CHOICES = [
        ("Mini Project", "Mini Project"),
        ("Major Project", "Major Project"),
        ("Research", "Research"),
        ("Other", "Other"),
    ]
    AY = [
        ('2017-18', '2017-18'),
        ('2018-19', '2018-19'),
        ('2019-20', '2019-20'),
        ('2020-21', '2020-21'),
        ('2021-22', '2021-22'),
        ('2022-23', '2022-23'),
        ('2023-24', '2023-24'),
        ('2024-25', '2024-25'),
        ('2025-26', '2025-26'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES, blank=True, null=True)
    project_type = models.CharField(max_length=50, choices=TYPE_CHOICES, blank=True, null=True)
    details = models.TextField(max_length=1000, blank=True, null=True)
    guide_name = models.CharField(max_length=100, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Reply(models.Model):
    """Reply Model"""

    sender = models.ForeignKey(User, related_name="sender2", on_delete=models.CASCADE, null=True)
    reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    conversation = models.ForeignKey('Conversation', related_name='replies', on_delete=models.CASCADE)

    def __str__(self):
        return "From {}, in {}".format(self.sender.username, self.conversation)

    def save(self, *args, **kwargs):
        if self.reply and self.replied_at is None:
            self.replied_at = now()

        super(Reply, self).save(*args, **kwargs)


class Conversation(models.Model):
    """Conversation Model"""

    sender = models.ForeignKey(User, related_name="sender1", on_delete=models.CASCADE, null=True)
    receipient = models.ForeignKey(User, related_name="receipient1", on_delete=models.CASCADE)
    conversation = models.TextField(max_length=100)
    sent_at = models.DateTimeField(null=True, blank=True)

    # reply = models.TextField(blank=True, null=True)
    # replied_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-sent_at']

    @property
    def get_replies(self):
        return self.replies.all()

    def __str__(self):
        return "From {}, to {}".format(self.sender.username, self.receipient.username)

    def save(self, *args, **kwargs):
        if not self.id:
            self.sent_at = timezone.now()

        # if (self.reply and self.replied_at is None):
        # self.replied_at = now()

        super(Conversation, self).save(*args, **kwargs)


class Msg(models.Model):
    """Message Model"""

    sender = models.ForeignKey(User, related_name="sender", on_delete=models.CASCADE, null=True)
    receipient = models.ForeignKey(User, related_name="receipient", on_delete=models.CASCADE)
    msg_content = models.TextField(max_length=100)
    sent_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    comment_at = models.DateTimeField(blank=True, null=True)
    is_approved = models.BooleanField(default=False, verbose_name="Approve?")
    date_approved = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "From {}, to {}".format(self.sender.username, self.receipient.username)

    def save(self, *args, **kwargs):
        if not self.id:
            self.sent_at = timezone.now()

        if self.comment and self.date_approved is None:
            self.date_approved = now()

        if self.comment and self.comment_at is None:
            self.comment_at = now()

        super(Msg, self).save(*args, **kwargs)

    class Meta:
        ordering = ['-sent_at']
