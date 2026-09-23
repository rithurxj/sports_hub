import datetime
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import admin_required, customer_required
from .forms import BookingForm, LoginForm, RegisterForm, TimeSlotForm, TurfForm
from .models import Booking, TimeSlot, Turf, UserProfile


# ==============================================================================
# PUBLIC & EXPLORATION VIEWS
# ==============================================================================

def home(request):
    """Landing page featuring search, sport filters, and popular grounds."""
    featured_turfs = Turf.objects.filter(is_active=True).order_by("?")[:6]
    total_turfs = Turf.objects.filter(is_active=True).count()
    total_slots = TimeSlot.objects.filter(is_active=True).count()
    total_bookings = Booking.objects.filter(status="CONFIRMED").count()

    context = {
        "turfs": featured_turfs,
        "total_turfs": total_turfs,
        "total_slots": total_slots,
        "total_bookings": total_bookings,
    }
    return render(request, "booking/home.html", context)


def turf_list(request):
    """Search and filter turfs by sport type, keyword, and price."""
    turfs = Turf.objects.filter(is_active=True)

    query = request.GET.get("q", "").strip()
    sport = request.GET.get("sport", "").strip()
    sort = request.GET.get("sort", "name")

    if query:
        turfs = turfs.filter(
            Q(name__icontains=query) |
            Q(location__icontains=query) |
            Q(description__icontains=query)
        )

    if sport in ["FOOTBALL", "CRICKET", "MULTI"]:
        turfs = turfs.filter(sport_type=sport)

    if sort == "price_asc":
        turfs = turfs.order_by("price")
    elif sort == "price_desc":
        turfs = turfs.order_by("-price")
    else:
        turfs = turfs.order_by("name")

    context = {
        "turfs": turfs,
        "query": query,
        "selected_sport": sport,
        "selected_sort": sort,
    }
    return render(request, "booking/turf_list.html", context)


def turf_detail(request, pk):
    """Detailed turf view with facilities, pricing, and live availability."""
    turf = get_object_or_404(Turf, pk=pk, is_active=True)
    slots = TimeSlot.objects.filter(is_active=True).order_by("start_time")
    today = timezone.localdate()

    # Pre-fetch today's booked slot IDs for preview
    booked_slot_ids = set(
        Booking.objects.filter(turf=turf, date=today, status="CONFIRMED")
        .values_list("time_slot_id", flat=True)
    )

    context = {
        "turf": turf,
        "slots": slots,
        "today": today,
        "booked_slot_ids": booked_slot_ids,
    }
    return render(request, "booking/turf_detail.html", context)


def turf_availability_api(request, pk):
    """
    JSON API returning slot availability for a given turf and date.
    Called dynamically by JavaScript on booking/detail pages.
    """
    turf = get_object_or_404(Turf, pk=pk, is_active=True)
    date_str = request.GET.get("date")

    if not date_str:
        target_date = timezone.localdate()
    else:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

    now = timezone.localtime()
    today = now.date()

    # Get all active slots
    all_slots = TimeSlot.objects.filter(is_active=True).order_by("start_time")

    # Get booked slots for this turf and date
    booked_slot_ids = set(
        Booking.objects.filter(turf=turf, date=target_date, status="CONFIRMED")
        .values_list("time_slot_id", flat=True)
    )

    slot_data = []
    for slot in all_slots:
        is_past = False
        if target_date < today:
            is_past = True
        elif target_date == today:
            # Check if start time has already passed
            if slot.start_time <= now.time():
                is_past = True

        is_booked = slot.id in booked_slot_ids

        slot_data.append({
            "id": slot.id,
            "label": str(slot),
            "start_time": slot.start_time.strftime("%I:%M %p"),
            "end_time": slot.end_time.strftime("%I:%M %p"),
            "is_booked": is_booked,
            "is_past": is_past,
            "is_available": (not is_booked) and (not is_past),
        })

    return JsonResponse({
        "turf_id": turf.id,
        "turf_name": turf.name,
        "date": target_date.isoformat(),
        "slots": slot_data,
    })


# ==============================================================================
# AUTHENTICATION & ROLE-BASED ROUTING
# ==============================================================================

def register_view(request):
    """Role-based registration for Customers and Turf Managers."""
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            role_display = user.profile.get_role_display()
            messages.success(request, f"Welcome to Sports Hub, {user.first_name or user.username}! You are registered as {role_display}.")
            return redirect_user_by_role(user)
    else:
        form = RegisterForm()

    return render(request, "booking/register.html", {"form": form})


def login_view(request):
    """Role-aware login view with smart redirection."""
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                if next_url:
                    return redirect(next_url)
                return redirect_user_by_role(user)
            else:
                messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = LoginForm()

    return render(request, "booking/login.html", {"form": form, "next": next_url})


def logout_view(request):
    """Logout view with confirmation message."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("home")


def redirect_user_by_role(user):
    """Helper: Route user to their role-specific dashboard."""
    if user.is_superuser or user.is_staff:
        return redirect("admin_dashboard")
    if hasattr(user, "profile") and user.profile.role == "ADMIN":
        return redirect("admin_dashboard")
    return redirect("customer_dashboard")


# ==============================================================================
# CUSTOMER WORKFLOW VIEWS
# ==============================================================================

@login_required
def customer_dashboard(request):
    """Customer personal portal with upcoming reservations and quick booking."""
    user = request.user
    today = timezone.localdate()

    bookings = Booking.objects.filter(user=user).select_related("turf", "time_slot").order_by("-date", "time_slot__start_time")
    upcoming_bookings = bookings.filter(date__gte=today, status="CONFIRMED")[:5]
    total_count = bookings.count()
    confirmed_count = bookings.filter(status="CONFIRMED").count()
    cancelled_count = bookings.filter(status="CANCELLED").count()

    recommended_turfs = Turf.objects.filter(is_active=True)[:3]

    context = {
        "upcoming_bookings": upcoming_bookings,
        "recent_bookings": bookings[:6],
        "total_count": total_count,
        "confirmed_count": confirmed_count,
        "cancelled_count": cancelled_count,
        "recommended_turfs": recommended_turfs,
    }
    return render(request, "booking/customer_dashboard.html", context)


@login_required
def book_turf(request, pk):
    """Interactive booking page with real-time slot selection and conflict prevention."""
    turf = get_object_or_404(Turf, pk=pk, is_active=True)
    today = timezone.localdate()

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking_date = form.cleaned_data["date"]
            slot = form.cleaned_data["time_slot"]

            # Validation 1: Date in past
            if booking_date < today:
                form.add_error("date", "Please select today or a future date.")
            else:
                # Validation 2: Time in past if date is today
                now = timezone.localtime()
                if booking_date == today and slot.start_time <= now.time():
                    form.add_error("time_slot", "This slot has already passed for today. Please pick an upcoming slot.")
                # Validation 3: Already booked
                elif Booking.objects.filter(
                    turf=turf, date=booking_date, time_slot=slot, status="CONFIRMED"
                ).exists():
                    form.add_error(None, f"Slot {slot} is already booked for {booking_date.strftime('%d %b %Y')}. Please choose another.")
                else:
                    try:
                        booking = form.save(commit=False)
                        booking.user = request.user
                        booking.turf = turf
                        booking.total_amount = turf.price
                        booking.status = "CONFIRMED"
                        booking.save()
                    except IntegrityError:
                        form.add_error(None, "This time slot was just booked by another player. Please select another slot.")
                    else:
                        messages.success(request, f"🎉 Booking Confirmed! Ground: {turf.name} on {booking.date.strftime('%d %b %Y')} ({booking.time_slot}).")
                        return redirect("my_bookings")
    else:
        initial_date = request.GET.get("date", today.isoformat())
        form = BookingForm(initial={"date": initial_date})

    context = {
        "turf": turf,
        "form": form,
        "today": today,
    }
    return render(request, "booking/book_turf.html", context)


@login_required
def my_bookings(request):
    """User booking history with filtering and one-click cancellation."""
    status_filter = request.GET.get("status", "ALL")
    bookings = Booking.objects.filter(user=request.user).select_related("turf", "time_slot").order_by("-date", "time_slot__start_time")

    if status_filter in ["CONFIRMED", "CANCELLED", "COMPLETED"]:
        bookings = bookings.filter(status=status_filter)

    today = timezone.localdate()

    context = {
        "bookings": bookings,
        "selected_status": status_filter,
        "today": today,
    }
    return render(request, "booking/my_bookings.html", context)


@login_required
def cancel_booking(request, pk):
    """Customer can cancel their own upcoming booking."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)

    if request.method == "POST":
        if booking.status == "CONFIRMED":
            booking.status = "CANCELLED"
            booking.save(update_fields=["status"])
            messages.success(request, f"Booking for {booking.turf.name} on {booking.date.strftime('%d %b %Y')} has been cancelled.")
        else:
            messages.warning(request, "This booking cannot be cancelled.")

    return redirect("my_bookings")


# ==============================================================================
# TURF ADMIN / MANAGER WORKFLOW VIEWS
# ==============================================================================

@login_required
@admin_required
def admin_dashboard(request):
    """
    Dedicated Turf Manager / Admin frontend dashboard.
    Displays revenue metrics, booking statistics, today's schedule, and quick links.
    """
    today = timezone.localdate()

    # Query metrics
    turfs_count = Turf.objects.count()
    active_turfs_count = Turf.objects.filter(is_active=True).count()
    total_slots_count = TimeSlot.objects.count()

    all_bookings = Booking.objects.select_related("turf", "user", "time_slot")
    total_bookings_count = all_bookings.count()
    confirmed_bookings_count = all_bookings.filter(status="CONFIRMED").count()

    today_bookings = all_bookings.filter(date=today, status="CONFIRMED").order_by("time_slot__start_time")
    recent_bookings = all_bookings.order_by("-booked_at")[:8]

    # Revenue calculation
    total_revenue = all_bookings.filter(status="CONFIRMED").aggregate(sum=Sum("total_amount"))["sum"] or 0
    today_revenue = today_bookings.aggregate(sum=Sum("total_amount"))["sum"] or 0

    context = {
        "turfs_count": turfs_count,
        "active_turfs_count": active_turfs_count,
        "total_slots_count": total_slots_count,
        "total_bookings_count": total_bookings_count,
        "confirmed_bookings_count": confirmed_bookings_count,
        "today_bookings": today_bookings,
        "recent_bookings": recent_bookings,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "today": today,
    }
    return render(request, "booking/admin/admin_dashboard.html", context)


@login_required
@admin_required
def admin_turf_list(request):
    """Admin view: List all turfs with quick management actions."""
    turfs = Turf.objects.annotate(booking_count=Count("bookings")).order_by("-created_at")
    return render(request, "booking/admin/turf_list_admin.html", {"turfs": turfs})


@login_required
@admin_required
def admin_turf_add(request):
    """Admin view: Add a new turf ground."""
    if request.method == "POST":
        form = TurfForm(request.POST)
        if form.is_valid():
            turf = form.save(commit=False)
            turf.owner = request.user
            turf.save()
            messages.success(request, f"Ground '{turf.name}' has been successfully added!")
            return redirect("admin_turf_list")
    else:
        form = TurfForm()

    return render(request, "booking/admin/turf_form.html", {
        "form": form,
        "action_title": "Add New Turf Ground",
        "button_text": "Create Turf",
    })


@login_required
@admin_required
def admin_turf_edit(request, pk):
    """Admin view: Edit an existing turf."""
    turf = get_object_or_404(Turf, pk=pk)

    if request.method == "POST":
        form = TurfForm(request.POST, instance=turf)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ground '{turf.name}' updated successfully.")
            return redirect("admin_turf_list")
    else:
        form = TurfForm(instance=turf)

    return render(request, "booking/admin/turf_form.html", {
        "form": form,
        "action_title": f"Edit {turf.name}",
        "button_text": "Save Changes",
        "turf": turf,
    })


@login_required
@admin_required
def admin_turf_toggle(request, pk):
    """Admin view: Quick toggle turf active/inactive status."""
    turf = get_object_or_404(Turf, pk=pk)
    if request.method == "POST":
        turf.is_active = not turf.is_active
        turf.save(update_fields=["is_active"])
        status = "activated" if turf.is_active else "deactivated"
        messages.info(request, f"Turf '{turf.name}' has been {status}.")
    return redirect("admin_turf_list")


@login_required
@admin_required
def admin_slot_list(request):
    """Admin view: Manage time slots."""
    slots = TimeSlot.objects.order_by("start_time")
    form = TimeSlotForm()

    if request.method == "POST":
        form = TimeSlotForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "New time slot added successfully!")
                return redirect("admin_slot_list")
            except IntegrityError:
                messages.error(request, "A time slot with these start and end times already exists.")

    return render(request, "booking/admin/slot_list_admin.html", {
        "slots": slots,
        "form": form,
    })


@login_required
@admin_required
def admin_slot_delete(request, pk):
    """Admin view: Delete or toggle a time slot."""
    slot = get_object_or_404(TimeSlot, pk=pk)
    if request.method == "POST":
        try:
            slot.delete()
            messages.success(request, f"Time slot {slot} has been deleted.")
        except Exception:
            # If protected by foreign key in existing bookings, toggle active instead
            slot.is_active = not slot.is_active
            slot.save(update_fields=["is_active"])
            messages.warning(request, f"Slot {slot} has past bookings attached, so its active status was toggled instead.")
    return redirect("admin_slot_list")


@login_required
@admin_required
def admin_booking_list(request):
    """Admin view: Manage all customer bookings with status controls."""
    bookings = Booking.objects.select_related("turf", "user", "time_slot").order_by("-date", "time_slot__start_time")

    turf_id = request.GET.get("turf")
    status = request.GET.get("status")
    date_query = request.GET.get("date")

    if turf_id and turf_id.isdigit():
        bookings = bookings.filter(turf_id=int(turf_id))
    if status in ["CONFIRMED", "CANCELLED", "COMPLETED"]:
        bookings = bookings.filter(status=status)
    if date_query:
        try:
            target_date = datetime.datetime.strptime(date_query, "%Y-%m-%d").date()
            bookings = bookings.filter(date=target_date)
        except ValueError:
            pass

    turfs = Turf.objects.all()

    context = {
        "bookings": bookings,
        "turfs": turfs,
        "selected_turf": int(turf_id) if turf_id and turf_id.isdigit() else "",
        "selected_status": status or "",
        "selected_date": date_query or "",
    }
    return render(request, "booking/admin/booking_list_admin.html", context)


@login_required
@admin_required
def admin_booking_status(request, pk, new_status):
    """Admin view: Quick change booking status (CONFIRMED, CANCELLED, COMPLETED)."""
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == "POST" and new_status in ["CONFIRMED", "CANCELLED", "COMPLETED"]:
        booking.status = new_status
        booking.save(update_fields=["status"])
        messages.success(request, f"Booking #{booking.id} status updated to {new_status}.")
    return redirect("admin_booking_list")
