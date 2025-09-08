from django.contrib import admin
from .models import Mentee, Mentor, Profile, Msg, Conversation, Reply, UserInfo, InternshipPBL, Project, SportsCulturalEvent, OtherEvent, LongTermGoal, EducationalDetail
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from .models import User


@admin.register(InternshipPBL)
class InternshipPBLAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "company_name", "academic_year", "semester", "start_date", "end_date", "no_of_days")
    search_fields = ("title", "company_name", "user__username")  # 🔍 search filter
    list_filter = ("user", "academic_year", "semester", "type")  # ✅ dropdown filters
    ordering = ("-start_date",)  # ⬅️ latest internships first
    readonly_fields = ("no_of_days",)  # prevent editing


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "academic_year", "semester", "project_type", "guide_name", "uploaded_at")
    search_fields = ("title", "guide_name", "user__username")
    list_filter = ("user", "academic_year", "semester", "project_type")
    ordering = ("-uploaded_at",)


@admin.register(SportsCulturalEvent)
class SportsCulturalEventAdmin(admin.ModelAdmin):
    list_display = ("user", "name_of_event", "academic_year", "semester", "type", "level", "prize_won", "uploaded_at")
    search_fields = ("name_of_event", "venue", "user__username")
    list_filter = ("user", "academic_year", "semester", "type", "level", "prize_won")
    ordering = ("-uploaded_at",)


@admin.register(OtherEvent)
class OtherEventAdmin(admin.ModelAdmin):
    list_display = ("user", "name_of_event", "academic_year", "semester", "level", "prize_won", "amount_won", "uploaded_at")
    search_fields = ("name_of_event", "details", "user__username")
    list_filter = ("user", "academic_year", "semester", "level", "prize_won")
    ordering = ("-uploaded_at",)


@admin.register(LongTermGoal)
class LongTermGoalAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "reason", "created_at")


@admin.register(EducationalDetail)
class EducationalDetailAdmin(admin.ModelAdmin):
    list_display = ("user", "examination", "percentage", "university_board", "year_of_passing")



class ConversationAdmin(admin.ModelAdmin):

    search_fields = ("conversation",)

    list_display = ("sender", "receipient", "sent_at", "conversation", "reply", "replied_at",)

    list_display_links = ("conversation",)

    list_per_page = 10




class MsgAdmin(admin.ModelAdmin):


    search_fields = ("msg_content",)

    list_filter = ("is_approved",)

    list_display = ("sender", "receipient", "sent_at", "msg_content", "comment", "comment_at", "is_approved", "date_approved")

    list_editable = ("is_approved",)

    list_display_links = ("msg_content",)

    list_per_page = 10


class MentorAdmin(admin.ModelAdmin):
    search_fields = ("interests",)





class UserAdmin(admin.ModelAdmin):

    list_display = ("username", "email", "is_mentor", "is_mentee",)

    list_display_links = ("username", "email",  "is_mentor", "is_mentee",)

    list_filter = ("username", "is_mentor", "is_mentee",)

    search_fields = ("username",)

    list_per_page = 10





admin.site.register(Reply)

admin.site.register(UserInfo)

admin.site.register(Mentee)

admin.site.register(Mentor, MentorAdmin)

#admin.site.register(User, UserAdmin)

admin.site.register(Profile)

admin.site.register(Msg, MsgAdmin)

admin.site.register(Conversation)





class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields =  '__all__'
        exclude =('password', )

class CustomUserAdmin(UserAdmin):

    form = CustomUserCreationForm

admin.site.register(User, CustomUserAdmin)


admin.site.unregister(Group)