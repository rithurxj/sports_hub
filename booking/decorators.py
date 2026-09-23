from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and has an ADMIN role,
    is_staff, or is_superuser.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in with an Admin/Manager account to access this page.")
            return redirect(f"/login/?next={request.path}")
        
        is_admin = (
            request.user.is_superuser
            or request.user.is_staff
            or (hasattr(request.user, "profile") and request.user.profile.role == "ADMIN")
            or request.user.groups.filter(name="Admin").exists()
        )
        if not is_admin:
            messages.error(request, "Access restricted: You do not have Turf Manager / Admin permissions.")
            return redirect("customer_dashboard")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def customer_required(view_func):
    """
    Decorator for views that checks that the user is logged in.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to continue.")
            return redirect(f"/login/?next={request.path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
