import traceback
import uuid
from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
import io
from django.utils.decorators import method_decorator
import os
import re
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from html import escape
from django.contrib import messages
from ..forms import MentorRegisterForm, MentorProfileForm, MoodleIdForm, ChatReplyForm, MentorInteractionForm
from django.views.generic import (View, TemplateView,
                                  ListView, DetailView,
                                  CreateView, UpdateView,
                                  DeleteView)
from django.utils.timezone import now
from django.db.models.functions import TruncMonth
from django.db.models import Count
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView
from ..models import (Profile, Msg, Conversation, Reply, Meeting, Mentor, Mentee, MentorMentee, Query, InternshipPBL,
                      PaperPublication, SemesterResult, SportsCulturalEvent, CertificationCourse, OtherEvent, Project,
                      MentorMenteeInteraction, Notification, ReminderLog)
from ..utils import get_document_progress
from django.views.decorators.csrf import csrf_exempt
from mentee.ai_utils import generate_ai_summary
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse_lazy
from ..forms import ReplyForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from reportlab.lib.styles import ParagraphStyle
from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.messages.views import SuccessMessageMixin
from ..render import Render
import json
import zipfile
from io import BytesIO
from datetime import datetime
from collections import Counter, defaultdict

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings

# Excel libs
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

# ReportLab libs
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table as RLTable, TableStyle as RLTableStyle,
    Paragraph, Spacer, Image as RLImage, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.units import cm
SEMESTER = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII']       #used in Mentor-Mentee interaction function

def home(request):
    """Landing page """

    return render(request, 'home.html')

@method_decorator(login_required, name='dispatch')
class AccountView(LoginRequiredMixin, UserPassesTestMixin, View):
    """For Mentor Account"""

    def test_func(self):
        # Only allow if the logged-in user is a mentor
        return hasattr(self.request.user, "mentor")

    def handle_no_permission(self):
        # If user is logged in but not mentor → redirect to home
        if self.request.user.is_authenticated:
            return redirect("home")
        # If not logged in → go to login
        return super().handle_no_permission()

    def get(self, request):
        form = MoodleIdForm()
        mentor = get_object_or_404(Mentor, user=request.user)

        mentee_mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")

        mentees = []
        no_document_mentees = []

        for mapping in mentee_mappings:
            user = mapping.mentee.user
            profile = Profile.objects.filter(user=user).first()

            completed_count, total_required, has_pending = get_document_progress(user)
            progress_percent = int((completed_count / total_required) * 100)

            mentee_data = {
                "id": mapping.mentee.pk,
                "moodle_id": profile.moodle_id if profile else "",
                "name": profile.student_name if profile else user.username,
                "semester": profile.semester if profile else "",
                "contact": profile.contact_number if profile else "",
                "progress": f"{completed_count}/{total_required}",
                "progress_percent": progress_percent,
                "has_any_document": completed_count > 0,
                "has_pending": has_pending,
            }

            mentees.append(mentee_data)

            if completed_count < 7:
                no_document_mentees.append(mentee_data)

        return render(request, "mentor/account1.html", {
            "form": form,
            "mentees": mentees,
            "no_document_mentees": no_document_mentees,
        })

    def post(self, request):
        form = MoodleIdForm(request.POST)
        mentor = get_object_or_404(Mentor, user=request.user)

        if form.is_valid():
            moodle_id = form.cleaned_data["moodle_id"]
            profile = Profile.objects.filter(moodle_id=moodle_id).first()

            if not profile:
                messages.error(request, "No student found with that Moodle ID.")
                return redirect("account1")

            mentee = Mentee.objects.filter(user=profile.user).first()
            if not mentee:
                mentee = Mentee.objects.create(user=profile.user)

            # Prevent duplicates
            # ✅ PREVENT MULTIPLE MENTORS ASSIGNING SAME MENTEE
            existing_mapping = MentorMentee.objects.filter(mentee=mentee).first()

            if existing_mapping:
                messages.error(
                    request,
                    f"{profile.student_name} is already assigned to Mentor: {existing_mapping.mentor.name}"
                )
                return redirect("account1")

            MentorMentee.objects.create(mentor=mentor, mentee=mentee)
            messages.success(request, f"{profile.student_name} added as your mentee!")

        return redirect("account1")


@login_required
def remind_mentee(request, mentee_id):
    mentor = get_object_or_404(Mentor, user=request.user)
    mentee = get_object_or_404(Mentee, pk=mentee_id)
    user = mentee.user

    completed_count, total_required, has_pending = get_document_progress(user)

    if not has_pending:
        messages.info(request, f"{user.username} - {user.profile.student_name} has already completed all required documents.")
        return redirect("account1")

    # ✅ 1. Save Notification
    Notification.objects.create(
        user=user,
        message=f"⚠️ Your mentor {mentor.name} has reminded you to upload your pending documents and complete the Profile.\n"
    )

    # ✅ 2. Send Email
    if user.email:
        send_mail(
            subject="Reminder to Upload Your Documents and Complete the Profile",
            message=(
                f"Dear {user.profile.student_name}({user.username}),\n\n"
                f"Your mentor {mentor.name} has reminded you to upload your pending documents and complete your profile.\n"
                f"You need to complete the pending uploads before the next mentoring session.\n"
                f"Please log in to MentorConnect and upload them as soon as possible.\n\n"
                f"Regards,\nMentorConnect Team\n\n\n"
                f"*This is a system generated Email. Please do not reply to this Email.*\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    # 3️⃣ Log this reminder
    ReminderLog.objects.create(
        mentor=mentor,
        mentee=mentee,
        is_auto=False,
    )
    messages.success(request, f"Reminder sent to {user.username} - {user.profile.student_name}!")
    return redirect("account1")


def register1(request):
    """Registration for mentors"""

    registered = False

    if request.method == 'POST':

        form1 = MentorRegisterForm(request.POST)

        if form1.is_valid():
            user = form1.save()
            user.is_mentor = True
            user.save()

            registered = True
            messages.success(request, f'Your account has been created! You are now able to log in')
            return redirect('login1')
    else:
        form1 = MentorRegisterForm()

    return render(request, 'mentor/register1.html', {'form1': form1})


@login_required
def profile1(request):
    """Update Mentor Profile"""

    if not hasattr(request.user, "mentor"):
        return redirect("home")

    mentor = request.user.mentor  # one-to-one relation

    if request.method == "POST":
        form = MentorProfileForm(request.POST, request.FILES, instance=mentor, user=request.user)

        if form.is_valid():
            # Update User info
            request.user.username = form.cleaned_data["username"]
            request.user.email = form.cleaned_data["email"]
            request.user.save()

            # Update Mentor info
            form.save()

            messages.success(request, "Your profile has been updated successfully!")
            return redirect("profile1")
    else:
        form = MentorProfileForm(instance=mentor, user=request.user)

    return render(request, "mentor/profile1.html", {"form": form})


def user_login(request):
    """Login function"""

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect(reverse('account1'))
            else:
                return HttpResponse("Your account was inactive.")
        else:
            print("Someone tried to login and failed.")
            print("They used username: {} and password: {}".format(username, password))
            return HttpResponse("Invalid login details given")
    else:
        return render(request, 'mentor/login1.html', {})


def custom_logout(request):
    logout(request)
    return redirect('login1')


@login_required
def remove_mentee(request, mentee_id):
    if not hasattr(request.user, "mentor"):
        return redirect("home")  # block non-mentors

    mentor = get_object_or_404(Mentor, user=request.user)
    mapping = get_object_or_404(MentorMentee, mentor=mentor, mentee_id=mentee_id)
    mapping.delete()
    return redirect("account1")


@login_required
def view_mentee(request, mentee_id):
    from mentee.models import (
        EducationalDetail, InternshipPBL,Project, SportsCulturalEvent, OtherEvent, LongTermGoal, CertificationCourse,
        PaperPublication, SelfAssessment, StudentInterest, SemesterResult, Profile, SubjectOfInterest
    )

    # get mentee profile
    mentee = get_object_or_404(User, pk=mentee_id)

    # fetch related objects
    profile = Profile.objects.filter(user=mentee).first()
    education = EducationalDetail.objects.filter(user=mentee)
    projects = Project.objects.filter(user=mentee)
    sports = SportsCulturalEvent.objects.filter(user=mentee)
    other_event = OtherEvent.objects.filter(user=mentee)
    publications = PaperPublication.objects.filter(user=mentee)
    student_interest = StudentInterest.objects.filter(student=mentee).first()
    results = SemesterResult.objects.filter(user=mentee)
    internships = InternshipPBL.objects.filter(user=mentee)
    goals = LongTermGoal.objects.filter(user=mentee)
    subjects = SubjectOfInterest.objects.filter(user=mentee)
    certifications = CertificationCourse.objects.filter(user=mentee)
    assessment = SelfAssessment.objects.filter(user=mentee)

    context = {
        "mentee": mentee,
        "profile": profile,
        "education": education,
        "projects": projects,
        "sports": sports,
        "other_event": other_event,
        "publications": publications,
        "student_interest": student_interest,
        "saved_interests": student_interest.interests if student_interest else [],
        "results": results,
        "internships": internships,
        "goal": goals,
        "subjects": subjects,
        "certifications": certifications,
        "assessment": assessment,
        "is_mentor_view": True,   # 👈 flag to hide edit buttons
    }
    return render(request, "mentor/view_mentee_dashboard.html", context)

@login_required
def mentee_documents(request):
    documents = []
    moodle = None
    error = None

    # current mentor
    mentor = get_object_or_404(Mentor, user=request.user)

    # mentees under this mentor (same logic as AccountView)
    mentee_mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")
    mentees = []
    for mapping in mentee_mappings:
        profile = Profile.objects.filter(user=mapping.mentee.user).first()
        if not profile:
            continue
        mentees.append({
            "user_id": mapping.mentee.user.id,
            "moodle_id": profile.moodle_id,
            "name": profile.student_name or mapping.mentee.user.username,
        })

    def get_mentee_user_by_moodle(moodle_id: str):
        for m in mentees:
            if m["moodle_id"] == moodle_id:
                return User.objects.get(pk=m["user_id"])
        return None

    if request.method == "POST":
        moodle = request.POST.get("moodle_id")

        mentee_user = get_mentee_user_by_moodle(moodle)
        if mentee_user is None:
            error = "Selected Moodle ID is not one of your mentees."
        else:

            def add_doc(file, label, dtype):
                """file: FileField, label: document name, dtype: category"""
                if file:
                    documents.append({
                        "name": label,
                        "file": file,
                        "type": dtype,
                    })

            # Internship / PBL
            for item in InternshipPBL.objects.filter(user=mentee_user):
                add_doc(
                    item.certificate,
                    item.title or "Internship / PBL Certificate",
                    "Internship / PBL",
                )

            # Sports & Cultural
            for item in SportsCulturalEvent.objects.filter(user=mentee_user):
                add_doc(
                    item.certificate,
                    item.name_of_event or "Sports / Cultural Event",
                    "Sports / Cultural",
                )

            # Other Events
            for item in OtherEvent.objects.filter(user=mentee_user):
                add_doc(
                    item.certificate,
                    item.name_of_event or "Other Event",
                    "Other Event",
                )

            # Certification Courses
            for item in CertificationCourse.objects.filter(user=mentee_user):
                add_doc(
                    item.certificate,
                    item.title or "Certification Course",
                    "Course",
                )

            # Paper Publications
            for item in PaperPublication.objects.filter(user=mentee_user):
                add_doc(
                    item.certificate,
                    item.title or "Paper Publication",
                    "Publication",
                )

            # Semester Results (marksheets)
            for item in SemesterResult.objects.filter(user=mentee_user):
                add_doc(
                    item.marksheet,
                    f"Semester {item.semester} Marksheet",
                    "Semester Result",
                )

    return render(request, "mentor/mentee_documents.html", {
        "documents": documents,
        "moodle": moodle,
        "mentees": mentees,
        "error": error,
    })


@login_required
def download_all_documents(request):
    if request.method != "POST":
        return redirect("mentee_documents")  # or wherever your page is

    moodle = request.POST.get("moodle_id")
    if not moodle:
        messages.error(request, "No Moodle ID selected.")
        return redirect("mentee_documents")

    # verify mentor and build mentees list (same logic as mentee_documents)
    mentor = get_object_or_404(Mentor, user=request.user)
    mentee_mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")
    mentees = {}
    for mapping in mentee_mappings:
        profile = Profile.objects.filter(user=mapping.mentee.user).first()
        if profile and profile.moodle_id:
            mentees[profile.moodle_id] = mapping.mentee.user

    if moodle not in mentees:
        messages.error(request, "Selected Moodle ID is not one of your mentees.")
        return redirect("mentee_documents")

    mentee_user = mentees[moodle]

    # collect files (FileField instances) and labels
    files_to_zip = []  # list of tuples: (filesystem_path, arcname)
    # helper to append if file present
    def try_add(filefield, label_prefix):
        # filefield expected to be a FieldFile (or None)
        if filefield:
            try:
                fs_path = filefield.path  # filesystem path
            except Exception:
                # fallback: try url -> not archive if no path
                fs_path = None
            if fs_path and os.path.exists(fs_path):
                # prepare a safe arcname within zip
                basename = os.path.basename(fs_path)
                arcname = f"{label_prefix} - {basename}"
                files_to_zip.append((fs_path, arcname))

    # gather from models (same categories as earlier)
    for item in InternshipPBL.objects.filter(user=mentee_user):
        try_add(item.certificate, f"Internship_PBL_{(item.title or '').strip()[:40]}")

    for item in SportsCulturalEvent.objects.filter(user=mentee_user):
        try_add(item.certificate, f"Sports_{(item.name_of_event or '').strip()[:40]}")

    for item in OtherEvent.objects.filter(user=mentee_user):
        try_add(item.certificate, f"OtherEvent_{(item.name_of_event or '').strip()[:40]}")

    for item in CertificationCourse.objects.filter(user=mentee_user):
        try_add(item.certificate, f"Course_{(item.title or '').strip()[:40]}")

    for item in PaperPublication.objects.filter(user=mentee_user):
        try_add(item.certificate, f"Publication_{(item.title or '').strip()[:40]}")

    for item in SemesterResult.objects.filter(user=mentee_user):
        try_add(item.marksheet, f"Marksheet_Sem{(item.semester or '')}")

    if not files_to_zip:
        messages.info(request, "No documents available to download for this student.")
        return redirect("mentee_documents")

    # create in-memory zip
    zip_filename = f"{moodle}_documents.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fs_path, arcname in files_to_zip:
            # arcname must be unique / safe
            # sanitize arcname
            safe_name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in arcname)
            # ensure unique if duplicates
            counter = 1
            candidate = safe_name
            while candidate in zf.namelist():
                candidate = f"{os.path.splitext(safe_name)[0]}_{counter}{os.path.splitext(safe_name)[1]}"
                counter += 1
            zf.write(fs_path, arcname=candidate)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return response

# Download student data in excel
# Mapping of all models and their fields
CATEGORY_MAP = {
    "internship": (
        "Internships/PBL",
        InternshipPBL,
        ["title", "academic_year", "semester", "type", "company_name",
         "start_date", "end_date", "no_of_days"]
    ),

    "projects": (
        "Projects",
        Project,
        ["title", "academic_year", "semester", "project_type",
         "guide_name", "link"]
    ),

    "sports": (
        "Sports/Cultural",
        SportsCulturalEvent,
        ["name_of_event", "academic_year", "semester", "type",
         "venue", "level", "prize_won"]
    ),

    "certifications": (
        "Courses/Certifications",
        CertificationCourse,
        ["title", "academic_year", "semester", "domain", "level",
         "start_date", "end_date", "no_of_days"]
    ),

    "other": (
        "Other Achievements",
        OtherEvent,
        ["name_of_event", "academic_year", "semester", "level",
         "details", "prize_won", "amount_won"]
    ),

    "publications": (
        "Paper Publications",
        PaperPublication,
        ["title", "academic_year", "semester", "type", "level",
         "authors", "amount_reimbursed"]
    ),
}


# Category mapping
CATEGORY_MODELS = {
    "internship": InternshipPBL,
    "projects": Project,
    "sports": SportsCulturalEvent,
    "other": OtherEvent,
    "courses": CertificationCourse,
    "publications": PaperPublication,
}


@login_required
def download_student_data(request):
    """
    Mentor-only view to download mentees' data.
    POST params:
      - category (all|internship|projects|sports|other|courses|publications)
      - year (e.g. 2023-24 or ALL)
      - branch (ALL or branch code)
      - export (excel|pdf|zip)
    """

    # --- basic context & permission check ---
    mentor = get_object_or_404(Mentor, user=request.user)
    mentee_mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")
    user_list = [m.mentee.user for m in mentee_mappings]

    profiles_qs = Profile.objects.filter(user__in=user_list)

    context = {
        "mentees": profiles_qs,
        "categories": [
            ("all", "ALL Categories (Combined)"),
            ("internship", "Internship / PBL"),
            ("projects", "Projects"),
            ("sports", "Sports & Cultural"),
            ("other", "Other Achievements / Hackathons"),
            ("courses", "Courses / Certifications"),
            ("publications", "Paper Publications"),
        ],
        "years": [f"{y}-{str(y+1)[-2:]}" for y in range(2017, 2027)],
        "branches": ["ALL", "IT", "CSE", "AIML", "DS", "MECH", "CIVIL"],
    }

    if request.method == "GET":
        return render(request, "mentor/download_student_data.html", context)

    # --- Read POST inputs ---
    category = request.POST.get("category", "all")
    academic_year = request.POST.get("year", "ALL")
    branch = request.POST.get("branch", "ALL")
    export_type = request.POST.get("export", "excel")  # excel|pdf|zip

    # Branch filter on profiles (applies globally)
    if branch != "ALL":
        profiles_qs = profiles_qs.filter(branch=branch)

    # Helper: get profile for a user (cached by dict for speed)
    profile_map = {p.user_id: p for p in profiles_qs}
    def profile_for_user(user):
        return profile_map.get(user.pk)

    # --- Collect rows for a model safely ---
    def collect_entries(model):
        qs = model.objects.filter(user__in=user_list)

        # Only filter by academic_year if model actually has this field and user selected a specific year
        if academic_year and academic_year != "ALL":
            if "academic_year" in [f.name for f in model._meta.fields]:
                qs = qs.filter(academic_year=academic_year)

        # If branch selected, limit to users whose Profile branch matches
        if branch != "ALL":
            valid_user_ids = list(profiles_qs.values_list("user_id", flat=True))
            qs = qs.filter(user__in=valid_user_ids)

        rows = []
        for obj in qs.select_related("user"):
            prof = profile_for_user(obj.user)
            base = {
                "moodle_id": prof.moodle_id if prof else getattr(obj.user, "username", ""),
                "student_name": prof.student_name if prof else getattr(obj.user, "username", ""),
                "email": prof.email if prof and prof.email else (obj.user.email if hasattr(obj.user, "email") else ""),
                "branch": prof.branch if prof else "",
                "_model": model.__name__,
                "_pk": obj.pk,
            }

            # iterate model fields and capture values (exclude id,user)
            for f in model._meta.fields:
                if f.name in ("id", "user", "certificate", "certificates"):
                    continue
                val = getattr(obj, f.name)

                # datetime tz fix
                if hasattr(val, "tzinfo") and val.tzinfo:
                    val = val.replace(tzinfo=None)

                # FileField -> output URL (if present) else file name
                from django.db.models.fields.files import FieldFile
                if isinstance(val, FieldFile):
                    if val and getattr(val, "name", ""):
                        try:
                            # prefer absolute url if available
                            url = val.url
                            full_url = request.build_absolute_uri(url)
                            val = full_url
                        except Exception:
                            val = val.name or ""
                    else:
                        val = ""

                # coerce to string for safe storage in collected rows
                if isinstance(val, (list, dict)):
                    # JSON-serialize complex types
                    try:
                        val = json.dumps(val, default=str)
                    except:
                        val = str(val)
                elif val is None:
                    val = ""

                base[f.name] = val
            base.pop("certificate", None)
            base.pop("certificates", None)
            rows.append(base)
        return rows

    # --- Build collected dict for chosen categories ---
    collected = {}
    for key, model in CATEGORY_MODELS.items():
        if category != "all" and category != key:
            continue
        collected[key] = collect_entries(model)

    # --- Helpers used by Excel builder ---
    def auto_adjust(ws):
        """Auto adjust column widths"""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    v = str(cell.value) if cell.value is not None else ""
                    if len(v) > max_len:
                        max_len = len(v)
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 4, 80)

    # -------------------------
    # Build Excel workbook
    # -------------------------
    def build_excel_workbook():
        wb = openpyxl.Workbook()
        cover = wb.active
        cover.title = "Cover"
        cover["A1"] = "APSIT - Student Data Export"
        cover["A1"].font = Font(size=18, bold=True)
        cover["A3"] = "Generated by:"
        cover["B3"] = request.user.get_full_name() or request.user.username
        cover["A4"] = "Generated on:"
        cover["B4"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cover["A5"] = "Selected Category:"
        cover["B5"] = category
        cover["A6"] = "Academic Year:"
        cover["B6"] = academic_year
        cover["A7"] = "Branch:"
        cover["B7"] = branch

        # Summary sheet
        summary = wb.create_sheet("Summary")
        summary["A1"] = "Summary Analytics"
        summary["A1"].font = Font(size=14, bold=True)

        total_mentees = profiles_qs.count()
        total_docs = sum(len(collected.get(k, [])) for k in collected)
        summary_data = [
            ("Total Mentees", total_mentees),
            ("Total Records (selected categories)", total_docs),
        ]

        # Add counts for each category + subcounts
        if "internship" in collected:
            ints = collected["internship"]
            summary_data.append(("Total Internships/PBL Records", len(ints)))
            type_counter = Counter([r.get("type") for r in ints if r.get("type")])
            for t, c in type_counter.items():
                summary_data.append((f"Internship Type: {t}", c))

        if "projects" in collected:
            summary_data.append(("Total Projects Records", len(collected["projects"])))

        if "sports" in collected:
            summary_data.append(("Total Sports/Cultural Records", len(collected["sports"])))
            level_counts = Counter([r.get("level") for r in collected["sports"] if r.get("level")])
            for lvl, c in level_counts.items():
                summary_data.append((f"Sports Level: {lvl}", c))

        if "other" in collected:
            summary_data.append(("Total Other Achievements Records", len(collected["other"])))
            prize_counts = Counter([r.get("prize_won") for r in collected["other"] if r.get("prize_won")])
            for p, c in prize_counts.items():
                summary_data.append((f"Prize Won ({p})", c))

        if "courses" in collected:
            summary_data.append(("Total Certifications Records", len(collected["courses"])))
            auth_counts = Counter([r.get("certifying_authority") for r in collected["courses"] if r.get("certifying_authority")])
            for a, c in auth_counts.items():
                summary_data.append((f"Authority: {a}", c))

        if "publications" in collected:
            summary_data.append(("Total Publications Records", len(collected["publications"])))
            pub_counts = Counter([r.get("type") for r in collected["publications"] if r.get("type")])
            for t, c in pub_counts.items():
                summary_data.append((f"Publication Type: {t}", c))

        # write summary_data
        r = 3
        for k, v in summary_data:
            summary[f"A{r}"] = k
            summary[f"B{r}"] = v
            r += 1

        # Branch x Category matrix
        branches = ["IT", "CSE", "AIML", "DS", "MECH", "CIVIL"]
        categories = list(CATEGORY_MODELS.keys())
        matrix_start_row = r + 2
        summary.cell(row=matrix_start_row, column=1, value="Branch-wise Total Records").font = Font(size=12, bold=True)

        header_row_idx = matrix_start_row + 1
        # header
        for ci, h in enumerate(["Branch"] + [c.title() for c in categories], start=1):
            summary.cell(row=header_row_idx, column=ci, value=h)

        # data rows
        for bi, br in enumerate(branches, start=header_row_idx + 1):
            summary.cell(row=bi, column=1, value=br)
            for ci, cat in enumerate(categories, start=2):
                cnt = sum(1 for rdict in collected.get(cat, []) if rdict.get("branch") == br)
                summary.cell(row=bi, column=ci, value=cnt)

        auto_adjust(summary)

        # Create per-category sheets with table & autofilter
        for key, rows in collected.items():
            sheet_name = key.upper()[:31]
            sheet = wb.create_sheet(sheet_name)
            if not rows:
                sheet.append(["No records found"])
                continue

            # columns from first row (stable ordering)
            first = rows[0]
            cols = [c for c in first.keys() if not c.startswith("_")]
            sheet.append(cols)

            for rdict in rows:
                row = [rdict.get(c, "") for c in cols]
                sheet.append(row)

            # format table & autofilter
            sheet.freeze_panes = sheet["A2"]
            table_ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"
            table = Table(displayName=f"{key}_table", ref=table_ref)
            style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False,
                                   showLastColumn=False, showRowStripes=True, showColumnStripes=False)
            table.tableStyleInfo = style
            sheet.add_table(table)

            auto_adjust(sheet)
        return wb

    # -------------------------
    # Build PDF bytes (ReportLab)
    # -------------------------
    def add_footer(canvas, doc):
        canvas.setFont("Helvetica", 9)

        # --- Page number ---
        page_num_text = f"Page {canvas.getPageNumber()}"

        # --- Mentor name ---
        mentor_name = (
                doc._request.user.mentor.name
                or doc._request.user.get_full_name()
                or doc._request.user.username
        )
        mentor_text = f"Mentor: {mentor_name}"

        # --- Bottom Y position ---
        y = 1 * cm

        # Page number (center)
        canvas.drawCentredString(A4[0] / 2.0, y, page_num_text)

        # Left text (mentor)
        canvas.drawString(1.5 * cm, y, mentor_text)

    def build_pdf_bytes():
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm)
        # inject request for footer
        doc._request = request
        story = []
        styles = getSampleStyleSheet()
        heading_style = styles["Heading1"]
        heading_style.fontSize = 16

        # logo
        logo_path = os.path.join(settings.MEDIA_ROOT, "logo.png")
        if os.path.exists(logo_path):
            try:
                img = RLImage(logo_path, width=2.5 * cm, height=2 * cm)
            except Exception:
                img = None

        # header
        header_cells = []
        if img:
            header_cells.append(img)
        header_cells.append(Paragraph("<b>APSIT - Student Data</b>", heading_style))
        header_table = RLTable([[header_cells[0] if img else "", header_cells[-1]]], colWidths=[2.4 * cm, 14 * cm])
        story.append(header_table)
        story.append(Spacer(1, 8))
        meta = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Mentor: {request.user.mentor.name or request.user.get_full_name() or request.user.username}"
        story.append(Paragraph(meta, styles["Normal"]))
        story.append(Spacer(1, 12))

        # each category
        small_para_style = ParagraphStyle('small', fontSize=8, leading=10)
        for key, rows in collected.items():
            title = key.replace("_", " ").title()
            story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
            if not rows:
                story.append(Paragraph("<i>No records found.</i>", styles["BodyText"]))
                story.append(PageBreak())
                continue

            # columns
            first = rows[0]
            cols = [c for c in first.keys() if not c.startswith("_")]
            data = [cols]
            for rdict in rows:
                data.append([str(rdict.get(c, "") or "") for c in cols])

            # convert to Paragraphs so cell text wraps
            wrapped = []
            for row in data:
                wrapped_row = [Paragraph(cell.replace("\n", "<br/>"), small_para_style) for cell in row]
                wrapped.append(wrapped_row)

            page_width = A4[0] - (doc.leftMargin + doc.rightMargin)
            col_count = max(1, len(cols))
            col_width = page_width / col_count
            col_widths = [col_width] * col_count

            tbl = RLTable(wrapped, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(RLTableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3f5cbf")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(tbl)
            story.append(PageBreak())

        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        buffer.seek(0)
        return buffer

    # -------------------------
    # Build CSV & JSON for zip
    # -------------------------
    def build_csv_and_json():
        files = {}
        import csv
        from io import StringIO

        for key, rows in collected.items():
            if not rows:
                continue

            # -----------------------
            # CSV (StringIO → encode)
            # -----------------------
            csv_io = StringIO()
            writer = csv.writer(csv_io)

            first = rows[0]
            cols = [c for c in first.keys() if not c.startswith("_")]
            writer.writerow(cols)

            for r in rows:
                writer.writerow([r.get(c, "") for c in cols])

            files[f"{key}.csv"] = csv_io.getvalue().encode("utf-8")

            # -----------------------
            # JSON
            #------------------------
            files[f"{key}.json"] = json.dumps(rows, default=str, indent=2).encode("utf-8")

        return files

    # -------------------------
    # Deliver based on export_type
    # -------------------------
    if export_type == "pdf":
        request.session["export_done"] = True
        pdf_buf = build_pdf_bytes()
        return FileResponse(pdf_buf, as_attachment=True, filename=f"{category}_AY-{academic_year}_{branch}-Dept_student_data.pdf")

    if export_type == "excel":
        request.session["export_done"] = True
        wb = build_excel_workbook()
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return FileResponse(out, as_attachment=True, filename=f"Excel_{category}_AY-{academic_year}_{branch}-Dept_student_data.xlsx", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if export_type == "zip":
        request.session["export_done"] = True
        wb = build_excel_workbook()
        excel_buf = BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)
        pdf_buf = build_pdf_bytes()
        csvs = build_csv_and_json()

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"Excel_{category}_AY-{academic_year}_{branch}-Dept_student_data.xlsx", excel_buf.getvalue())
            zf.writestr(f"{category}_AY-{academic_year}_{branch}-Dept_student_data.pdf", pdf_buf.getvalue())
            for name, data in csvs.items():
                zf.writestr(name, data)
        zip_buffer.seek(0)
        return FileResponse(zip_buffer, as_attachment=True, filename=f"{category}_AY-{academic_year}_{branch}-Dept_student_data_bundle.zip")

    # fallback
    return render(request, "mentor/download_student_data.html", context)


@login_required
def clear_export_flag(request):
    request.session.pop("export_done", None)
    return HttpResponse("OK")


@method_decorator(login_required, name='dispatch')
class MessageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """controls message view"""

    template_name = 'mentor/messages-module1.html'
    model = Msg

    def test_func(self):
        return self.request.user.is_mentor

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['count'] = Msg.objects.filter(receipient=self.request.user).filter(is_approved=False).count()
        context['count1'] = Msg.objects.filter(receipient=self.request.user).filter(is_approved=True).count()
        context['count2'] = Conversation.objects.filter(sender=self.request.user).count()
        return context

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)

@method_decorator(login_required, name='dispatch')
class MessageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Creates new message"""

    fields = ('receipient', 'msg_content')
    model = Msg
    template_name = 'mentor/messagecreate1.html'

    def test_func(self):
        return self.request.user.is_mentor

    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('list1')

@method_decorator(login_required, name='dispatch')
class MessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List sent Messages"""

    model = Msg
    template_name = 'mentor/listmessages1.html'
    context_object_name = 'sentmesso'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)

@method_decorator(login_required, name='dispatch')
class SentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """details the message sent"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'mentor/sent1.html'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)

@method_decorator(login_required, name='dispatch')
class SentMessageDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Deletes sent messages"""

    model = Msg
    success_url = reverse_lazy("list1")
    template_name = 'mentor/sentmessage_delete1.html'

    def test_func(self):
        return self.request.user.is_mentor

@method_decorator(login_required, name='dispatch')
class InboxView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """ Lists messages in inbox view"""

    def test_func(self):
        return self.request.user.is_mentor

    model = Msg
    context_object_name = 'inbox'
    template_name = 'mentor/inbox1.html'
    paginate_by = 5

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user).filter(is_approved=False)

@method_decorator(login_required, name='dispatch')
class InboxDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Inbox Detailed view"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'mentor/inboxview1.html'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


@login_required
def reply_message(request, pk):
    """Replies, approves, comments on messages"""

    if not request.user.is_mentor:
        return redirect('home')

    reply = get_object_or_404(Msg, pk=pk, receipient=request.user)

    if request.method == 'POST':

        form = ReplyForm(request.POST)

        if form.is_valid():
            reply.is_approved = form.cleaned_data['is_approved']
            reply.comment = form.cleaned_data['comment']
            reply.save()

            return redirect('inbox2')

    else:

        form = ReplyForm

    context = {
        'messo': reply,
        'reply': reply,
        'form': form,
    }

    return render(request, 'mentor/comment.html', context)

@method_decorator(login_required, name='dispatch')
class Approved(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """view list of approved messeges from mentors"""

    def test_func(self):
        return self.request.user.is_mentor

    # def get(self, request):

    # messo = Msg.objects.filter(is_approved=True).order_by('-date_approved')

    # context = {

    # 'messo': messo,

    # }

    # return render(request, "menti/approved.html", context)

    model = Msg.objects.filter(is_approved=True).order_by('-date_approved')

    template_name = 'mentor/approved.html'

    context_object_name = 'messo'

    paginate_by = 5

    def get_queryset(self):
        return self.model.filter(receipient=self.request.user)


@method_decorator(login_required, name='dispatch')
class ProfileDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """view details of a user in the profile"""

    model = Msg
    context_object_name = 'msg'
    template_name = 'mentor/profile_detail1.html'

    def test_func(self):
        return self.request.user.is_mentor


@method_decorator(login_required, name='dispatch')
class ConversationCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    """Create Conversation"""

    fields = ('conversation',)
    model = Conversation
    template_name = 'mentor/chat.html'
    context_object_name = 'conversation'
    success_message = 'Your Conversation Has been Created!'

    def test_func(self):
        return self.request.user.is_mentor

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.receipient = User.objects.get(pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('conv1')


@method_decorator(login_required, name='dispatch')
class ConversationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List all chat conversation by a user"""

    model = Conversation
    template_name = 'mentor/list-converations.html'
    context_object_name = 'conversation'
    paginate_by = 4

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


"""List all chat conversation by a user"""
# class ConverationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):

# fields = ('reply',)
# model = Conversation
# template_name = 'mentor/conversation.html'
# context_object_name = 'conversation'

# def test_func(self):
# return self.request.user.is_mentor

# def form_valid(self, form):
# form.instance.sender = self.request.user
# form.instance.receipient = User.objects.get(pk=self.kwargs['pk'])
# return super().form_valid(form)

# def get_success_url(self):
# return reverse('conv1')


# def get_queryset(self):
# return self.model.objects.filter(sender=self.request.user)


@method_decorator(login_required, name='dispatch')
class ReplyCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    """Replies by a user"""

    fields = ('reply',)
    model = Reply
    template_name = 'mentor/conversation.html'
    success_message = 'You have replied!'

    def test_func(self):
        return self.request.user.is_mentor

    def form_valid(self, form):
        form.instance.sender = self.request.user
        form.instance.conversation = Conversation.objects.get(pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv-reply', kwargs={'pk': self.object.conversation_id})

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


@method_decorator(login_required, name='dispatch')
class ConversationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Conversation
    template_name = 'mentor/conversation1.html'
    context_object_name = 'conv'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        from django.db.models import Q
        return Conversation.objects.filter(
            Q(sender=self.request.user) | Q(receipient=self.request.user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ChatReplyForm()
        context["is_mentor_view"] = True
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = ChatReplyForm(request.POST, request.FILES)

        if form.is_valid():
            reply = Reply()
            reply.reply = request.POST.get("reply")
            reply.file = request.FILES.get("file")
            reply.sender = request.user
            reply.conversation = self.object
            reply.replied_at = now()
            reply.save()

            return redirect('conv-reply', pk=self.object.pk)

        context = self.get_context_data(object=self.object)
        context['form'] = form
        return self.render_to_response(context)



@method_decorator(login_required, name='dispatch')
class ConversationDeleteView(SuccessMessageMixin, DeleteView):
    """delete view Chat"""

    model = Reply
    template_name = 'mentor/chat-confirm-delete.html'
    success_message = 'Your message has been deleted!'

    # success_url = reverse_lazy('conv1')

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv-reply', kwargs={'pk': self.object.conversation_id})


@method_decorator(login_required, name='dispatch')
class Conversation2DeleteView(DeleteView):
    """delete view Coversation"""

    model = Conversation
    template_name = 'mentor/conversation-confirm-delete.html'

    # success_url = reverse_lazy('conv1')

    def get_success_url(self):
        return reverse_lazy('conv1')


@method_decorator(login_required, name='dispatch')
class MentorMeetingListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Meeting
    template_name = 'mentor/vc.html'  # You’ll create this template
    context_object_name = 'meetings'
    paginate_by = 5

    def test_func(self):
        return self.request.user.is_mentor  # Ensure only mentors can access

    def get_queryset(self):
        queryset = Meeting.objects.filter(
            mentor__user=self.request.user
        ).order_by('-appointment_date', '-time_slot')

        for meeting in queryset:
            combined_datetime = datetime.combine(meeting.appointment_date, meeting.time_slot)
            if timezone.is_naive(combined_datetime):
                combined_datetime = timezone.make_aware(combined_datetime, timezone.get_current_timezone())

            # Instead of assigning to meeting.meeting_datetime (which is a read-only property),
            # Assign to a custom attribute for temporary use in the view or template
            meeting._meeting_datetime = combined_datetime
            meeting._meeting_end_datetime = combined_datetime + timedelta(hours=1)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.localtime(timezone.now())
        return context


@login_required
def mentor_queries(request):
    # Get the Mentor instance linked to the logged-in user
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        # maybe the user is actually a mentee
        return redirect('mentee_queries')
    # Now filter queries for this mentor instance
    queries = Query.objects.filter(mentor=mentor).order_by('-created_at')

    return render(request, "mentor/mentor_queries.html", {"queries": queries})


@login_required
def mark_as_done(request, query_id):
    query = get_object_or_404(Query, id=query_id)
    query.status = "resolved"
    query.save()

    # Notify mentee (basic message, can extend to email/websocket)
    messages.success(request, f"Query from {query.mentee} has been resolved.")
    return redirect(reverse('mentor_queries'))


def send_forget_password_email(email, token):
    try:
        subject = 'Reset Your Password'
        reset_link = f'http://127.0.0.1:8000/change-pass/{token}/'
        message = f"""
        Hi,

        You requested a password reset. Click the link below to reset your password:

        {reset_link}

        If you did not request this, please ignore this email.

        Regards,
        APSIT
        """
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]

        send_mail(subject, message.strip(), email_from, recipient_list)
        print("✅ Reset email sent successfully.")
        return True

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False


def ForgetPass(request):
    try:
        if request.method == 'POST':
            username = request.POST.get('username')
            print(f"Submitted username: {username}")

            # Find the user by username
            user_obj = User.objects.filter(username=username).first()
            if not user_obj:
                messages.error(request, 'No user found with this username.')
                return render(request, 'mentor/forget-pass.html')

            # Get the user's profile
            profile_obj = Profile.objects.filter(user=user_obj).first()
            if not profile_obj:
                messages.error(request, 'Profile not found for this user.')
                return render(request, 'mentor/forget-pass.html')

            # Create token and save
            token = str(uuid.uuid4())
            profile_obj.forget_password_token = token
            profile_obj.save()

            # Send email
            send_forget_password_email(user_obj.email, token)

            messages.success(request, 'Password reset link has been sent to your email.')
            return render(request, 'mentor/forget-pass.html')

    except Exception as e:
        print("Error in ForgetPassword:")
        traceback.print_exc()
        messages.error(request, 'Something went wrong. Please try again.')

    return render(request, 'mentor/forget-pass.html')
def ChangePass(request, token):
    try:
        profile_obj = Profile.objects.filter(forget_password_token=token).first()

        if not profile_obj:
            messages.error(request, "Invalid or expired token.")
            return redirect('login1')

        context = {
            'user_id': profile_obj.user.id,
            'token': token
        }

        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('reconfirm_password')

            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'mentor/change-pass.html', context)

            user = profile_obj.user
            user.set_password(new_password)
            user.save()

            profile_obj.forget_password_token = None
            profile_obj.save()

            messages.success(request, 'Password updated successfully.')
            return redirect('login1')     # Mentor login

        return render(request, 'mentor/change-pass.html', context)

    except Exception as e:
        print("Error in ChangePass:", e)
        messages.error(request, "Something went wrong. Try again.")
        return redirect('forget_pass')


COMMON_AGENDA_POINTS = [
    "Academic performance review",
    "75% Attendance compulsory",
    "Internship / Project progress",
    "Career guidance & higher studies",
    "Personal or behavioural concerns",
]


@login_required
def mentor_mentee_interactions(request):

    mentor = get_object_or_404(Mentor, user=request.user)

    # ✅ Get mentees under this mentor
    mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")
    mentee_users = [m.mentee.user for m in mappings]
    mentee_profiles = Profile.objects.filter(user__in=mentee_users)

    # ✅ Filtering
    semester_filter = request.GET.get("semester")
    date_filter = request.GET.get("date")

    interactions = MentorMenteeInteraction.objects.filter(mentor=request.user)

    if semester_filter:
        interactions = interactions.filter(semester=semester_filter)

    if date_filter:
        interactions = interactions.filter(date=date_filter)

    # ✅ CREATE + UPDATE INTERACTION (SAME FORM)
    if request.method == "POST":
        interaction_id = request.POST.get("interaction_id")

        date = request.POST.get("date")
        mentee_ids = request.POST.getlist("mentees")
        checked_points = request.POST.getlist("agenda_points")
        extra_text = request.POST.get("agenda_extra", "").strip()

        # ✅ FIXED: Auto semester from SELECTED mentees only
        semester = ""
        selected_profiles = Profile.objects.filter(user__id__in=mentee_ids)
        if selected_profiles.exists():
            semester = ", ".join(
                selected_profiles.values_list("semester", flat=True).distinct()
            )

        # ✅ Build agenda safely
        agenda_parts = checked_points[:]
        if extra_text:
            agenda_parts.append(extra_text)
        agenda_text = "; ".join(agenda_parts)

        # ✅ UPDATE EXISTING
        if interaction_id:
            interaction = get_object_or_404(
                MentorMenteeInteraction, id=interaction_id, mentor=request.user
            )
            interaction.date = date
            interaction.semester = semester
            interaction.agenda = agenda_text
            interaction.save()
            interaction.mentees.set(User.objects.filter(id__in=mentee_ids))

            messages.success(request, "Interaction updated successfully.")

        # ✅ CREATE NEW
        else:
            interaction = MentorMenteeInteraction.objects.create(
                mentor=request.user,
                date=date,
                semester=semester,
                agenda=agenda_text,
            )
            interaction.mentees.set(User.objects.filter(id__in=mentee_ids))

            messages.success(request, "Interaction saved successfully.")

        return redirect("mentor_interaction")

    # ✅ ATTENDANCE REPORT
    attendance = []
    total_interactions = interactions.count()

    for p in mentee_profiles:
        present = interactions.filter(mentees=p.user).count()
        percent = round((present / total_interactions) * 100, 2) if total_interactions else 0

        attendance.append({
            "name": p.student_name,
            "semester": p.semester,
            "branch": p.branch,
            "moodle": p.moodle_id,
            "percent": percent
        })
    #monthly attendance
    monthly_raw = (
        interactions
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    monthly_attendance = []

    for row in monthly_raw:
        month_name = row["month"].strftime("%b %Y")
        percent = round((row["total"] / total_interactions) * 100, 2) if total_interactions else 0
        monthly_attendance.append({
            "month": month_name,
            "percent": percent
        })
    context = {
        "mentor": mentor,
        "mentees": mentee_profiles,
        "interactions": interactions.order_by("-date"),
        "common_agenda": COMMON_AGENDA_POINTS,
        "attendance": attendance,
        "semesters": [s for s in SEMESTER],
        "monthly_attendance": monthly_attendance,
    }

    return render(request, "mentor/mentor_mentee_interactions.html", context)


@login_required
def delete_interaction(request, pk):
    interaction = get_object_or_404(MentorMenteeInteraction, pk=pk, mentor=request.user)
    interaction.delete()
    messages.success(request, "Interaction deleted.")
    return redirect("mentor_interaction")


@login_required
def regenerate_ai_summary(request, pk):
    interaction = get_object_or_404(MentorMenteeInteraction, id=pk, mentor=request.user)

    # ✅ Call your AI generator here
    summary = generate_ai_summary(interaction.agenda)

    interaction.ai_summary = summary
    interaction.save()

    return JsonResponse({
        "success": True,
        "summary": interaction.ai_summary
    })


@login_required
def export_interactions(request, export_type):
    mentor = get_object_or_404(Mentor, user=request.user)
    qs = MentorMenteeInteraction.objects.filter(mentor=request.user).prefetch_related("mentees__profile")

    # ✅ EXCEL
    if export_type == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Date", "Semester", "Agenda", "AI Summary", "Mentees"])

        for i in qs:
            mentees = ", ".join([
                f"{u.profile.student_name} ({u.profile.moodle_id})"
                for u in i.mentees.all()
            ])

            ws.append([
                i.date.strftime("%d-%m-%Y"),
                i.semester,
                i.agenda,
                i.ai_summary or "Not Generated",
                mentees
            ])

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return FileResponse(buf, as_attachment=True, filename="Mentor_Mentee_interactions.xlsx")

    # ✅ PDF EXPORT (FIXED FORMATTING)
    buffer = BytesIO()

    # ✅ Convert Agenda & AI Summary into Bullet List
    def bulletize(text):
        if not text:
            return ""

        text = text.strip()

        # ✅ REMOVE any existing <link> tags (prevents duplication)
        text = re.sub(r"<link[^>]*>|</link>", "", text)

        # ✅ 1. Protect URLs with tokens
        url_pattern = r"(https?://[^\s]+)"
        urls = re.findall(url_pattern, text)

        url_map = {}
        for i, url in enumerate(urls):
            token = f"[[URL_{i}]]"
            url_map[token] = url
            text = text.replace(url, token)

        # ✅ 2. Normalize separators
        text = text.replace("•", ".")
        text = text.replace("\n", ".")
        text = text.replace(";", ".")

        # ✅ 3. Split into sentences safely
        sentences = re.split(r"\.(?=\s|$)", text)

        bullets = []

        for s in sentences:
            s = s.strip()
            if not s:
                continue

            # ✅ 4. Restore each URL as BLUE + UNDERLINED clickable link
            for token, url in url_map.items():
                s = s.replace(
                    token,
                    f'<font color="blue"><u><link href="{url}">{url}</link></u></font>'
                )

            # ✅ 5. Escape only normal text
            s = escape(s, quote=False)

            # ✅ Un-escape the tags we intentionally inserted
            s = s.replace("&lt;font", "<font").replace("&lt;/font&gt;", "</font>")
            s = s.replace("&lt;u&gt;", "<u>").replace("&lt;/u&gt;", "</u>")
            s = s.replace("&lt;link", "<link").replace("&lt;/link&gt;", "</link>")
            s = s.replace("&gt;", ">")

            bullets.append("• " + s)

        return "<br/>".join(bullets)

    # ✅ HIGH-RES PDF (Better Printing)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=110,
        bottomMargin=90
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BlueLink",
        parent=styles["Normal"],
        textColor=colors.blue,
        underline=True
    ))
    story = []

    # ✅ EXPORT DATE (TODAY)
    export_date = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    # ✅ GET UNIQUE DEPARTMENTS & SEMESTERS FROM MENTEES
    mentee_departments = set()
    mentee_semesters = set()

    for i in qs:
        for u in i.mentees.all():
            if hasattr(u, "profile"):
                if u.profile.branch:
                    mentee_departments.add(u.profile.branch)
                if u.profile.semester:
                    mentee_semesters.add(u.profile.semester)

    department = ", ".join(sorted(mentee_departments)) if mentee_departments else "Not Available"
    semester_filter = ", ".join(sorted(mentee_semesters)) if mentee_semesters else "Not Available"

    # ✅ HEADER DETAILS
    header_info = f"""
    <b>Department:</b> {department} &nbsp;&nbsp;&nbsp;&nbsp;
    <b>Semester:</b> {semester_filter} <br/>
    <b>Generated on:</b> {export_date}
    """

    # ✅ TABLE DATA
    data = [["Sr. No.", "Date", "Sem", "Agenda", "AI Summary", "Mentees"]]

    for idx, i in enumerate(qs, start=1):
        mentee_lines = []

        for u in i.mentees.all():
            if hasattr(u, "profile"):
                name = u.profile.student_name
                dept = u.profile.branch if u.profile.branch else "N/A"
                moodle = u.profile.moodle_id if u.profile.moodle_id else "N/A"

                mentee_lines.append(f"{name} ({dept}, {moodle})")

        mentees_formatted = "<br/>".join(mentee_lines)

        agenda_paragraph = Paragraph(bulletize(i.agenda), styles["Normal"])
        ai_summary_paragraph = Paragraph(
            bulletize(i.ai_summary or "Not Generated"),
            styles["Normal"]
        )

        data.append([
            str(idx),
            i.date.strftime("%d-%m-%Y"),
            i.semester,
            agenda_paragraph,
            ai_summary_paragraph,
            Paragraph(mentees_formatted, styles["Normal"]),
        ])

    # ✅ COLUMN WIDTHS (PRINT OPTIMIZED)
    table = RLTable(
        data,
        colWidths=[33, 56, 28, 160, 160, 150],  # ✅ wider AI + Agenda
        repeatRows=1
    )

    # ✅ TABLE STYLING
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

        # ✅ Vertical alignment
        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        # ✅ AUTO WORD WRAP (CRITICAL FIX)
        ("WORDWRAP", (0, 0), (-1, -1), "CJK"),

        # ✅ Font control
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),

        # ✅ Padding (PREVENT OVERLAP)
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(table)
    story.append(Spacer(1, 40))
    # ✅ ATTENDANCE SUMMARY TABLE (PER MENTEE)

    # ✅ Get unique mentees from queryset
    attendance_map = {}

    total_interactions = qs.count()

    for interaction in qs:
        for u in interaction.mentees.all():
            if hasattr(u, "profile"):
                key = u.profile.moodle_id
                if key not in attendance_map:
                    attendance_map[key] = {
                        "name": u.profile.student_name,
                        "dept": u.profile.branch if u.profile.branch else "N/A",
                        "moodle": u.profile.moodle_id,
                        "present": 0,
                    }
                attendance_map[key]["present"] += 1

    # ✅ Build Attendance Table Data
    attendance_data = [["Sr. No.", "Name", "Department", "Moodle ID", "Present", "Attendance %"]]

    for idx, v in enumerate(attendance_map.values(), start=1):
        percent = round((v["present"] / total_interactions) * 100, 2) if total_interactions else 0
        attendance_data.append([
            str(idx),
            v["name"],
            v["dept"],
            v["moodle"],
            str(v["present"]),
            f"{percent}%",
        ])
    story.append(Spacer(1, 25))

    attendance_title = Paragraph("<b>Mentee Attendance Summary</b>", styles["Heading2"])
    story.append(attendance_title)
    story.append(Spacer(1, 10))

    attendance_table = RLTable(attendance_data, colWidths=[40, 130, 100, 100, 70, 90])

    attendance_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(attendance_table)

    # ✅ SIGNATURE SECTION
    sign_table = RLTable(
        [
            ["", ""],
            ["______________________________", "______________________________"],
            ["Mentor's Signature", "HOD / Coordinator Signature"]
        ],
        colWidths=[250, 250]
    )

    sign_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 20),
    ]))

    story.append(sign_table)

    # ✅ LOGO PATH
    logo_path = os.path.join(settings.MEDIA_ROOT, "logo.png")

    # ✅ FOOTER + PAGE NUMBER + LOGO
    def add_footer_and_page_number(canvas, doc):
        canvas.saveState()

        width, height = A4

        # ✅ WHITE BACKGROUND FOR LOGO
        canvas.setFillColor(colors.white)
        canvas.rect(30, height - 80, 90, 50, fill=1, stroke=0)

        # ✅ LOGO
        if os.path.exists(logo_path):
            canvas.drawImage(
                logo_path,
                35,
                height - 85,
                width=100,
                height=60,
                preserveAspectRatio=True,
                mask="auto"
            )

        # ✅ MAIN TITLE (FIRST PAGE)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.setFillColor(colors.black)

        if doc.page == 1:
            canvas.drawString(130, height - 50, "Mentor–Mentee Interaction Report")
        else:
            canvas.drawString(130, height - 50, "Mentor–Mentee Interaction Report")

        # ✅ HEADER DETAILS
        canvas.setFont("Helvetica", 10)
        header_y = height - 70
        canvas.drawString(130, header_y, f"Department: {department}")
        canvas.drawString(350, header_y, f"Semester: {semester_filter}")
        canvas.drawString(130, header_y - 15, f"Generated On: {export_date}")

        # ✅ FOOTER WITH MENTOR NAME
        mentor_name = mentor.name if mentor.name else mentor.user.get_full_name() or mentor.user.username
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, 30, f"Generated by Mentor: {mentor_name}")

        # ✅ PAGE NUMBER
        canvas.drawRightString(width - 36, 30, f"Page {doc.page}")

        canvas.restoreState()

    # ✅ BUILD DOCUMENT
    doc.build(
        story,
        onFirstPage=add_footer_and_page_number,
        onLaterPages=add_footer_and_page_number
    )

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="Mentor_Mentee_interactions.pdf")


@login_required
def student_visualization(request):
    internship_data = list(
        InternshipPBL.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    project_data = list(
        Project.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    sports_data = list(
        SportsCulturalEvent.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    course_data = list(
        CertificationCourse.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    hackathon_data = list(
        OtherEvent.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    paper_data = list(
        PaperPublication.objects.values("user__profile__branch")
        .annotate(total=Count("id"))
    )

    return render(request, "mentor/student_visualization.html", {
        "internship_data": internship_data,
        "project_data": project_data,
        "sports_data": sports_data,
        "course_data": course_data,
        "hackathon_data": hackathon_data,
        "paper_data": paper_data,
    })


@login_required
def get_chart_data(request):
    category = request.GET.get("category")

    model_map = {
        "internship": InternshipPBL,
        "project": Project,
        "sports": SportsCulturalEvent,
        "course": CertificationCourse,
        "other": OtherEvent,
        "paper": PaperPublication,
    }

    model = model_map.get(category)
    if not model:
        return JsonResponse({"labels": [], "data": []})

    data = (
        model.objects
        .values("user__profile__branch")
        .annotate(count=Count("id"))
        .order_by("user__profile__branch")
    )

    labels = [d["user__profile__branch"] or "Unknown" for d in data]
    counts = [d["count"] for d in data]

    return JsonResponse({
        "labels": labels,
        "data": counts,
    })
