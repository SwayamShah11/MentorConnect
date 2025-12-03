import io
from datetime import datetime
import openpyxl
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from ..models import Mentor, MentorMentee, Profile
from ..utils import get_document_progress
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse


def _build_hod_dashboard_data():
    """
    Central function: build all analytics used by dashboard + exports.
    Returns a dict with the same structure used by the template.
    """
    mentors_qs = Mentor.objects.all()

    mentor_stats = []
    mentees_list = []

    total_mentees = 0
    ready_count = 0
    partial_count = 0
    not_started_count = 0

    for mentor in mentors_qs:
        mappings = MentorMentee.objects.filter(mentor=mentor).select_related("mentee__user")
        mentor_total = mappings.count()
        mentor_ready = 0
        mentor_partial = 0
        mentor_not_started = 0
        mentor_progress_sum = 0

        for mapping in mappings:
            user = mapping.mentee.user
            profile = Profile.objects.filter(user=user).first()

            completed, total, has_pending = get_document_progress(user)
            progress_percent = int((completed / total) * 100) if total else 0

            total_mentees += 1

            if completed == 0:
                mentor_not_started += 1
                not_started_count += 1
            elif completed == total:
                mentor_ready += 1
                ready_count += 1
            else:
                mentor_partial += 1
                partial_count += 1

            mentor_progress_sum += progress_percent

            # determine simple readiness label for UI filters
            if completed == 0:
                readiness = "not_started"
            elif completed == total:
                readiness = "ready"
            else:
                readiness = "partial"

            mentees_list.append({
                "student_name": profile.student_name if profile else user.username,
                "moodle_id": profile.moodle_id if profile else "",
                "semester": profile.semester if profile else "",
                "contact": profile.contact_number if profile else "",
                "mentor_name": mentor.name,
                "department": mentor.department,
                "progress": f"{completed}/{total}",
                "progress_percent": progress_percent,
                "readiness": readiness,
            })

        avg_progress = int(mentor_progress_sum / mentor_total) if mentor_total else 0

        mentor_stats.append({
            "mentor_name": mentor.name,
            "department": mentor.department,
            "total_mentees": mentor_total,
            "ready": mentor_ready,
            "partial": mentor_partial,
            "not_started": mentor_not_started,
            "avg_progress_percent": avg_progress,
        })

    placement_ready_percent = int((ready_count / total_mentees) * 100) if total_mentees else 0

    return {
        "total_mentors": mentors_qs.count(),
        "total_mentees": total_mentees,
        "ready_count": ready_count,
        "partial_count": partial_count,
        "not_started_count": not_started_count,
        "placement_ready_percent": placement_ready_percent,
        "mentor_stats": mentor_stats,
        "mentees_list": mentees_list,
    }


class HODDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "hod/dashboard.html"

    def test_func(self):
        # Admin (HOD) only
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = _build_hod_dashboard_data()
        context.update(data)
        return context


@login_required
@user_passes_test(lambda u: u.is_superuser)
def hod_export_excel(request):
    data = _build_hod_dashboard_data()
    mentees = data["mentees_list"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Placement Readiness"

    headers = [
        "Moodle ID",
        "Student Name",
        "Semester",
        "Contact",
        "Mentor",
        "Department",
        "Progress (completed/total)",
        "Progress (%)",
        "Readiness",
    ]
    ws.append(headers)

    for m in mentees:
        ws.append([
            m["moodle_id"],
            m["student_name"],
            m["semester"],
            m["contact"],
            m["mentor_name"],
            m["department"],
            m["progress"],
            m["progress_percent"],
            m["readiness"],
        ])

    # Adjust column widths a bit
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = max(12, max_length + 2)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"hod_placement_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
def hod_export_pdf(request):
    data = _build_hod_dashboard_data()
    mentees = data["mentees_list"]

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))

    width, height = landscape(A4)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 40, "HOD Placement Readiness Report")

    p.setFont("Helvetica", 10)
    summary = (
        f"Total Mentees: {data['total_mentees']}  |  "
        f"Ready: {data['ready_count']}  |  "
        f"Partial: {data['partial_count']}  |  "
        f"Not Started: {data['not_started_count']}  |  "
        f"Overall Readiness: {data['placement_ready_percent']}%"
    )
    p.drawString(50, height - 60, summary)

    # Table headers
    y = height - 90
    p.setFont("Helvetica-Bold", 9)
    headers = ["Moodle ID", "Name", "Sem", "Contact", "Mentor", "Dept", "Progress", "%", "Status"]
    col_widths = [70, 110, 40, 80, 110, 80, 70, 30, 60]

    x_start = 40
    x = x_start
    for i, h in enumerate(headers):
        p.drawString(x, y, h)
        x += col_widths[i]

    y -= 15
    p.setFont("Helvetica", 8)

    for m in mentees:
        if y < 40:  # new page if not enough space
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 8)

        row = [
            m["moodle_id"],
            m["student_name"],
            m["semester"],
            m["contact"],
            m["mentor_name"],
            m["department"],
            m["progress"],
            str(m["progress_percent"]),
            m["readiness"],
        ]

        x = x_start
        for i, value in enumerate(row):
            p.drawString(x, y, str(value)[:30])  # simple truncation
            x += col_widths[i]

        y -= 12

    p.showPage()
    p.save()

    buffer.seek(0)
    filename = f"hod_placement_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
