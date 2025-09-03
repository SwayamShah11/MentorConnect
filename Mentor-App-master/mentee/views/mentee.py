from django.shortcuts import render, redirect, get_object_or_404
# from ..models import Status
# from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..forms import MenteeRegisterForm, UserUpdateForm, ProfileUpdateForm, UserInfoForm, ProjectForm
from django.views.generic import TemplateView
from ..models import Profile, Msg, Conversation, Reply, Project
from django.contrib.auth import get_user_model

User = get_user_model()
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

from django.views.generic import (View, TemplateView,
                                  ListView, DetailView,
                                  CreateView, UpdateView,
                                  DeleteView)

from django.urls import reverse_lazy
from .. import models
from django.contrib.messages.views import SuccessMessageMixin

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin

from ..forms import SendForm
from django.db.models import Count, Q
from ..render import Render
from ..models import InternshipPBL
from ..forms import InternshipPBLForm
from django.http import HttpResponse, Http404
from django.conf import settings
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image
import pypandoc

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
        return self.request.user.is_mentee

    """
    List all of the Users that we want.
    """

    def get(self, request):
        users = User.objects.all().filter(is_mentor=True)

        context = {
            'users': users,

        }

        return render(request, "menti/account.html", context)


def register(request):
    """Controls the register module"""

    registered = False

    if request.method == 'POST':

        form1 = MenteeRegisterForm(request.POST)
        form2 = UserInfoForm(request.POST)

        if form1.is_valid() and form2.is_valid():
            user = form1.save()
            user.is_mentee = True
            user.save()

            info = form2.save(commit=False)
            info.user = user
            info.save()

            registered = True

            messages.success(request, f'Your account has been created! You are now able to log in')

            return redirect('login')

    else:

        form1 = MenteeRegisterForm()
        form2 = UserInfoForm()

    return render(request, 'menti/register.html', {'form1': form1, 'form2': form2, })


# class MenteeSignUpView(CreateView):
# model = User
# form_class = MenteeRegisterForm
# template_name = 'menti/register.html'

# def get_context_data(self, **kwargs):
# kwargs['user_type'] = 'mentee'
# return super().get_context_data(**kwargs)

# def form_valid(self, form):
# user = form.save()
# login(self.request, user)
# return redirect('login')


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


@login_required
def mentee_home(request):
    profile = Profile.objects.get(user=request.user)
    return render(request, "menti/mentee_home.html", {"profile": profile})


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

    return render(request, 'menti/profile.html', {'form': form})


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


@login_required
def internship_pbl_list(request):
    internships = InternshipPBL.objects.filter(user=request.user)  # show only user’s data

    if request.method == "POST":
        form = InternshipPBLForm(request.POST, request.FILES)
        if form.is_valid():
            internship = form.save(commit=False)
            internship.user = request.user   # 🔥 link logged-in user
            # Auto-calc safeguard if JS fails
            if internship.start_date and internship.end_date:
                internship.no_of_days = (internship.end_date - internship.start_date).days + 1
            internship.save()
            return redirect("internship-pbl-list")
        else:
            print(form.errors)  # debug in console
    else:
        form = InternshipPBLForm()

    return render(request, "menti/internship_pbl_list.html", {
        "internships": internships,
        "form": form
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
        },
    )


# # Update project
# @login_required
# def add_project(request):
#     if request.method == "POST":
#         form = ProjectForm(request.POST, request.FILES)
#         if form.is_valid():
#             form.save()
#             return redirect("projects-list")
#     else:
#         form = ProjectForm()
#     return render(request, "menti/projects_list.html", {"form": form, "editing": False})
#
#
# @login_required
# def update_project(request, project_id):
#     project = get_object_or_404(Project, id=project_id)
#     if request.method == "POST":
#         form = ProjectForm(request.POST, request.FILES, instance=project)
#         if form.is_valid():
#             form.save()
#             return redirect("projects_list")
#     else:
#         form = ProjectForm(instance=project)
#     return render(
#         request,
#         "mentee/projects.html",
#         {"form": form, "editing": True, "project_id": project.id},
#     )
#
# # Delete project
# @login_required
# def delete_project(request, pk):
#     project = get_object_or_404(Project, pk=pk)
#     project.delete()
#     return redirect('projects-list')


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


class InboxDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Inbox Detailed view"""

    model = Msg
    context_object_name = 'messo'
    template_name = 'menti/inboxview.html'

    def test_func(self):
        return self.request.user.is_mentee

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


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

        return context

    def get_queryset(self):
        return self.model.objects.filter(receipient=self.request.user)


def messege_view(request):
    """Views the Message Module"""

    if not request.user.is_mentee:
        return redirect('home')

    return render(request, 'menti/messages-module.html', )


class SentMessageDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Deletes Sent Messages"""

    model = models.Msg
    success_url = reverse_lazy("list")
    template_name = 'menti/sentmessage_delete.html'

    def test_func(self):
        return self.request.user.is_mentee


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
