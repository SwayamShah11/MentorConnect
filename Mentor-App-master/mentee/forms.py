from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from .models import Mentee, Mentor, UserInfo, InternshipPBL, Project, Profile, Msg, SportsCulturalEvent, OtherEvent, CertificationCourse, PaperPublication, SelfAssessment, LongTermGoal, SubjectOfInterest, EducationalDetail, SemesterResult, Meeting, StudentInterest
from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm
from .validators import PDFValidationMixin
from django.contrib.auth.forms import ReadOnlyPasswordHashField


from django.contrib.auth import get_user_model
User = get_user_model()




class MenteeRegisterForm(UserCreationForm):

    email = forms.EmailField()

    #interests = forms.ModelMultipleChoiceField(
        #queryset=Subject.objects.all(),
        #widget=forms.CheckboxSelectMultiple,
        #required=True)

    #interests= forms.ChoiceField(required=True, widget=forms.RadioSelect(
        #attrs={'class': 'Radio'}))

    class Meta:
       model = User
       fields = ['username', 'email', 'password1', 'password2']



    def save(self):
        user = super().save(commit=False)
        user.is_mentee = True
        user.save()
        mentee = Mentee.objects.create(user=user)
        #mentee.interests.add(*self.cleaned_data.get('interests'))
        #mentee.interests = self.cleaned_data.get('interests')

        return user


class UserInfoForm(forms.ModelForm):

    interest = forms.ChoiceField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'Radio'}), choices=(('economics', 'Economics'), ('bbit', 'BBIT'),))

    class Meta():
        model = UserInfo
        fields = ('interest',)


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email']


# custom validator for contact numbers
def validate_contact(value):
    if not value.isdigit():
        raise ValidationError("Contact number must contain only digits.")
    if len(value) != 10:
        raise ValidationError("Contact number must be exactly 10 digits.")

# regex validator for email
email_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message="Enter a valid email address."
)

class ProfileUpdateForm(forms.ModelForm):
    # override email field with regex validation
    email = forms.EmailField(   # 👈 changed from email_id → email
        validators=[email_validator],
        widget=forms.EmailInput(attrs={'placeholder': 'example@email.com', 'readonly':'readonly'})
    )

    class Meta:
        model = Profile
        fields = [
            'moodle_id',   # 👈 added so it shows up
            'image', 'student_name', 'semester', 'year', 'branch',
            'address', 'contact_number', 'email', 'dob', 'hobby', 'about_me',
            'mother_name', 'mother_occupation', 'mother_contact',
            'father_name', 'father_occupation', 'father_contact',
            'sibling1_name', 'sibling2_name', 'career_domain'
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'contact_number': forms.TextInput(attrs={'maxlength': '10', 'pattern': '[0-9]{10}', 'title': 'Enter a 10-digit number'}),
            'mother_contact': forms.TextInput(attrs={'maxlength': '10', 'pattern': '[0-9]{10}', 'title': 'Enter a 10-digit number'}),
            'father_contact': forms.TextInput(attrs={'maxlength': '10', 'pattern': '[0-9]{10}', 'title': 'Enter a 10-digit number'}),
            'moodle_id': forms.TextInput(attrs={'readonly': 'readonly'}),  # 👈 non-editable frontend
        }

    # Backend validation (extra safety)
    def clean_contact_number(self):
        contact = self.cleaned_data.get("contact_number")
        if contact:
            validate_contact(contact)
        return contact

    def clean_mother_contact(self):
        contact = self.cleaned_data.get("mother_contact")
        if contact:
            validate_contact(contact)
        return contact

    def clean_father_contact(self):
        contact = self.cleaned_data.get("father_contact")
        if contact:
            validate_contact(contact)
        return contact


class InternshipPBLForm(PDFValidationMixin, forms.ModelForm):
    class Meta:
        model = InternshipPBL
        fields = ["title", "academic_year", "semester", "type",
                  "company_name", "details", "start_date", "end_date",
                  "no_of_days", "certificate"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "details (max 500 words)"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "no_of_days": forms.NumberInput(attrs={"readonly": "readonly"}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "academic_year", "semester", "project_type", "details", "guide_name", "link"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Project Title"}),
            "guide_name": forms.TextInput(attrs={"placeholder": "Guide Name"}),
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "details (max 500 words)"}),
            "link": forms.URLInput(attrs={"placeholder": "Enter project link (e.g. GitHub, Google Drive, etc.)"}),
        }


class SportsCulturalForm(PDFValidationMixin, forms.ModelForm):
    class Meta:
        model = SportsCulturalEvent
        fields = [
            "name_of_event", "academic_year", "semester", "type",
            "venue", "level", "prize_won", "certificate"
        ]
        widgets = {
            "name_of_event": forms.TextInput(attrs={"placeholder": "Name of Event"}),
            "venue": forms.TextInput(attrs={"placeholder": "Venue"}),
        }


class OtherEventForm(PDFValidationMixin, forms.ModelForm):
    class Meta:
        model = OtherEvent
        fields = [
            "name_of_event", "academic_year", "semester", "level",
            "details", "prize_won", "amount_won", "team_members", "certificate"
        ]
        widgets = {
            "name_of_event": forms.TextInput(attrs={"placeholder": "Name of Event"}),
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "details (max 500 words)"}),
            "amount_won": forms.TextInput(attrs={"placeholder": "eg. Rs. 5000"}),
            "team_members": forms.Textarea(attrs={"placeholder": "Name of all members (separated by commas). In case of individual participation write only your name."}),
        }


class CertificationCourseForm(PDFValidationMixin, forms.ModelForm):
    class Meta:
        model = CertificationCourse
        fields = [
            "title", "certifying_authority", "valid_upto",
            "academic_year", "semester", "start_date", "end_date",
            "no_of_days", "domain", "level", "amount_reimbursed", "certificate"
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Course Title"}),
            "certifying_authority": forms.TextInput(attrs={"placeholder": "eg. NPTEL, Cisco, Redhat, etc."}),
            "valid_upto": forms.TextInput(attrs={"placeholder": "eg. 2025, lifetime"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "no_of_days": forms.NumberInput(attrs={"readonly": "readonly"}),
            "domain": forms.TextInput(attrs={"placeholder": "Domain"}),
            "level": forms.TextInput(attrs={"placeholder": "eg. global, entry, foundation, expert, etc."}),
            "amount_reimbursed": forms.TextInput(attrs={"placeholder": "eg. Rs. 5000"}),
        }


class PaperPublicationForm(PDFValidationMixin, forms.ModelForm):
    class Meta:
        model = PaperPublication
        fields = ["title", "academic_year", "semester", "type", "details", "level", "amount_reimbursed", "authors", "certificate"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Paper Title"}),
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "Details (max 500 words)"}),
            "amount_reimbursed": forms.TextInput(attrs={"placeholder": "eg. Rs. 5000"}),
            "authors": forms.Textarea(attrs={"placeholder": "Name of all authors (separated by commas)."}),
        }


class SelfAssessmentForm(forms.ModelForm):
    goals = forms.MultipleChoiceField(
        choices=SelfAssessment.GOAL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = SelfAssessment
        fields = ["semester", "goals", "reason"]
        widgets = {
            "semester": forms.Select(attrs={"class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Reason"}),
        }


class LongTermGoalForm(forms.ModelForm):
    plan = forms.ChoiceField(
        choices=LongTermGoal.PLAN_CHOICES,
        widget=forms.RadioSelect,
        required=True
    )

    class Meta:
        model = LongTermGoal
        fields = ['plan', 'reason']
        widgets = {
            'reason': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Reason', 'rows': 2}),
        }


class SubjectOfInterestForm(forms.ModelForm):
    class Meta:
        model = SubjectOfInterest
        fields = ['subject']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'Enter subject'}),
        }


class EducationalDetailForm(forms.ModelForm):
    class Meta:
        model = EducationalDetail
        fields = ["examination", "percentage", "university_board", "year_of_passing"]
        widgets = {
            "examination": forms.Select(attrs={"class": "form-select"}),
            "percentage": forms.TextInput(attrs={"placeholder": "eg. 90", "class": "form-control"}),
            "university_board": forms.TextInput(attrs={"placeholder": "University/board", "class": "form-control"}),
            "year_of_passing": forms.TextInput(attrs={"placeholder": "eg 2014", "class": "form-control"}),
        }


class SemesterResultForm(forms.ModelForm):
    class Meta:
        model = SemesterResult
        fields = ["semester", "pointer", "no_of_kt", "marksheet"]
        widgets = {
            "semester": forms.Select(attrs={"class": "form-control"}),
            "pointer": forms.TextInput(attrs={"class": "form-control", "placeholder": "eg. 9.05"}),
            "no_of_kt": forms.TextInput(attrs={"class": "form-control", "placeholder": "eg. 2 (If none enter 0)"}),
        }


class InterestForm(forms.Form):
    interests = forms.MultipleChoiceField(
        choices=StudentInterest.INTEREST_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )


#mentor
class MoodleIdForm(forms.Form):
    moodle_id = forms.CharField(
        label="Moodle Id",
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Moodle Id of the Mentee"})
    )


class MentorRegisterForm(UserCreationForm):
    email = forms.EmailField()

    #interests = forms.ModelMultipleChoiceField(
        #queryset=Subject.objects.all(),
        #widget=forms.CheckboxSelectMultiple,
        #required=True
    #)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


    def save(self):
        user = super().save(commit=False)
        user.is_mentor = True
        user.save()
        mentor = Mentor.objects.create(user=user)
        #mentor.interests.add(*self.cleaned_data.get('interests'))

        return user


class UserInfoForm(forms.ModelForm):

    interest = forms.ChoiceField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'Radio'}), choices=(('economics', 'Economics'), ('bbit', 'BBIT'),))

    class Meta():
        model = UserInfo
        fields = ('interest',)


class ReplyForm(forms.Form):

    is_approved = forms.BooleanField(

        label='Approve?',
        help_text='Are you satisfied with the request?',
        required=False,

    )

    comment = forms.CharField(

        widget=forms.Textarea,
        min_length=4,
        error_messages={

            'required': 'Please enter your reply or comments',
            'min_length': 'Please write at least 5 characters (you have written %(show_value)s)'

        }

    )

class SendForm(ModelForm):

    class Meta:
        model = Msg
        fields = ['msg_content']


#zaruuu
class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['appointment_date', 'time_slot']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time_slot': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
        }




