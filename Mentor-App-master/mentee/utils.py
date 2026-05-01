from .models import (Profile, InternshipPBL, Project, CertificationCourse, PaperPublication, SportsCulturalEvent,
    OtherEvent, SemesterResult, EducationalDetail, StudentInterest, StudentProfileOverview)
from django.utils import timezone
from zoneinfo import ZoneInfo
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from collections import defaultdict
from django.db.models import Count
from itertools import chain

def compute_profile_completeness(user):
    """
    Returns (score_percentage, items_list)
    items_list = [{"label": "...", "done": True/False}]
    """

    items = []

    # 1. Basic profile
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        profile = None

    def filled(val):
        return bool(val)

    # Basic fields
    items.append({"label": "Name", "done": profile and filled(profile.student_name)})
    items.append({"label": "Branch/Year/Semester", "done": profile and filled(profile.branch) and filled(profile.year) and filled(profile.semester)})
    items.append({"label": "Contact & Email", "done": profile and filled(profile.contact_number) and filled(user.email)})
    items.append({"label": "Career Domain", "done": profile and filled(profile.career_domain)})
    items.append({"label": "About Me", "done": profile and filled(profile.about_me)})

    # 2. Education
    items.append({"label": "Pre-Engineering Education (SSC/HSC/Diploma)", "done": EducationalDetail.objects.filter(user=user).exists()})
    items.append({"label": "Semester Results", "done": SemesterResult.objects.filter(user=user).exists()})

    # 3. Experience / Projects / Certifications / Publications
    items.append({"label": "At least one Internship/PBL", "done": InternshipPBL.objects.filter(user=user).exists()})
    items.append({"label": "At least one Project", "done": Project.objects.filter(user=user).exists()})
    items.append({"label": "At least one Certification/Course", "done": CertificationCourse.objects.filter(user=user).exists()})
    items.append({"label": "At least one Paper/Publication", "done": PaperPublication.objects.filter(user=user).exists()})

    # 4. Achievements & Activities
    sports_or_other = SportsCulturalEvent.objects.filter(user=user).exists() or OtherEvent.objects.filter(user=user).exists()
    items.append({"label": "Sports/Cultural/Other Achievements", "done": sports_or_other})

    # 5. Interests & Goals
    items.append({"label": "Student Interests", "done": StudentInterest.objects.filter(student=user).exists()})
    items.append({"label": "Long Term Goal", "done": user.longtermgoal_set.exists()})

    # 6. Overview fields
    overview = StudentProfileOverview.objects.filter(user=user).first()
    items.append({"label": "Professional Summary", "done": overview and filled(overview.profile_summary)})
    items.append({"label": "Key Skills", "done": overview and filled(overview.key_skills)})

    total = len(items)
    done_count = sum(1 for i in items if i["done"])
    score = int((done_count / total) * 100) if total > 0 else 0

    # Optionally store score
    if overview:
        overview.completeness_score = score
        overview.save(update_fields=["completeness_score"])

    return score, items


def get_document_progress(user):
    """
    Returns (completed_count, total_required, has_pending)
    """

    has_internship = InternshipPBL.objects.filter(
        user=user, certificate__isnull=False
    ).exclude(certificate="").exists()

    has_marksheet = SemesterResult.objects.filter(
        user=user, marksheet__isnull=False
    ).exclude(marksheet="").exists()

    has_project = Project.objects.filter(user=user).exists()

    has_certification = CertificationCourse.objects.filter(
        user=user, certificate__isnull=False
    ).exclude(certificate="").exists()

    # has_publication = PaperPublication.objects.filter(
    #     user=user, certificate__isnull=False
    # ).exclude(certificate="").exists()
    #
    # has_sports = SportsCulturalEvent.objects.filter(
    #     user=user, certificate__isnull=False
    # ).exclude(certificate="").exists()
    #
    # has_other = OtherEvent.objects.filter(
    #     user=user, certificate__isnull=False
    # ).exclude(certificate="").exists()

    completed_count = sum([
        has_internship,
        has_marksheet,
        has_project,
        has_certification,
        # has_publication,
        # has_sports,
        # has_other,
    ])

    total_required = 4
    has_pending = completed_count < total_required

    return completed_count, total_required, has_pending


IST = ZoneInfo("Asia/Kolkata")

def to_ist(dt):
    """Convert UTC datetime → IST, return formatted string."""
    if not dt:
        return ""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.astimezone(IST).strftime("%d-%m-%Y %H:%M:%S")


def mentee_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # login_required will handle if you also use it; otherwise redirect yourself
            return redirect("login")  # change to your mentee login url name

        # strict mentee check (recommended)
        if not hasattr(request.user, "mentee") or not request.user.is_mentee:
            messages.error(request, "You are not authorized to access the mentee portal. Please use mentor login page.")
            return redirect("home")
        return view_func(request, *args, **kwargs)
    return _wrapped


def mentor_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login1")  # change to your mentor login url name

        if not hasattr(request.user, "mentor") or not request.user.is_mentor:
            messages.error(request, "You are not authorized to access the mentor portal. Please use mentee login page")
            return redirect("home")
        return view_func(request, *args, **kwargs)
    return _wrapped


def mentor_or_staff_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login1")
        is_mentor = hasattr(request.user, "mentor") and getattr(request.user, "is_mentor", False)
        if not (request.user.is_staff or is_mentor):
            messages.error(request, "You are not authorized to access this page.")
            return redirect("account1")
        return view_func(request, *args, **kwargs)
    return _wrapped


def get_student_risk(swot):
    score_map = {'low': 1, 'moderate': 2, 'high': 3, 'na': 0}

    scores = [
        score_map.get(swot.ppt_confidence, 0),
        score_map.get(swot.core_subjects_confidence, 0),
        score_map.get(swot.communication_confidence, 0),
        score_map.get(swot.softskills_confidence, 0),
        score_map.get(swot.resume_building_confidence, 0),
        score_map.get(swot.project_explanation_confidence, 0),
        score_map.get(swot.tech_platform_confidence, 0),
    ]

    if not any(scores):
        return "Unknown"

    student_score = sum(scores) / (len(scores) * 3) * 100

    if student_score < 40:
        return "High"
    elif student_score < 70:
        return "Moderate"
    return "Low"


def calculate_swot_analytics(swot_queryset):
    score_map = {'low': 1, 'moderate': 2, 'high': 3, 'na': 0}

    analytics = {
        "total_students": swot_queryset.count(),
        "avg_score": 0,
        "risk_counts": {"High": 0, "Moderate": 0, "Low": 0},
        "career_counts": {},
    }

    total_score = 0
    count = 0

    for swot in swot_queryset:
        scores = [
            score_map.get(swot.ppt_confidence, 0),
            score_map.get(swot.core_subjects_confidence, 0),
            score_map.get(swot.communication_confidence, 0),
            score_map.get(swot.softskills_confidence, 0),
            score_map.get(swot.resume_building_confidence, 0),
            score_map.get(swot.project_explanation_confidence, 0),
            score_map.get(swot.tech_platform_confidence, 0),
        ]

        if any(scores):
            student_score = sum(scores) / (len(scores) * 3) * 100
            total_score += student_score
            count += 1

            # Risk classification
            risk = get_student_risk(swot)
            if risk in analytics["risk_counts"]:
                analytics["risk_counts"][risk] += 1

        # Career preference
        career = swot.career_option or "unknown"
        analytics["career_counts"][career] = analytics["career_counts"].get(career, 0) + 1

    if count > 0:
        analytics["avg_score"] = round(total_score / count, 2)

    return analytics


def get_global_performance_data():
    internships = InternshipPBL.objects.all()
    certs = CertificationCourse.objects.all()

    upload_user_ids = (
        list(internships.values_list("user_id", flat=True)) +
        list(certs.values_list("user_id", flat=True))
    )

    upload_profiles = Profile.objects.filter(user_id__in=upload_user_ids)

    # ===============================
    # BEST DIVISION
    # ===============================
    best_div = (
        upload_profiles.values("div", "branch", "year")
        .annotate(student_count=Count("user_id", distinct=True))
        .order_by("-student_count")
        .first()
    )

    if best_div:
        div = best_div["div"]
        branch = best_div["branch"]
        year = best_div["year"]

        div_users = upload_profiles.filter(div=div, branch=branch, year=year)\
                                   .values_list("user_id", flat=True)

        div_internships = internships.filter(user_id__in=div_users).count()
        div_certs = certs.filter(user_id__in=div_users).count()

        best_div["uploads"] = div_internships + div_certs
    else:
        best_div = {"div": "", "branch": "", "student_count": 0, "uploads": 0}

    # ===============================
    # TOP STUDENTS
    # ===============================
    student_map = defaultdict(int)

    for row in internships.values("user_id").annotate(c=Count("id")):
        student_map[row["user_id"]] += row["c"]

    for row in certs.values("user_id").annotate(c=Count("id")):
        student_map[row["user_id"]] += row["c"]

    top_user_ids = sorted(student_map, key=lambda k: student_map[k], reverse=True)[:5]

    profiles_top = Profile.objects.filter(user_id__in=top_user_ids)

    top_students = []

    for p in profiles_top:
        top_students.append({
            "moodle_id": p.moodle_id,
            "student_name": p.student_name,
            "branch": p.branch,
            "year": p.year,
            "div": p.div,
            "total": student_map.get(p.user_id, 0)
        })

    top_students = sorted(top_students, key=lambda x: x["total"], reverse=True)

    return {
        "best_division": best_div,
        "top_students": top_students,
        "max_uploads": top_students[0]["total"] if top_students else 1
    }
