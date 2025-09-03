from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from .models import Mentee, Mentor, UserInfo, InternshipPBL, Project, Profile, Msg
from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm
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
        widget=forms.EmailInput(attrs={'placeholder': 'example@email.com'})
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


class InternshipPBLForm(forms.ModelForm):
    class Meta:
        model = InternshipPBL
        fields = ["title", "academic_year", "semester", "type",
                  "company_name", "details", "start_date", "end_date",
                  "no_of_days", "certificate"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "no_of_days": forms.NumberInput(attrs={"readonly": "readonly"}),
        }

    def clean_certificate(self):
        certificate = self.cleaned_data.get("certificate", False)
        if certificate and certificate.size > 1024 * 1024:  # 1 MB
            raise forms.ValidationError("Certificate size must be less than 200KB")
        if certificate and not certificate.name.endswith(".pdf"):
            raise forms.ValidationError("Only PDF files are allowed")
        return certificate


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "academic_year", "semester", "project_type", "details", "guide_name", "link"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "details (max 500 words)"}),
        }


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







