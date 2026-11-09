from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.audit import services as audit

from . import services
from .forms import EmailAuthenticationForm, ProfileForm


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.GET.get("logout") or request.GET.get("logged_out"):
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        if user:
            services.activate_pending_memberships(user, request=self.request)
        return response


class LogoutView(auth_views.LogoutView):
    """POST-only logout view with AJAX/Fetch API support, audit logging, and full cookie deletion."""

    http_method_names = ["post", "options"]

    def post(self, request, *args, **kwargs):
        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
        )
        if is_ajax:
            from django.contrib.auth import logout as auth_logout
            from django.http import JsonResponse
            auth_logout(request)
            response = JsonResponse({"status": "logged_out", "redirect_url": "/accounts/login/"})
        else:
            response = super().post(request, *args, **kwargs)

        response.delete_cookie(
            settings.SESSION_COOKIE_NAME,
            domain=settings.SESSION_COOKIE_DOMAIN,
            path=settings.SESSION_COOKIE_PATH or "/",
        )
        response.delete_cookie(
            settings.CSRF_COOKIE_NAME,
            domain=settings.CSRF_COOKIE_DOMAIN,
            path=settings.CSRF_COOKIE_PATH or "/",
        )
        for cookie_name in request.COOKIES:
            response.delete_cookie(
                cookie_name,
                domain=settings.SESSION_COOKIE_DOMAIN,
                path=settings.SESSION_COOKIE_PATH or "/",
            )
        response["Clear-Site-Data"] = '"cookies"'
        return response


class ActivateView(auth_views.PasswordResetConfirmView):
    """Invitation link: the invited user chooses a password; pending memberships become ACTIVE."""

    template_name = "accounts/activate.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        response = super().form_valid(form)
        services.activate_pending_memberships(form.user, request=self.request)
        audit.record("auth.password_set", actor=form.user, target=form.user, target_repr=form.user.email,
                     request=self.request)
        messages.success(self.request, "Your password is set. Sign in to continue.")
        return response


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit.record("auth.password_reset", actor=form.user, target=form.user, target_repr=form.user.email,
                     request=self.request)
        messages.success(self.request, "Password updated. Sign in with your new password.")
        return response


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit.record("auth.password_changed", actor=self.request.user, target=self.request.user,
                     target_repr=self.request.user.email, request=self.request)
        messages.success(self.request, "Password changed.")
        return response


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        before = {"full_name": request.user.full_name, "phone": request.user.phone}
        form.save()
        audit.record("user.profile_updated", actor=request.user, target=request.user,
                     target_repr=request.user.email, before=before,
                     after={"full_name": form.instance.full_name, "phone": form.instance.phone},
                     request=request)
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
