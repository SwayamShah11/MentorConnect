from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser, BaseUserManager
from PIL import Image
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, timedelta
from django.urls import reverse
from django.utils.timezone import now
import uuid


class User(AbstractUser):
    is_mentee = models.BooleanField(default=False)
    is_mentor = models.BooleanField(default=False)


class Mentee(models.Model):
    """Mentee models"""
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    mentor = models.ForeignKey("Mentor", on_delete=models.SET_NULL, null=True, blank=True, related_name="mentees")

    def __str__(self):
        return self.user.username

DEPARTMENT_CHOICES = [
    ('CIVIL', 'CIVIL'),
    ('COMPS', 'COMPUTER SCIENCE'),
    ('EXTC', 'ELECTRONICS & TELECOMMUNICATION'),
    ('MECH', 'MECHANICAL'),
    ('IT', 'INFORMATION TECHNOLOGY'),
    ('CSE - AIML', 'ARTIFICIAL INTELLIGENCE & MACHINE LEARNING'),
    ('CSE - DS', 'DATA SCIENCE'),
]

class Mentor(models.Model):
    """Mentor models"""
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    image = models.ImageField(default='default.png', upload_to="mentors/", blank=True, null=True)
    name = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=150, choices=DEPARTMENT_CHOICES, blank=True, null=True)
    expertise = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.user.username


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

SEMESTER = [
        ('I', 'I'), ('II', 'II'), ('III', 'III'), ('IV', 'IV'),
        ('V', 'V'), ('VI', 'VI'), ('VII', 'VII'), ('VIII', 'VIII'),
    ]

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
    forget_password_token = models.CharField(max_length=500, blank=True, null=True)
    image = models.ImageField(default='default.png', upload_to='profile_pics')

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
        Profile.objects.create(user=instance, moodle_id=instance.username, email=instance.email)  # 👈 auto set moodle_id

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()


class MentorMentee(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name="mentor_mappings")
    mentee = models.ForeignKey(Mentee, on_delete=models.CASCADE, related_name="mentee_mappings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("mentor", "mentee")

    def __str__(self):
        return f"{self.mentor.user.username} → {self.mentee.user.username}"


class InternshipPBL(models.Model):
    TYPE_CHOICES = [
        ("Internship in Industry", "Internship in Industry"),
        ("Internship through APSIT SKILLS Platform", "Internship through APSIT SKILLS Platform"),
        ("Internship through AICTE Virtual Internship Platform", "Internship through AICTE Virtual Internship Platform"),
        ("PBL", "PBL"),
        ("Other", "Other"),
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
    certificate = models.FileField(upload_to="certificates/internships/", blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            delta = (self.end_date - self.start_date).days + 1
            self.no_of_days = delta if delta > 0 else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.academic_year})"


class Project(models.Model):
    TYPE_CHOICES = [
        ("Mini Project", "Mini Project"),
        ("Major Project", "Major Project"),
        ("Research", "Research"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    project_type = models.CharField(max_length=50, choices=TYPE_CHOICES, blank=True, null=True)
    details = models.TextField(max_length=1000, blank=True, null=True)
    guide_name = models.CharField(max_length=100, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SportsCulturalEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ("Indoor", "Indoor"),
        ("Outdoor", "Outdoor"),
    ]
    LEVEL_CHOICES = [
        ("Inter-College", "Inter-College"),
        ("Intra-College", "Intra-College"),
        ("District", "District"),
        ("State", "State"),
        ("National", "National"),
        ("International", "International"),
        ("Other", "Other"),
    ]
    PRIZE_CHOICES = [
        ("Participation", "Participation"),
        ("1st", "1st"),
        ("2nd", "2nd"),
        ("3rd", "3rd"),
        ("4th", "4th"),
        ("5th", "5th"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    name_of_event = models.CharField(max_length=200, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, blank=True, null=True)
    venue = models.CharField(max_length=500, blank=True, null=True)
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES, blank=True, null=True)
    prize_won = models.CharField(max_length=20, choices=PRIZE_CHOICES, blank=True, null=True)
    certificate = models.FileField(upload_to="sports_cultural_certificates/", null=True, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name_of_event} ({self.academic_year})"


class OtherEvent(models.Model):
    LEVEL_CHOICES = [
        ("College", "College"),
        ("University", "University"),
        ("District", "District"),
        ("State", "State"),
        ("National", "National"),
        ("International", "International"),
        ("Other", "Other"),
    ]
    PRIZE_CHOICES = [
        ("Participation", "Participation"),
        ("1st", "1st"),
        ("2nd", "2nd"),
        ("3rd", "3rd"),
        ("4th", "4th"),
        ("5th", "5th"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    name_of_event = models.CharField(max_length=200, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES, blank=True, null=True)
    details = models.TextField(max_length=1000, blank=True, null=True)
    prize_won = models.CharField(max_length=20, choices=PRIZE_CHOICES, blank=True, null=True)
    amount_won = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    team_members = models.TextField(max_length=500, blank=True, null=True)
    certificate = models.FileField(upload_to="other_event_certificates/", null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name_of_event} ({self.academic_year})"


class CertificationCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    certifying_authority = models.CharField(max_length=100, blank=True, null=True)
    valid_upto = models.CharField(max_length=50, null=True, blank=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    no_of_days = models.PositiveIntegerField(blank=True, null=True)
    domain = models.CharField(max_length=150, blank=True, null=True)
    level = models.CharField(max_length=20, blank=True, null=True)
    amount_reimbursed = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    certificate = models.FileField(upload_to="certificates/courses/", blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PaperPublication(models.Model):
    TYPE_CHOICES = [
        ("Other", "Other"),
        ("Conference", "Conference"),
        ("Journal", "Journal"),
        ("Article", "Article"),
        ("Blog", "Blog"),
    ]

    LEVEL_CHOICES = [
        ("International", "International"),
        ("National", "National"),
        ("State", "State"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    academic_year = models.CharField(max_length=20, choices=AY, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, blank=True, null=True)
    details = models.TextField(max_length=500, blank=True, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True, null=True)
    amount_reimbursed = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    authors = models.TextField(max_length=255, help_text="Comma separated list of authors", blank=True, null=True)
    certificate = models.FileField(upload_to="publications/", blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SelfAssessment(models.Model):
    GOAL_CHOICES = [
        ("To clear A.T.K.T.", "To clear A.T.K.T."),
        ("Competitive Exams", "Competitive Exams"),
        ("Extra Curricular/Co- curricular Activities", "Extra Curricular/Co- curricular Activities"),
        ("Attendance", "Attendance"),
        ("Certification Courses", "Certification Courses"),
        ("Undertaking Projects", "Undertaking Projects"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    goals = models.JSONField(default=list)  # stores multiple goals
    reason = models.TextField(max_length=500, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.semester}"


class LongTermGoal(models.Model):
    PLAN_CHOICES = [
        ('Work', 'Work'),
        ('Post Graduation', 'Post Graduation'),
        ('Entrepreneurship', 'Entrepreneurship'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_plan_display()}"


class SubjectOfInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.username} - {self.subject}"


class EducationalDetail(models.Model):
    EXAM_CHOICES = [
        ("SSC", "SSC"),
        ("HSC", "HSC"),
        ("Diploma", "Diploma"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    examination = models.CharField(max_length=50, choices=EXAM_CHOICES, blank=True, null=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    university_board = models.CharField(max_length=200, blank=True, null=True)
    year_of_passing = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.examination} - {self.user.username}"


class SemesterResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,blank=True, null=True)
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True, null=True)
    pointer = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)  # Example: 9.25
    no_of_kt = models.PositiveIntegerField(default=0, blank=True, null=True)
    marksheet = models.FileField(upload_to="marksheets/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Sem {self.semester}"


class StudentInterest(models.Model):
    INTEREST_CHOICES = [
        # Post BE Exam
        ('gre', 'GRE'),
        ('gate', 'GATE'),
        ('coach', 'GATE/GRE Coaching from College'),
        ('ent', 'Entrepreneur'),
        ('hs', 'Higher Studies'),
        ('place', 'On-campus placements'),

        # Honors/Minors
        ('cyber', 'Cyber Security'),
        ('robotics', 'Robotics'),
        ('struct', 'Professional Practices in Structural Engineering'),
        ('aiml', 'Artificial Intelligence and Machine Learning'),
        ('iot', 'Internet of Things'),

        # Sports
        ('athletics', 'Athletics'),
        ('badminton', 'Badminton'),
        ('table-tennis', 'Table Tennis'),
        ('carrom', 'Carrom'),
        ('chess', 'Chess'),
        ('kabaddi', 'Kabaddi'),
        ('cricket', 'Cricket'),
        ('football', 'Football'),
        ('tug-of-war', 'Tug of War'),
        ('dodgeball', 'Dodgeball'),
        ('volleyball', 'Volleyball'),
        ('throwball', 'Throwball'),
        ('dancing', 'Dancing'),
        ('singing', 'Singing'),

        # Volunteering
        ('volunteer', 'Volunteering'),
        ('leader', 'Leadership'),

        # Clubs
        ('blockchain', 'Blockchain'),
        ('design', 'Design'),
        ('mac', 'MAC Racing Club'),
        ('smart', 'Smart City Club'),
        ('web', 'Web Development'),
        ('software-dev', 'Software Development'),

        # OJUS
        ('design-team', 'OJUS Design Team'),
        ('tech-team', 'OJUS Technical Team'),
        ('creative-team', 'OJUS Creative Team'),
        ('photo-team', 'OJUS Photography Team'),
        ('pub-team', 'OJUS Publicity Team'),
        ('eve-team', 'OJUS Event Team'),

        # Student Council
        ('gen-sec', 'General Secretary'),
        ('gs-associate', 'General Secretary Associate'),
        ('edit-team', 'Editorial Team'),
        ('creative-media-team', 'Creative Media Team'),
        ('sports-sec', 'Sports Secretary'),
        ('cult-sec', 'Cultural Secretary'),
        ('joint-cult-sec', 'Joint Cultural Secretary'),
        ('ladies-rep', 'Ladies Representative'),
        ('joint-ladies-rep', 'Joint Ladies Representative'),

        # Dept Societies
        ('society', 'Department Level Societies'),
    ]

    student = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)  # only 1 entry per user
    interests = models.JSONField(default=list)  # stores multiple interests in one field
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {', '.join(self.interests)}"


class Reply(models.Model):
    """Reply Model"""

    sender = models.ForeignKey(User, related_name="sender2", on_delete=models.CASCADE, null=True)
    reply = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    conversation = models.ForeignKey('Conversation', related_name='replies', on_delete=models.CASCADE)

    def __str__(self):
        return f"From {self.sender.username}, in {self.conversation}"

    def save(self, *args, **kwargs):
        if (self.reply or self.file) and self.replied_at is None:
            self.replied_at = now()
        super().save(*args, **kwargs)


class Conversation(models.Model):
    """Conversation Model"""

    sender = models.ForeignKey(User, related_name="sender1", on_delete=models.CASCADE, null=True)
    receipient = models.ForeignKey(User, related_name="receipient1", on_delete=models.CASCADE)
    conversation = models.TextField(max_length=100)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)

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

        super(Conversation, self).save(*args, **kwargs)


class Msg(models.Model):
    """Message Model"""

    sender = models.ForeignKey(User, related_name="sender", on_delete=models.CASCADE, null=True)
    receipient = models.ForeignKey(User, related_name="receipient", on_delete=models.CASCADE)
    msg_content = models.TextField(max_length=100)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    comment_at = models.DateTimeField(blank=True, null=True)
    is_approved = models.BooleanField(default=False, verbose_name="Approve?")
    date_approved = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"From {self.sender.username}, to {self.receipient.username}"

    def save(self, *args, **kwargs):
        if not self.id:
            self.sent_at = timezone.now()
        if self.comment and self.date_approved is None:
            self.date_approved = now()
        if self.comment and self.comment_at is None:
            self.comment_at = now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-sent_at']

#zaruuu
class MentorAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    availability_start = models.TimeField()
    availability_end = models.TimeField()

    def _str_(self):
        return self.user.username


class MenteeAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def _str_(self):
        return self.user.username


class Meeting(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='meetings')
    mentee = models.ForeignKey(Mentee, on_delete=models.CASCADE, related_name='meetings')

    appointment_date = models.DateField()
    time_slot = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    video_room_name = models.CharField(max_length=255, unique=True, blank=True, null=True, default=uuid.uuid4)
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')



    def save(self, *args, **kwargs):
        if not self.video_room_name:
            self.video_room_name = str(uuid.uuid4())  # auto-generate unique room
        super().save(*args, **kwargs)

    def _str_(self):
        return f"{self.mentee.user.username} & {self.mentor.user.username} on {self.appointment_date} at {self.time_slot}"

    @property
    def meeting_datetime(self):
        """Returns timezone-aware datetime of meeting start"""
        dt = datetime.combine(self.appointment_date, self.time_slot)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    @property
    def meeting_end_datetime(self):
        """Returns timezone-aware datetime of meeting end"""
        return self.meeting_datetime + timedelta(minutes=self.duration_minutes)

    @property
    def can_join(self):
        """Meeting can be joined only during scheduled window"""
        now = timezone.localtime(timezone.now())
        return self.meeting_datetime <= now <= self.meeting_end_datetime


class Query(models.Model):
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('moderate', 'Moderate'),
        ('low', 'Low'),
    ]

    mentee = models.ForeignKey(Mentee, on_delete=models.CASCADE)
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending")

    def _str_(self):
        return f"Query by {self.mentee} to {self.mentor}"