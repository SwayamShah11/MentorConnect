from django.contrib import admin
from .models import (Mentor, Profile, Msg, Conversation, Reply, InternshipPBL, Project, SportsCulturalEvent, OtherEvent,
                     CertificationCourse, LongTermGoal, EducationalDetail, Meeting, MentorMentee, SelfAssessment, Query,
                     StudentInterest, SemesterResult, MentorMenteeInteraction, ActivityLog, WeeklyAgenda, SWOTAnalysis,
                     PaperPublication)
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.utils import timezone
from .certificate_verification import apply_course_certificate_verification, apply_internship_certificate_verification
from django.db import connection

# Generic reusable admin action
def reset_sequence_for_model(model):
    table_name = model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

# Shared admin action
def delete_all_and_reset_id(modeladmin, request, queryset):
    model = modeladmin.model
    model.objects.all().delete()
    reset_sequence_for_model(model)
    modeladmin.message_user(request, f"All {model.__name__} entries deleted and ID reset to 1.")


@admin.register(InternshipPBL)
class InternshipPBLAdmin(admin.ModelAdmin):
    list_display = (
        "user", "title", "company_name", "verification_status", "domain",
        "qr_detected", "qr_url_accessible", "academic_year", "semester", "start_date", "end_date", "no_of_days",
        "uploaded_at"
    )
    search_fields = ("title", "company_name", "user__username")
    list_filter = ("verification_status", "qr_detected", "qr_url_accessible", "domain", "academic_year", "semester", "type")
    ordering = ("-start_date",)
    readonly_fields = ("no_of_days", "qr_payload", "verification_notes", "verification_checked_at")
    actions = ("mark_verified", "mark_verify_physically", "rerun_qr_verification", delete_all_and_reset_id)

    @admin.action(description="Mark selected as manually verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(verification_status="verified", verification_checked_at=timezone.now())
        self.message_user(request, f"{updated} internship certificate(s) marked verified.")

    @admin.action(description="Mark selected for physical verification")
    def mark_verify_physically(self, request, queryset):
        updated = queryset.update(verification_status="verify_physically", verification_checked_at=timezone.now())
        self.message_user(request, f"{updated} internship certificate(s) marked as verify physically.")

    @admin.action(description="Re-run automatic QR verification")
    def rerun_qr_verification(self, request, queryset):
        count = 0
        for item in queryset:
            if item.certificate:
                apply_internship_certificate_verification(item, save=True)
                count += 1
        self.message_user(request, f"Automatic verification re-run for {count} internship certificate(s).")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "academic_year", "semester", "project_type", "guide_name", "uploaded_at")
    search_fields = ("title", "guide_name", "user__username", "project_type")
    list_filter = ("user", "academic_year", "semester", "project_type")
    ordering = ("-uploaded_at",)
    actions = [delete_all_and_reset_id]


@admin.register(SportsCulturalEvent)
class SportsCulturalEventAdmin(admin.ModelAdmin):
    list_display = ("user", "name_of_event", "academic_year", "semester", "type", "level", "prize_won", "uploaded_at")
    search_fields = ("name_of_event", "venue", "user__username")
    list_filter = ("user", "academic_year", "semester", "type", "level", "prize_won")
    ordering = ("-uploaded_at",)
    actions = [delete_all_and_reset_id]


@admin.register(OtherEvent)
class OtherEventAdmin(admin.ModelAdmin):
    list_display = ("user", "name_of_event", "academic_year", "semester", "level", "prize_won", "amount_won", "uploaded_at")
    search_fields = ("name_of_event", "details", "user__username")
    list_filter = ("user", "academic_year", "semester", "level", "prize_won")
    ordering = ("-uploaded_at",)
    actions = [delete_all_and_reset_id]


@admin.register(CertificationCourse)
class CertificationCourseAdmin(admin.ModelAdmin):
    list_display = (
        "user", "title", "certifying_authority", "domain", "verification_status", "semester", "academic_year",
        "qr_detected", "qr_url_accessible", "verification_checked_at", "uploaded_at"
    )
    search_fields = ("title", "certifying_authority", "user__username")
    list_filter = ("verification_status", "qr_detected", "qr_url_accessible", "domain", "academic_year", "semester")
    readonly_fields = ("qr_payload", "verification_notes", "verification_checked_at")
    ordering = ("-uploaded_at",)
    actions = ("mark_verified", "mark_unverified", "rerun_qr_verification", delete_all_and_reset_id)

    @admin.action(description="Mark selected as manually verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(verification_status="manual_verified", verification_checked_at=timezone.now())
        self.message_user(request, f"{updated} certificate(s) marked verified.")

    @admin.action(description="Mark selected as unverified")
    def mark_unverified(self, request, queryset):
        updated = queryset.update(verification_status="unverified", verification_checked_at=timezone.now())
        self.message_user(request, f"{updated} certificate(s) marked unverified.")

    @admin.action(description="Re-run automatic QR verification")
    def rerun_qr_verification(self, request, queryset):
        count = 0
        for item in queryset:
            if item.certificate:
                apply_course_certificate_verification(item, save=True)
                count += 1
        self.message_user(request, f"Automatic verification re-run for {count} certificate(s).")


@admin.register(LongTermGoal)
class LongTermGoalAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "reason", "created_at")
    actions = [delete_all_and_reset_id]


@admin.register(EducationalDetail)
class EducationalDetailAdmin(admin.ModelAdmin):
    list_display = ("user", "examination", "percentage", "university_board", "year_of_passing")
    list_filter = ("examination", "university_board", "year_of_passing")
    search_fields = ['user__username']
    actions = [delete_all_and_reset_id]


@admin.register(StudentInterest)
class StudentInterestAdmin(admin.ModelAdmin):
    list_display = ("student", "get_interests", "created_at")
    actions = [delete_all_and_reset_id]

    def get_interests(self, obj):
        return ", ".join(obj.interests)
    get_interests.short_description = "Interests"


@admin.register(SemesterResult)
class SemesterResultAdmin(admin.ModelAdmin):
    list_display = ("user", "academic_year", "semester", "pointer", "no_of_kt", "created_at")
    list_filter = ("academic_year", "semester", "pointer", "no_of_kt")
    search_fields = ['user__username']
    actions = [delete_all_and_reset_id]


@admin.register(MentorMentee)
class MentorMenteeMappingAdmin(admin.ModelAdmin):
    list_display = ("mentor", "mentee", "created_at")
    search_fields = ('mentor__user__username', 'mentee__user__username')
    list_filter = ['mentor__name']
    actions = [delete_all_and_reset_id]


@admin.register(PaperPublication)
class PaperPublicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'academic_year', 'semester', 'year', 'type', 'conf_name', 'level', 'amount_reimbursed', 'authors')
    search_fields = ('user__username', 'title', 'academic_year', 'semester', 'year', 'type', 'authors')
    list_filter = ['academic_year', 'semester', 'year', 'type', 'authors']
    actions = [delete_all_and_reset_id]

class ConversationAdmin(admin.ModelAdmin):
    search_fields = ("conversation",)
    list_display = ("sender", "receipient", "sent_at", "conversation", "reply", "replied_at",)
    list_display_links = ("conversation",)
    list_per_page = 10
    actions = [delete_all_and_reset_id]


class MsgAdmin(admin.ModelAdmin):
    search_fields = ("msg_content",)
    list_filter = ("is_approved",)
    list_display = ("sender", "receipient", "sent_at", "msg_content", "comment", "comment_at", "is_approved", "chat_started", "date_approved")
    list_editable = ("is_approved",)
    list_display_links = ("msg_content",)
    list_per_page = 10
    actions = [delete_all_and_reset_id]


class MentorAdmin(admin.ModelAdmin):
    search_fields = ("interests",)


class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_mentor", "is_mentee",)
    list_display_links = ("username", "email",  "is_mentor", "is_mentee",)
    list_filter = ("username", "is_mentor", "is_mentee",)
    search_fields = ("username",)
    list_per_page = 10


admin.site.register(Reply)

# admin.site.register(Mentee)

admin.site.register(Mentor, MentorAdmin)

admin.site.register(Profile)

admin.site.register(Msg, MsgAdmin)

admin.site.register(Conversation)


User = get_user_model()
class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields =  '__all__'
        exclude =('password', )

class CustomUserAdmin(UserAdmin):
    form = CustomUserCreationForm

admin.site.register(User, CustomUserAdmin)


# from .models import MentorAdmin
# @admin.register(MentorAdmin)
# class MentorAdmin(admin.ModelAdmin):
#     list_display = ['user', 'specialization', 'availability_start', 'availability_end']
#     search_fields = ['user_username', 'user_first_name']
#     list_filter = ['specialization']


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = [
        'mentor_name', 'mentee_name',
        'appointment_date', 'time_slot',
        'duration_minutes', 'status', 'created_at'
    ]

    search_fields = [
        'mentor__user__username', 'mentee__user__username',
        'mentor__user__first_name', 'mentee__user__first_name',
        'mentor__user__last_name', 'mentee__user__last_name',
    ]

    list_filter = ['appointment_date', 'status', 'mentor__user__username', 'mentee__user__username']
    actions = [delete_all_and_reset_id]
    ordering = ['-appointment_date', '-time_slot']

    def mentor_name(self, obj):
        return obj.mentor.user.get_full_name() or obj.mentor.user.username
    mentor_name.short_description = 'Mentor'

    def mentee_name(self, obj):
        return obj.mentee.user.get_full_name() or obj.mentee.user.username
    mentee_name.short_description = 'Mentee'


@admin.register(MentorMenteeInteraction)
class MentorMenteeInteractionAdmin(admin.ModelAdmin):
    list_display = [
        'mentor',
        'mentee_list',
        'date',
        'semester',
        'class_year',
        'agenda',
        'created_at',
    ]

    list_filter = [
        'semester',
        'class_year',
    ]

    search_fields = [
        'mentor__username',
        'mentees__username',
    ]
    actions = [delete_all_and_reset_id]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("mentees")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "module", "timestamp", "ip_address")
    list_filter = ("action", "module", "timestamp")
    search_fields = ("user__username", "action", "details")
    actions = [delete_all_and_reset_id]


@admin.register(WeeklyAgenda)
class WeeklyAgendaAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'academic_year', 'week', 'year', 'sem', 'created_by', 'created_at', 'updated_at')
    list_filter = ('academic_year', 'week', 'year', 'sem', 'created_by')
    search_fields = ('academic_year', 'week', 'year', 'sem')
    actions = [delete_all_and_reset_id]


@admin.register(SWOTAnalysis)
class SWOTAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'mentor_name', 'moodle_id', 'year', 'division', 'batch', 'career_option', 'other_career')
    list_filter = ('name', 'mentor_name', 'year', 'division', 'batch', 'career_option')
    search_fields = ('name', 'mentor_name', 'year', 'division', 'batch', 'career_option')
    actions = [delete_all_and_reset_id]


@admin.register(SelfAssessment)
class SelfAssessmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'year', 'goals', 'reason', 'created_at')
    list_filter = ['user__username', 'year']
    search_fields = ['user__username', 'year']
    actions = [delete_all_and_reset_id]


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'mentee', 'text', 'severity', 'status', 'created_at')
    list_filter = ['mentor__name', 'severity', 'status', 'mentee__user']
    search_fields = ['mentor__name', 'mentee__user__username', 'severity']
    actions = [delete_all_and_reset_id]
