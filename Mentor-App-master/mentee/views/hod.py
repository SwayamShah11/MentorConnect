import os
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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

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
                readiness = "not started"
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

    filename = f"hod_student_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
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
    page_width, page_height = landscape(A4)

    # ---------------- FOOTER FUNCTION ----------------
    def add_footer(c: canvas.Canvas, doc):
        c.setFont("Helvetica", 8)

        # PAGE NUMBER — Bottom Center
        page_num = c.getPageNumber()
        c.drawCentredString(page_width / 2, 20, f"Page {page_num}")

        # GENERATED DATE — Bottom Left
        generated = datetime.now().strftime("%d-%m-%Y %H:%M")
        c.drawString(30, 20, f"Generated: {generated}")

        # ---------------- SIGNATURE LINES ----------------
        line_width = 140

        # Corrected Y positions
        line_y = 55  # line above
        text_y = 40  # text below line (far away from page number)

        # PRINCIPAL (right side)
        principal_x = page_width - line_width - 50
        c.line(principal_x, line_y, principal_x + line_width, line_y)
        c.drawString(principal_x, text_y, "Principal Signature")

        # HOD (center-right)
        hod_x = principal_x - line_width - 100
        c.line(hod_x, line_y, hod_x + line_width, line_y)
        c.drawString(hod_x, text_y, "HOD Signature")

    #-----------------------------------------------------------------------------------------------

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=70,
        bottomMargin=70,
    )

    styles = getSampleStyleSheet()
    story = []

    # ---------------- HEADER WITH LOGO + TITLE ----------------
    header_table_data = []

    logo_path = os.path.join("media", "logo.png")

    if os.path.exists(logo_path):
        img = Image(logo_path, width=80, height=60)
    else:
        img = Paragraph("", styles["Normal"])  # fallback

    title = Paragraph("<b>HOD Student Readiness Report</b>", styles["Title"])

    # 2-column header row
    header_table_data.append([img, title])

    header_table = Table(
        header_table_data,
        colWidths=[100, page_width - 200],  # adjust spacing
    )

    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 12))

    # ---------------- METADATA SECTION ----------------
    hod_name = request.user.get_full_name() or request.user.username
    academic_year = datetime.now().year

    metadata_text = (
        f"<b>Academic Year:</b> {academic_year}-{str(academic_year + 1)[-2:]}<br/>"
        f"<b>Generated By (HOD):</b> Dr.{hod_name}<br/>"
        f"<b>Generated On:</b> {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    )

    metadata_para = Paragraph(metadata_text, styles["Normal"])
    story.append(metadata_para)
    story.append(Spacer(1, 14))

    summary_text = (
        f"Total Mentees: {data['total_mentees']} &nbsp;&nbsp;&nbsp; "
        f"Student completion - &nbsp;"
        f"Ready: {data['ready_count']} &nbsp;&nbsp;&nbsp; "
        f"Partial: {data['partial_count']} &nbsp;&nbsp;&nbsp; "
        f"Not Started: {data['not_started_count']} &nbsp;&nbsp;&nbsp; "
        f"Overall Readiness: {data['placement_ready_percent']}%"
    )
    summary = Paragraph(summary_text, styles["Normal"])
    story.append(summary)
    story.append(Spacer(1, 10))

    # ---------------- TABLE ----------------
    headers = ["Moodle ID", "Name", "Sem", "Contact", "Mentor", "Dept", "Progress", "Completion (%)", "Status"]

    table_data = [headers]

    for m in mentees:
        table_data.append([
            m["moodle_id"],
            m["student_name"],
            m["semester"],
            m["contact"],
            m["mentor_name"],
            m["department"],
            m["progress"],
            str(m["progress_percent"]),
            m["readiness"],
        ])

    # Column widths for clean layout
    col_widths = [70, 120, 40, 80, 120, 80, 70, 70, 80]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    tbl.setStyle(TableStyle([
        # Header Styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#000000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),

        # Body Styling
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # BORDERS
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),

        # Row Padding
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(tbl)

    # ---------------- BUILD PDF ----------------
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)

    buffer.seek(0)
    filename = f"hod_student_report_{datetime.now().strftime('%d-%m-%Y')}.pdf"
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
    return response
