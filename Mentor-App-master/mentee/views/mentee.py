from django.shortcuts import render, redirect, get_object_or_404
# from ..models import Status
# from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from ..forms import MenteeRegisterForm, ProfileUpdateForm, InternshipPBLForm, ProjectForm, SportsCulturalForm, OtherEventForm, CertificationCourseForm, PaperPublicationForm, SelfAssessmentForm, LongTermGoalForm, SubjectOfInterestForm, EducationalDetailForm, SemesterResultForm, MeetingForm
from django.views.generic import TemplateView
from ..models import Profile, Msg, Conversation, Reply, InternshipPBL, Project, SportsCulturalEvent, OtherEvent, CertificationCourse, PaperPublication, SelfAssessment, LongTermGoal, SubjectOfInterest, EducationalDetail, SemesterResult, Meeting, Mentor, Mentee, StudentInterest
from django.contrib.auth import get_user_model
import logging
logger = logging.getLogger(__name__)
User = get_user_model()
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse
import traceback
from django.views.generic import (View, TemplateView,
                                  ListView, DetailView,
                                  CreateView, UpdateView,
                                  DeleteView)
from django.core.mail import send_mail
from django.urls import reverse_lazy
from .. import models
from django.contrib.messages.views import SuccessMessageMixin

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin

from ..forms import SendForm
from django.db.models import Count, Q
from ..render import Render
from django.http import HttpResponse, Http404
from django.conf import settings
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image
import pypandoc
from django.core.mail import EmailMultiAlternatives
import uuid
from django.template.loader import render_to_string

def home(request):
    """Home landing page"""
    return render(request, 'home.html')


# """Home account landing page after you login"""
# @login_required
# def account(request):

# users = User.objects.all().filter(is_mentor=True)

# context = {

# 'users': users


# }

# return render(request, 'menti/account.html', context)


class AccountList(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        # Only mentees can access this view
        return self.request.user.is_mentee

    def get(self, request, *args, **kwargs):
        try:
            mentee = request.user.mentee
        except Mentee.DoesNotExist:
            return render(request, "menti/account.html", {"user_meeting_data": []})

            # Get the one assigned mentor
        mapping = mentee.mentee_mappings.select_related("mentor__user").first()
        if not mapping:
            return render(request, "menti/account.html", {"user_meeting_data": []})

        mentor = mapping.mentor
        now = timezone.localtime(timezone.now())
        meetings = Meeting.objects.filter(mentee=mentee, mentor=mentor)

        meeting = meetings.first()
        can_join = can_feedback = feedback_exists = False
        if meeting:
            start = meeting.meeting_datetime
            end = meeting.meeting_end_datetime
            can_join = start <= now <= end
            feedback_exists = hasattr(meeting, "feedback_obj")
            can_feedback = now > end and not feedback_exists

        user_meeting_data = [{
            "user": mentor.user,
            "meeting": meeting,
            "can_join": can_join,
            "can_feedback": can_feedback,
            "feedback_exists": feedback_exists,
        }]

        return render(request, "menti/account.html", {
            "user_meeting_data": user_meeting_data,
            "now": now,
            "is_mentor_view": False,
        })


def register(request):
    """Controls the register module"""

    registered = False

    if request.method == 'POST':

        form1 = MenteeRegisterForm(request.POST)

        if form1.is_valid():
            user = form1.save()
            user.is_mentee = True
            user.save()

            registered = True
            messages.success(request, f'Your account has been created! You are now able to log in')
            return redirect('login')
    else:
        form1 = MenteeRegisterForm()

    return render(request, 'menti/register.html', {'form1': form1})


def user_login(request):
    """Login function"""

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome to your Account')
                return HttpResponseRedirect(reverse('mentee-home'))

            else:
                return HttpResponse("Your account was inactive.")
        else:
            print("Someone tried to login and failed.")
            print("They used username: {} and password: {}".format(username, password))
            return HttpResponse("Invalid login details given")
    else:
        return render(request, 'menti/login.html', {})


def custom_logout(request):
    logout(request)
    return redirect('login')


def send_forget_password_email(email, token):
    try:
        subject = 'Reset Your Password'
        reset_link = f'http://127.0.0.1:8000/change-password/{token}/'
        message = f"""
        Hi,

        You requested a password reset. Click the link below to reset your password:

        {reset_link}

        If you did not request this, please ignore this email.

        Regards,
        Your App Team
        """
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]

        send_mail(subject, message.strip(), email_from, recipient_list)
        print("✅ Reset email sent successfully.")
        return True

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False


def ForgetPassword(request):
    try:
        if request.method == 'POST':
            moodle_id = request.POST.get('username')  # still from the same form field
            print(f"Submitted moodle_id: {moodle_id}")

            # Find the profile by moodle_id
            profile_obj = Profile.objects.filter(moodle_id=moodle_id).first()
            if not profile_obj:
                messages.error(request, 'No user found with this Moodle ID.')
                return render(request, 'menti/forget-password.html')

            user_obj = profile_obj.user  # Get the related User

            # Create token and save
            token = str(uuid.uuid4())
            profile_obj.forget_password_token = token
            profile_obj.save()

            # Send email
            send_forget_password_email(user_obj.email, token)

            messages.success(request, 'Password reset link has been sent to your email.')
            return render(request, 'menti/forget-password.html')

    except Exception as e:
        print("Error in ForgetPassword:")
        traceback.print_exc()
        messages.error(request, 'Something went wrong. Please try again.')

    return render(request, 'menti/forget-password.html')


def ChangePassword(request, token):
    try:
        profile_obj = Profile.objects.filter(forget_password_token=token).first()

        if not profile_obj:
            messages.error(request, "Invalid or expired token.")
            return redirect('login')

        context = {
            'user_id': profile_obj.user.id,
            'token': token
        }

        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('reconfirm_password')
            user_id = request.POST.get('user_id')

            if not user_id:
                messages.error(request, 'User ID is missing.')
                return render(request, 'menti/change-password.html', context)

            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'menti/change-password.html', context)

            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()

            # Clear token after reset
            profile_obj.forget_password_token = None
            profile_obj.save()

            messages.success(request, 'Password updated successfully.')
            return redirect('login')

        # GET request
        return render(request, 'menti/change-password.html', context)

    except Exception as e:
        print("Error in ChangePassword:", e)
        messages.error(request, "Something went wrong. Try again.")
        return redirect('forget_password')


@login_required
def mentee_home(request):
    profile = Profile.objects.get(user=request.user)
    return render(request, "menti/mentee_home.html", {"profile": profile, "is_mentor_view": False,})


@login_required
def profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, 'menti/profile.html', {'form': form, "is_mentor_view": False,})


class MessageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Creates new message"""

    fields = ('receipient', 'msg_content')
    model = Msg
    template_name = 'menti/messagecreate.html'

    def test_func(self):
        return self.request.user.is_mentee

    def form_valid(self, form):
        form.instance.sender = self.request.user

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 👇 Add flag here
        context['is_mentor_view'] = False

        return context


@login_required
def internship_pbl_list(request, pk=None):
    internships = InternshipPBL.objects.filter(user=request.user).order_by("-start_date")
    internship = None
    editing = False

    if pk:  # Editing case
        internship = get_object_or_404(InternshipPBL, pk=pk, user=request.user)
        editing = True

    if request.method == "POST":
        form = InternshipPBLForm(request.POST, request.FILES, instance=internship)
        if form.is_valid():
            internship = form.save(commit=False)
            internship.user = request.user

            if internship.start_date and internship.end_date:
                internship.no_of_days = (internship.end_date - internship.start_date).days + 1

            internship.save()

            if editing:
                messages.success(request, "Internship record updated successfully.")
            else:
                messages.success(request, "Internship record added successfully.")

            return redirect("internship-pbl-list")
        else:
            print(form.errors)
    else:
        form = InternshipPBLForm(instance=internship)

    return render(request, "menti/internship_pbl_list.html", {
        "internships": internships,
        "form": form,
        "editing": editing,
        "edit_id": internship.pk if internship else None,
        "is_mentor_view": False,
    })


#download internship certificate
@login_required
def download_certificate(request, pk):
    try:
        internship = InternshipPBL.objects.get(pk=pk)
        if not internship.certificate:
            raise Http404("No certificate found")

        file_path = internship.certificate.path
        file_ext = os.path.splitext(file_path)[1].lower()

        # Case 1: Already PDF
        if file_ext == ".pdf":
            file_name = f"certificate_{internship.user.username}.pdf"
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'attachment; filename="certificate_{file_name}_{internship.user.username}"'
                return response

        # Case 2: Image (jpg/png) → Convert to PDF
        elif file_ext in [".jpg", ".jpeg", ".png"]:
            image = Image.open(file_path)
            pdf_path = os.path.join(settings.MEDIA_ROOT, f"temp_{internship.pk}.pdf")
            image.convert('RGB').save(pdf_path)

            with open(pdf_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'attachment; filename="certificate_{internship.user.username}.pdf"'
            os.remove(pdf_path)
            return response

        # Case 3: DOCX/TXT → Convert to PDF using pypandoc
        elif file_ext in [".docx", ".txt"]:
            pdf_path = os.path.join(settings.MEDIA_ROOT, f"temp_{internship.pk}.pdf")
            pypandoc.convert_file(file_path, 'pdf', outputfile=pdf_path)

            with open(pdf_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'attachment; filename="certificate_{internship.user.username}.pdf"'
            os.remove(pdf_path)
            return response

        else:
            raise Http404("Unsupported file type for conversion")

    except InternshipPBL.DoesNotExist:
        raise Http404("Record not found")


@login_required
def delete_internship(request, pk):
    internship = get_object_or_404(InternshipPBL, pk=pk, user=request.user)

    # Delete certificate file from storage
    if internship.certificate:
        file_path = internship.certificate.path
        if os.path.exists(file_path):
            os.remove(file_path)

    # Delete record from DB
    internship.delete()
    messages.success(request, "Record deleted successfully.")
    return redirect("internship-pbl-list")


@login_required
def projects_view(request):
    projects = Project.objects.filter(user=request.user).order_by("-uploaded_at")

    # If editing (project_id passed in query params)
    project_id = request.GET.get("edit")
    project_to_edit = None
    if project_id:
        project_to_edit = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == "POST":
        if "delete" in request.POST:  # delete project
            project = get_object_or_404(Project, id=request.POST.get("delete"), user=request.user)
            project.delete()
            return redirect("projects-list")

        elif project_id:  # update project
            form = ProjectForm(request.POST, request.FILES, instance=project_to_edit)
            if form.is_valid():
                form.save()
                return redirect("projects-list")
        else:  # add new project
            form = ProjectForm(request.POST, request.FILES)
            if form.is_valid():
                project = form.save(commit=False)
                project.user = request.user
                project.save()
                return redirect("projects-list")
    else:
        if project_to_edit:
            form = ProjectForm(instance=project_to_edit)  # prefill form for editing
        else:
            form = ProjectForm()

    return render(
        request,
        "menti/projects_list.html",
        {
            "projects": projects,
            "form": form,
            "editing": bool(project_to_edit),
            "project_id": project_to_edit.id if project_to_edit else None,
            "is_mentor_view": False,
        },
    )


@login_required
def sports_cultural_list(request):
    events = SportsCulturalEvent.objects.filter(user=request.user).order_by("-uploaded_at")

    editing = False
    edit_id = None

    if request.method == "POST":
        form = SportsCulturalForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.save()
            messages.success(request, "Event added successfully.")
            return redirect("sports-and-cultural")
    else:
        form = SportsCulturalForm()

    return render(request, "menti/sports_and_cultural.html", {
        "events": events,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def edit_sports_cultural(request, pk):
    event = get_object_or_404(SportsCulturalEvent, pk=pk, user=request.user)
    editing = True
    edit_id = pk

    if request.method == "POST":
        form = SportsCulturalForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated successfully.")
            return redirect("sports-and-cultural")
    else:
        form = SportsCulturalForm(instance=event)

    events = SportsCulturalEvent.objects.filter(user=request.user).order_by("-uploaded_at")

    return render(request, "menti/sports_and_cultural.html", {
        "events": events,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def delete_sports_cultural(request, pk):
    event = get_object_or_404(SportsCulturalEvent, pk=pk, user=request.user)

    if event.certificate:
        event.certificate.delete(save=False)

    event.delete()
    messages.success(request, "Event deleted successfully.")
    return redirect("sports-and-cultural")


@login_required
def other_event_list(request, pk=None):
    events = OtherEvent.objects.filter(user=request.user).order_by("-uploaded_at")
    editing = False
    edit_id = None

    if pk:  # Editing mode
        event = get_object_or_404(OtherEvent, pk=pk, user=request.user)
        form = OtherEventForm(instance=event)
        editing = True
        edit_id = pk
    else:
        form = OtherEventForm()

    if request.method == "POST":
        if pk:  # Update existing record
            form = OtherEventForm(request.POST, request.FILES, instance=event)
        else:   # Add new record
            form = OtherEventForm(request.POST, request.FILES)

        if form.is_valid():
            new_event = form.save(commit=False)
            new_event.user = request.user
            new_event.save()
            return redirect("other-events")

    return render(request, "menti/other_events.html", {
        "events": events,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def delete_other_event(request, pk):
    event = get_object_or_404(OtherEvent, pk=pk, user=request.user)

    if event.certificate:
        file_path = event.certificate.path
        if os.path.exists(file_path):
            os.remove(file_path)

    event.delete()
    messages.success(request, "Event deleted successfully.")
    return redirect("other-events")


@login_required
def certification_list(request, pk=None):
    certifications = CertificationCourse.objects.filter(user=request.user).order_by("-uploaded_at")
    editing = False
    edit_id = None

    if pk:
        cert = get_object_or_404(CertificationCourse, pk=pk, user=request.user)
        form = CertificationCourseForm(instance=cert)
        editing = True
        edit_id = pk
    else:
        form = CertificationCourseForm()

    if request.method == "POST":
        if pk:
            form = CertificationCourseForm(request.POST, request.FILES, instance=cert)
        else:
            form = CertificationCourseForm(request.POST, request.FILES)

        if form.is_valid():
            new_cert = form.save(commit=False)
            new_cert.user = request.user
            new_cert.save()
            return redirect("certifications")

    return render(request, "menti/certifications.html", {
        "certifications": certifications,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def delete_certification(request, pk):
    cert = get_object_or_404(CertificationCourse, pk=pk, user=request.user)

    if cert.certificate:
        file_path = cert.certificate.path
        if os.path.exists(file_path):
            os.remove(file_path)

    cert.delete()
    messages.success(request, "Certification deleted successfully.")
    return redirect("certifications")


@login_required
def publications_list(request, pk=None):
    publications = PaperPublication.objects.filter(user=request.user).order_by("-uploaded_at")
    editing = False
    edit_id = None

    if pk:
        pub = get_object_or_404(PaperPublication, pk=pk, user=request.user)
        form = PaperPublicationForm(instance=pub)
        editing = True
        edit_id = pk
    else:
        form = PaperPublicationForm()

    if request.method == "POST":
        if pk:
            form = PaperPublicationForm(request.POST, request.FILES, instance=pub)
        else:
            form = PaperPublicationForm(request.POST, request.FILES)

        if form.is_valid():
            new_pub = form.save(commit=False)
            new_pub.user = request.user
            new_pub.save()
            return redirect("publications")

    return render(request, "menti/publications.html", {
        "publications": publications,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def delete_publication(request, pk):
    pub = get_object_or_404(PaperPublication, pk=pk, user=request.user)
    pub.delete()
    return redirect("publications")


@login_required
def self_assessment(request, pk=None):
    assessments = SelfAssessment.objects.filter(user=request.user).order_by("-created_at")
    editing = False
    edit_id = None

    if pk:
        assessment = get_object_or_404(SelfAssessment, pk=pk, user=request.user)
        form = SelfAssessmentForm(instance=assessment)
        editing = True
        edit_id = pk
    else:
        form = SelfAssessmentForm()

    if request.method == "POST":
        if pk:
            form = SelfAssessmentForm(request.POST, instance=assessment)
        else:
            form = SelfAssessmentForm(request.POST)

        if form.is_valid():
            new_assessment = form.save(commit=False)
            new_assessment.user = request.user
            new_assessment.save()
            return redirect("self_assessment")

    return render(request, "menti/self_assessment.html", {
        "assessments": assessments,
        "form": form,
        "editing": editing,
        "edit_id": edit_id,
        "is_mentor_view": False,
    })


@login_required
def delete_assessment(request, pk):
    assessment = get_object_or_404(SelfAssessment, pk=pk, user=request.user)
    assessment.delete()
    return redirect("self_assessment")


@login_required
def long_term_goals(request, edit_id=None):
    goals = LongTermGoal.objects.filter(user=request.user)
    subjects = SubjectOfInterest.objects.filter(user=request.user)

    # --- Long term goal form ---
    if request.method == "POST" and "save_goal" in request.POST:
        goal_form = LongTermGoalForm(request.POST)
        if goal_form.is_valid():
            goal = goal_form.save(commit=False)
            goal.user = request.user
            goal.save()
            return redirect("long_term_goals")
    else:
        goal_form = LongTermGoalForm()

    # --- Subject form (Add/Edit) ---
    subject_instance = None
    if edit_id:
        subject_instance = get_object_or_404(SubjectOfInterest, pk=edit_id, user=request.user)

    if request.method == "POST" and "save_subject" in request.POST:
        subject_form = SubjectOfInterestForm(request.POST, instance=subject_instance)
        if subject_form.is_valid():
            subject = subject_form.save(commit=False)
            subject.user = request.user
            subject.save()
            return redirect("long_term_goals")
    else:
        subject_form = SubjectOfInterestForm(instance=subject_instance)

    return render(request, "menti/long_term_goals.html", {
        "goal_form": goal_form,
        "goal": goals,
        "subject_form": subject_form,
        "subjects": subjects,
        "edit_id": edit_id,  # pass edit id to template
        "is_mentor_view": False,
    })


@login_required
def delete_subject(request, pk):
    subject = get_object_or_404(SubjectOfInterest, pk=pk, user=request.user)
    subject.delete()
    return redirect("long_term_goals")


@login_required
def educational_details(request):
    details = EducationalDetail.objects.filter(user=request.user)

    editing = None
    if "edit" in request.GET:
        editing = get_object_or_404(EducationalDetail, id=request.GET.get("edit"), user=request.user)

    if request.method == "POST":
        # Delete action
        if "delete" in request.POST:
            detail = get_object_or_404(EducationalDetail, id=request.POST.get("delete"), user=request.user)
            detail.delete()
            messages.success(request, "Educational detail deleted successfully.")
            return redirect("educational-details")

        # Add / Update form
        form = EducationalDetailForm(request.POST, instance=editing)
        if form.is_valid():
            edu = form.save(commit=False)
            edu.user = request.user   # ✅ ensure user is attached
            edu.save()
            messages.success(request, "Educational detail saved successfully.")
            return redirect("educational-details")
        else:
            print("Form errors:", form.errors)  # ✅ Debug line
    else:
        form = EducationalDetailForm(instance=editing)

    context = {
        "details": details,
        "form": form,
        "editing": editing,
        "is_mentor_view": False,
    }
    return render(request, "menti/educational_details.html", context)


@login_required
def semester_results(request):
    semesters = SemesterResult.objects.filter(user=request.user)

    # Normal add
    if request.method == "POST" and "edit_id" not in request.POST:
        form = SemesterResultForm(request.POST, request.FILES)
        if form.is_valid():
            sem = form.save(commit=False)
            sem.user = request.user
            sem.save()
            return redirect("semester_results")
    else:
        form = SemesterResultForm()

    return render(request, "menti/semester_results.html", {
        "form": form,
        "semesters": semesters,
        "editing": False,
        "is_mentor_view": False,
    })


@login_required
def edit_semester(request, pk):
    semester = get_object_or_404(SemesterResult, pk=pk, user=request.user)

    if request.method == "POST":
        form = SemesterResultForm(request.POST, request.FILES, instance=semester)
        if form.is_valid():
            form.save()
            return redirect("semester_results")
    else:
        form = SemesterResultForm(instance=semester)

    semesters = SemesterResult.objects.filter(user=request.user)
    return render(request, "menti/semester_results.html", {
        "form": form,
        "semesters": semesters,
        "editing": True,
        "edit_id": semester.pk,
        "is_mentor_view": False,
    })


@login_required
def delete_semester(request, pk):
    semester = get_object_or_404(SemesterResult, pk=pk, user=request.user)
    semester.delete()
    return redirect("semester_results")


@login_required
def student_interests(request):
    obj, created = StudentInterest.objects.get_or_create(student=request.user)
    if request.method == "POST":
        selected = request.POST.getlist("interests")
        obj.interests = selected
        obj.save()

        messages.success(request, "Your interests have been saved!")
        return redirect("student_interests")

    saved_interests = []
    try:
        saved_interests = StudentInterest.objects.get(student=request.user).interests
    except StudentInterest.DoesNotExist:
        pass

    return render(request, "menti/student_interests.html", {
        "saved_interests": saved_interests,
        "is_mentor_view": False,
    })


@login_required
def uploaded_documents(request):
    documents = []

    # Collect user’s uploaded files from each model
    internships = InternshipPBL.objects.filter(user=request.user, certificate__isnull=False).exclude(certificate="")
    marksheets = SemesterResult.objects.filter(user=request.user, marksheet__isnull=False).exclude(marksheet="")
    publications = PaperPublication.objects.filter(user=request.user, certificate__isnull=False).exclude(certificate="")
    other_events = OtherEvent.objects.filter(user=request.user, certificate__isnull=False).exclude(certificate="")
    sports = SportsCulturalEvent.objects.filter(user=request.user, certificate__isnull=False).exclude(certificate="")
    courses = CertificationCourse.objects.filter(user=request.user, certificate__isnull=False).exclude(certificate="")

    # Normalize them into one list
    for doc in internships:
        documents.append({"category": "Internship/PBL", "name": doc.title or doc.company_name or "Internship Certificate", "file": doc.certificate})
    for doc in marksheets:
        documents.append({"category": "Marksheet", "name": f"Semester - {doc.semester} Marksheet" or "Marksheet", "file": doc.marksheet})
    for doc in publications:
        documents.append({"category": "Publication", "name": doc.title or "Publication Certificate", "file": doc.certificate})
    for doc in other_events:
        documents.append({"category": "Other Event", "name": doc.name_of_event or "Other Event Certificate", "file": doc.certificate})
    for doc in sports:
        documents.append({"category": "Sports & Cultural", "name": doc.name_of_event or "Sports Certificate", "file": doc.certificate})
    for doc in courses:
        documents.append({"category": "Certification Course", "name": doc.title or "Certification", "file": doc.certificate})

    return render(request, "menti/uploaded_documents.html", {"documents": documents, "is_mentor_view": False})


@login_required
def credits_view(request):
    return render(request, 'menti/credits.html', {"is_mentor_view": False,})


class MessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Views lists of messages you have sent to other users"""

    model = Conversation
    template_name = 'menti/listmessages.html'
    context_object_name = 'conversation1'
    paginate_by = 2

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class SentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """details the message sent"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'menti/sent.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


class InboxView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Views lists of inbox messages received"""

    model = Msg
    context_object_name = 'inbox'
    template_name = 'menti/inbox.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class InboxDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Inbox Detailed view"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'menti/inboxview.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class MessageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """controls messege view"""

    template_name = 'menti/messages-module.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['count'] = Msg.objects.filter(receipient=self.request.user).filter(is_approved=False).count()
        context['count1'] = Msg.objects.filter(sender=self.request.user).filter(is_approved=True).count()
        context['count3'] = Conversation.objects.filter(receipient=self.request.user).count()
        context['count4'] = Conversation.objects.filter(sender=self.request.user).count()
        context['is_mentor_view'] = False
        return context

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


def messege_view(request):
    """Views the Message Module"""

    if not request.user.is_mentee:
        return redirect('home')

    return render(request, 'menti/messages-module.html', {"is_mentor_view": False,})


class SentMessageDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Deletes Sent Messages"""

    model = models.Msg
    success_url = reverse_lazy("list")
    template_name = 'menti/sentmessage_delete.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class Approved(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """view list of approved messages from mentors"""

    def test_func(self):
        return self.request.user.is_mentee

    # def get(self, request):

    # messo = Msg.objects.filter(is_approved=True).order_by('-date_approved')

    # context = {

    # 'messo': messo,

    # }

    # return render(request, "menti/approved.html", context)

    model = Msg.objects.filter(is_approved=True).order_by('-date_approved')

    template_name = 'menti/approved.html'

    context_object_name = 'messo'

    paginate_by = 5

    def get_queryset(self):
        return self.model.filter(sender=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class Pdf(View):
    """Pdf of Approved Requests"""

    def get(self, request):
        messo1 = Msg.objects.filter(is_approved=True).order_by('-date_approved').filter(sender=self.request.user)

        params = {
            'messo1': messo1,

            'request': request
        }
        return Render.render('menti/pdf.html', params)


class CreateMessageView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    """create new message for a specific user from the profile"""

    fields = ('msg_content',)
    model = Msg
    template_name = 'menti/sendindividual.html'
    success_message = 'Your Message has Been Sent!'

    def test_func(self):
        return self.request.user.is_mentee

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.receipient = User.objects.get(pk=self.kwargs['pk'])

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('list')


class ProfileDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """view details of a user in the profile"""

    model = User
    context_object_name = 'user'
    template_name = 'menti/profile_detail.html'

    def test_func(self):
        return self.request.user.is_mentee


class ConversationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List all chat conversation by a user"""

    model = Conversation
    template_name = 'menti/list-converations.html'
    context_object_name = 'conversation'
    paginate_by = 5

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_mentor_view'] = False
        return context


class ConversationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """List Conversations"""

    model = Conversation
    template_name = 'menti/conversation1.html'
    context_object_name = 'conv'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


class ConversationList1View(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """List Conversation"""

    model = Conversation
    template_name = 'menti/conversation2.html'
    context_object_name = 'conversation'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


def con(request, pk):
    """List conversations"""

    conv = get_object_or_404(Conversation, pk=pk)

    context = {

        'conv': conv,

    }

    return render(request, 'menti/conversation1.html', context)


class ReplyCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Replies by a user"""

    fields = ('reply',)
    model = Reply
    template_name = 'menti/conversation.html'

    def test_func(self):
        return self.request.user.is_mentee

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.conversation = Conversation.objects.get(pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv1-reply', kwargs={'pk': self.object.conversation_id})

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


class ConversationDeleteView(DeleteView):
    """delete view Chat"""
    model = Reply
    template_name = 'menti/chat-confirm-delete.html'

    # success_url = reverse_lazy('conv1')

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv1-reply', kwargs={'pk': self.object.conversation_id})


def search(request):
    """Search For Users"""

    if not request.user.is_mentee:
        return redirect('home')

    queryset = User.objects.all()

    query = request.GET.get('q')

    if query:
        queryset = queryset.filter(

            Q(username__icontains=query) |
            Q(first_name__icontains=query)

        ).distinct()

    context = {
        'is_mentor_view': False,
        'queryset': queryset
    }

    return render(request, 'menti/search_results.html', context)


class CreateIndividualMessageView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    """create new message for a specific user from search query"""

    fields = ('conversation',)
    model = Conversation
    template_name = 'menti/messagecreate2.html'
    success_message = 'Your Conversation Has been Created!'

    def test_func(self):
        return self.request.user.is_mentee

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.receipient = User.objects.get(pk=self.kwargs['pk'])

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('list')


class Profile2DetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """view details of a user search in the profile"""

    model = User
    context_object_name = 'user'
    template_name = 'menti/profile_detail1.html'

    def test_func(self):
        return self.request.user.is_mentee


class Reply1CreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Replies by a user"""

    fields = ('reply',)
    model = Reply
    template_name = 'menti/conversation3.html'

    def test_func(self):
        return self.request.user.is_mentee

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.conversation = Conversation.objects.get(pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv3-reply', kwargs={'pk': self.object.conversation_id})

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


def con1(request, pk):
    """View individual conversation"""

    conv = get_object_or_404(Conversation, pk=pk)

    context = {

        'conv': conv,

    }

    return render(request, 'menti/conversation4.html', context)


@login_required
def schedule_meeting_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    mentor = get_object_or_404(Mentor, user=user)
    mentee = get_object_or_404(Mentee, user=request.user)

    # Check if meeting already exists between this mentee and mentor
    existing_meeting = Meeting.objects.filter(mentor=mentor, mentee=mentee).first()

    if request.method == 'POST':
        form = MeetingForm(request.POST, instance=existing_meeting)  # reuse existing meeting if any
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.mentor = mentor
            meeting.mentee = mentee
            meeting.duration_minutes = 2

            # Only assign video_room_name if it's not already set
            if not meeting.video_room_name:
                meeting.video_room_name = str(uuid.uuid4())

            meeting.save()

            # Generate meeting room link
            jitsi_link = f"https://meet.jit.si/{meeting.video_room_name}"


            # Email context
            context = {
                'mentor_name': mentor.user.first_name or mentor.user.username,
                'mentee_name': mentee.user.first_name or mentee.user.username,
                'mentee_email': mentee.user.email,
                'meeting_date': meeting.appointment_date.strftime('%Y-%m-%d'),
                'meeting_time': meeting.time_slot.strftime('%H:%M'),
                'jitsi_link': jitsi_link,
            }

            subject = f"New Meeting Scheduled with {context['mentee_name']}"
            from_email = settings.EMAIL_HOST_USER
            to_email = [mentor.user.email]

            html_content = render_to_string('menti/meeting_invite.html', context)

            email = EmailMultiAlternatives(subject, '', from_email, to_email)
            email.attach_alternative(html_content, "text/html")
            email.extra_headers = {'Reply-To': mentee.user.email}

            email.send()

            messages.success(request, "Meeting scheduled and email sent to the mentor.")
            return redirect('account')
    else:
        form = MeetingForm(instance=existing_meeting)

    return render(request, 'menti/schedule_meeting.html', {'mentor': mentor, 'form': form})


@login_required
def meeting_room_view(request, room_name):
    meeting = get_object_or_404(Meeting, video_room_name=room_name)

    # Access control (optional)
    if request.user != meeting.mentor.user and request.user != meeting.mentee.user:
        return HttpResponseForbidden("Not authorized to join this meeting.")

    jitsi_link = f"https://meet.jit.si/{meeting.video_room_name}"  # ✅ Jitsi Link
    return render(request, 'menti/meeting_room.html', {
        'meeting': meeting,
        'jitsi_link': jitsi_link,
    })


@login_required
def meetings_view(request):
    # your logic here
    return render(request, 'menti/meetings.html')
