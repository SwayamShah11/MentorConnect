from django.shortcuts import render, redirect, get_object_or_404
# from ..models import Status
# from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..forms import MentorRegisterForm, UserUpdateForm, ProfileUpdateForm, UserInfoForm, MoodleIdForm
from django.views.generic import (View, TemplateView,
                                  ListView, DetailView,
                                  CreateView, UpdateView,
                                  DeleteView)

from django.http import HttpResponseRedirect
from ..models import Profile

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

from django.views.generic import TemplateView
from ..models import Profile, Msg, Conversation, Reply, Meeting, Mentor, Mentee, MentorMentee
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse_lazy
from ..forms import ReplyForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin

from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.messages.views import SuccessMessageMixin
from ..render import Render






def home(request):
    """Landing page """

    return render(request, 'home.html')


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
        for mapping in mentee_mappings:
            profile = Profile.objects.filter(user=mapping.mentee.user).first()
            mentees.append({
                "id": mapping.mentee.pk,
                "moodle_id": profile.moodle_id if profile else "",
                "name": profile.student_name if profile else mapping.mentee.user.username,
                "semester": profile.semester if profile else "",
                "contact": profile.contact_number if profile else "",
            })

        return render(request, "mentor/account1.html", {"form": form, "mentees": mentees})

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
            MentorMentee.objects.get_or_create(mentor=mentor, mentee=mentee)
            messages.success(request, f"{profile.student_name} added as your mentee!")

        return redirect("account1")



def register1(request):
    """Registration for mentors"""

    registered = False

    if request.method == 'POST':

        form1 = MentorRegisterForm(request.POST)
        form2 = UserInfoForm(request.POST)

        if form1.is_valid() and form2.is_valid():
            user = form1.save()
            user.is_mentor = True
            user.save()

            info = form2.save(commit=False)
            info.user = user
            info.save()

            registered = True

            messages.success(request, f'Your account has been created! You are now able to log in')

            return redirect('login1')

    else:

        form1 = MentorRegisterForm()
        form2 = UserInfoForm()

    return render(request, 'mentor/register1.html', {'form1': form1, 'form2': form2, })



def profile1(request):
    """Update Mentor Profile"""

    if not request.user.is_mentor:
        return redirect('home')

    if request.method == 'POST':

        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your account has been Updated!')
            return redirect('profile1')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {

        'u_form': u_form,
        'p_form': p_form
    }

    return render(request, 'mentor/profile1.html', context)


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
        PaperPublication, SelfAssessment, StudentInterest, SemesterResult, Profile
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
    student_interest = StudentInterest.objects.filter(student=mentee)
    results = SemesterResult.objects.filter(user=mentee)
    internships = InternshipPBL.objects.filter(user=mentee)
    goals = LongTermGoal.objects.filter(user=mentee)
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
        "results": results,
        "internships": internships,
        "goals": goals,
        "certifications": certifications,
        "assessment": assessment,
        "is_mentor_view": True,   # 👈 flag to hide edit buttons
    }
    return render(request, "mentor/view_mentee_dashboard.html", context)


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


class MessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List sent Messages"""

    model = Msg
    template_name = 'mentor/listmessages1.html'
    context_object_name = 'sentmesso'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


class SentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """details the message sent"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'mentor/sent1.html'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


class SentMessageDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Deletes sent messages"""

    model = Msg
    success_url = reverse_lazy("list1")
    template_name = 'mentor/sentmessage_delete1.html'

    def test_func(self):
        return self.request.user.is_mentor


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


class InboxDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Inbox Detailed view"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'mentor/inboxview1.html'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)



def reply_message(request, pk):
    """Replies, approves, comments on messages"""

    if not request.user.is_mentor:
        return redirect('home')

    reply = get_object_or_404(Msg, pk=pk)

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
        'reply': reply,
        'form': form,
    }

    return render(request, 'mentor/comment.html', context)


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


class Pdf(View):
    """Pdf of Approved Requests"""

    def test_func(self):
        return self.request.user.is_mentor

    def get(self, request):
        messo2 = Msg.objects.filter(is_approved=True).order_by('-date_approved').filter(receipient=self.request.user)

        params = {
            'messo2': messo2,

            'request': request
        }
        return Render.render('mentor/pdf.html', params)



class ProfileDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """view details of a user in the profile"""

    model = Msg
    context_object_name = 'msg'
    template_name = 'mentor/profile_detail1.html'

    def test_func(self):
        return self.request.user.is_mentor


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


class ConversationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """List Conversations"""

    model = Conversation
    template_name = 'mentor/conversation1.html'
    context_object_name = 'conv'

    def test_func(self):
        return self.request.user.is_mentor

    def get_queryset(self):
        return self.model.objects.filter(sender=self.request.user)


class ConversationDeleteView(SuccessMessageMixin, DeleteView):
    """delete view Chat"""

    model = Reply
    template_name = 'mentor/chat-confirm-delete.html'
    success_message = 'Your message has been deleted!'

    # success_url = reverse_lazy('conv1')

    def get_success_url(self):
        conversation = self.object.conversation
        return reverse_lazy('conv-reply', kwargs={'pk': self.object.conversation_id})


class Conversation2DeleteView(DeleteView):
    """delete view Coversation"""

    model = Conversation
    template_name = 'mentor/conversation-confirm-delete.html'

    # success_url = reverse_lazy('conv1')

    def get_success_url(self):
        return reverse_lazy('conv1')


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
