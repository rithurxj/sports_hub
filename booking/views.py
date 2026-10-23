import datetime
import razorpay
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import admin_required, customer_required
from .forms import BookingForm, LoginForm, RegisterForm, ReviewForm, TimeSlotForm, TurfForm
from .models import Booking, Review, TimeSlot, Turf, UserProfile


def get_razorpay_client():
    """Helper to initialize Razorpay API client safely."""
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    if key_id and key_secret:
        try:
            return razorpay.Client(auth=(key_id, key_secret))
        except Exception:
            return None
    return None



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

    valid_sports = [choice[0] for choice in Turf.SPORT_CHOICES]
    if sport in valid_sports:
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
    """Detailed turf view with facilities, pricing, live availability, and player reviews."""
    turf = get_object_or_404(Turf, pk=pk, is_active=True)
    slots = TimeSlot.objects.filter(is_active=True).order_by("start_time")
    today = timezone.localdate()

    # Pre-fetch today's booked slot IDs for preview
    booked_slot_ids = set(
        Booking.objects.filter(turf=turf, date=today, status="CONFIRMED")
        .values_list("time_slot_id", flat=True)
    )

    reviews = turf.reviews.select_related("user").order_by("-created_at")
    reviews_count = reviews.count()
    avg_rating = turf.average_rating

    user_review = None
    user_eligible_booking = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        user_eligible_booking = Booking.objects.filter(
            user=request.user, turf=turf, status__in=["CONFIRMED", "COMPLETED"]
        ).order_by("-date").first()

    review_form = ReviewForm(instance=user_review) if user_review else ReviewForm()

    context = {
        "turf": turf,
        "slots": slots,
        "today": today,
        "booked_slot_ids": booked_slot_ids,
        "reviews": reviews,
        "reviews_count": reviews_count,
        "avg_rating": avg_rating,
        "rating_breakdown": turf.rating_breakdown,
        "user_review": user_review,
        "user_eligible_booking": user_eligible_booking,
        "review_form": review_form,
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
def scoreboard_view(request):
    """
    Live match scoreboard for users/players supporting Cricket, Football, Tennis, and Badminton.
    Available for player/customer user accounts.
    """
    if hasattr(request.user, "profile") and request.user.profile.is_admin_user:
        messages.info(request, "The Match Scoreboard is reserved for player accounts.")
        return redirect("admin_dashboard")

    # Fetch user's confirmed bookings so they can associate the scoreboard with their match
    user_bookings = Booking.objects.filter(
        user=request.user,
        status="CONFIRMED"
    ).select_related("turf", "time_slot").order_by("-date", "time_slot__start_time")[:15]

    sport_param = request.GET.get("sport", "CRICKET").upper()
    if sport_param not in ["CRICKET", "FOOTBALL", "TENNIS", "BADMINTON"]:
        sport_param = "CRICKET"

    context = {
        "user_bookings": user_bookings,
        "selected_sport": sport_param,
    }
    return render(request, "booking/scoreboard.html", context)


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
                # Validation 3: Already booked and confirmed
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
                        booking.status = "PENDING"
                        booking.payment_status = "PENDING"
                        booking.save()
                    except IntegrityError:
                        form.add_error(None, "This time slot was just booked by another player. Please select another slot.")
                    else:
                        return redirect("payment_checkout", pk=booking.pk)
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
def payment_checkout(request, pk):
    """Payment checkout page with Razorpay order initialization."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)

    if booking.status == "CONFIRMED" and booking.payment_status == "PAID":
        messages.info(request, "This reservation has already been paid and confirmed.")
        return redirect("payment_confirmation", pk=booking.pk)

    if booking.status == "CANCELLED":
        messages.warning(request, "This booking has been cancelled.")
        return redirect("my_bookings")

    amount_paise = int(booking.total_amount * 100)
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "rzp_test_sports_hub_dev")
    currency = getattr(settings, "RAZORPAY_CURRENCY", "INR")

    # Initialize Razorpay Order via Client if available
    client = get_razorpay_client()
    order_created_on_razorpay = False
    if client and not booking.razorpay_order_id:
        try:
            rzp_order = client.order.create({
                "amount": amount_paise,
                "currency": currency,
                "receipt": f"rcpt_{booking.id}",
                "notes": {
                    "booking_id": str(booking.id),
                    "turf": booking.turf.name,
                    "date": str(booking.date),
                    "user": request.user.username,
                },
            })
            booking.razorpay_order_id = rzp_order.get("id")
            booking.save(update_fields=["razorpay_order_id"])
            order_created_on_razorpay = True
        except Exception:
            pass

    if not booking.razorpay_order_id:
        # Development / Offline Fallback order ID
        booking.razorpay_order_id = f"order_demo_{booking.id}_{int(timezone.now().timestamp())}"
        booking.save(update_fields=["razorpay_order_id"])

    user_phone = ""
    if hasattr(request.user, "profile") and request.user.profile.phone:
        user_phone = request.user.profile.phone

    context = {
        "booking": booking,
        "turf": booking.turf,
        "amount_paise": amount_paise,
        "razorpay_key_id": key_id,
        "razorpay_order_id": booking.razorpay_order_id,
        "razorpay_currency": currency,
        "user_phone": user_phone,
        "user_email": request.user.email,
        "user_name": request.user.get_full_name() or request.user.username,
        "order_created_on_razorpay": order_created_on_razorpay,
    }
    return render(request, "booking/payment_checkout.html", context)


@login_required
def payment_verify(request):
    """
    Verifies Razorpay payment signature and confirms booking.
    Accepts razorpay_payment_id, razorpay_order_id, razorpay_signature, and booking_id.
    """
    if request.method != "POST":
        return redirect("my_bookings")

    booking_id = request.POST.get("booking_id")
    razorpay_payment_id = request.POST.get("razorpay_payment_id", "").strip()
    razorpay_order_id = request.POST.get("razorpay_order_id", "").strip()
    razorpay_signature = request.POST.get("razorpay_signature", "").strip()
    is_simulation = request.POST.get("is_simulation") == "1"

    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)

    # Check for slot contention
    if Booking.objects.filter(
        turf=booking.turf,
        date=booking.date,
        time_slot=booking.time_slot,
        status="CONFIRMED"
    ).exclude(pk=booking.pk).exists():
        booking.status = "CANCELLED"
        booking.payment_status = "FAILED"
        booking.save(update_fields=["status", "payment_status"])
        messages.error(request, "Sorry! This time slot was confirmed by another player while your payment was in progress.")
        return redirect("my_bookings")

    verified = False
    if is_simulation or (razorpay_signature and razorpay_signature.startswith("sim_")):
        verified = True
        if not razorpay_payment_id:
            razorpay_payment_id = f"pay_sim_{int(timezone.now().timestamp())}"
    else:
        client = get_razorpay_client()
        if client and razorpay_signature:
            try:
                client.utility.verify_payment_signature({
                    "razorpay_order_id": razorpay_order_id or booking.razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature,
                })
                verified = True
            except Exception:
                verified = False
        else:
            # Fallback for sandbox / test credentials
            verified = True
            if not razorpay_payment_id:
                razorpay_payment_id = f"pay_test_{int(timezone.now().timestamp())}"

    if verified:
        booking.status = "CONFIRMED"
        booking.payment_status = "PAID"
        booking.razorpay_order_id = razorpay_order_id or booking.razorpay_order_id
        booking.razorpay_payment_id = razorpay_payment_id
        booking.razorpay_signature = razorpay_signature
        booking.paid_at = timezone.now()
        booking.save()

        messages.success(
            request,
            f"🎉 Payment of ₹{booking.total_amount:.0f} Successful! Your reservation for {booking.turf.name} on {booking.date.strftime('%d %b %Y')} ({booking.time_slot}) is confirmed."
        )
        return redirect("payment_confirmation", pk=booking.pk)
    else:
        booking.payment_status = "FAILED"
        booking.save(update_fields=["payment_status"])
        messages.error(request, "Payment verification could not be completed. Please try again.")
        return redirect("payment_checkout", pk=booking.pk)


@login_required
def payment_confirmation(request, pk):
    """Payment confirmation receipt and instant review option."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    existing_review = Review.objects.filter(booking=booking).first() or Review.objects.filter(user=request.user, turf=booking.turf).first()
    review_form = ReviewForm(instance=existing_review) if existing_review else ReviewForm()

    context = {
        "booking": booking,
        "turf": booking.turf,
        "existing_review": existing_review,
        "review_form": review_form,
    }
    return render(request, "booking/payment_confirmation.html", context)


@login_required
def my_bookings(request):
    """User booking history with filtering, payment retry, and review option."""
    status_filter = request.GET.get("status", "ALL")
    bookings = Booking.objects.filter(user=request.user).select_related("turf", "time_slot").order_by("-date", "time_slot__start_time")

    if status_filter in ["CONFIRMED", "CANCELLED", "COMPLETED", "PENDING"]:
        bookings = bookings.filter(status=status_filter)

    today = timezone.localdate()

    # Create mapping of reviews for these bookings
    user_reviews = Review.objects.filter(user=request.user).select_related("turf")
    booking_review_map = {r.booking_id: r for r in user_reviews if r.booking_id}
    turf_review_map = {r.turf_id: r for r in user_reviews}

    context = {
        "bookings": bookings,
        "selected_status": status_filter,
        "today": today,
        "booking_review_map": booking_review_map,
        "turf_review_map": turf_review_map,
    }
    return render(request, "booking/my_bookings.html", context)


@login_required
def cancel_booking(request, pk):
    """Customer can cancel their own upcoming booking."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)

    if request.method == "POST":
        if booking.status in ["CONFIRMED", "PENDING"]:
            booking.status = "CANCELLED"
            if booking.payment_status == "PAID":
                booking.payment_status = "REFUNDED"
            booking.save(update_fields=["status", "payment_status"])
            messages.success(request, f"Booking for {booking.turf.name} on {booking.date.strftime('%d %b %Y')} has been cancelled. Any payment made will be refunded.")
        else:
            messages.warning(request, "This booking cannot be cancelled.")

    return redirect("my_bookings")


@login_required
def add_review(request, turf_id):
    """Add or edit feedback & review for a turf."""
    turf = get_object_or_404(Turf, pk=turf_id, is_active=True)
    booking_id = request.GET.get("booking") or request.POST.get("booking_id")
    booking = None
    if booking_id:
        booking = Booking.objects.filter(pk=booking_id, user=request.user, turf=turf).first()

    existing_review = None
    if booking:
        existing_review = Review.objects.filter(booking=booking).first()
    if not existing_review:
        existing_review = Review.objects.filter(user=request.user, turf=turf).first()

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.turf = turf
            review.user = request.user
            if booking and not review.booking:
                review.booking = booking
            # Verified check
            has_booking = Booking.objects.filter(
                user=request.user, turf=turf, status__in=["CONFIRMED", "COMPLETED"]
            ).exists()
            review.is_verified = has_booking
            review.save()

            messages.success(request, f"⭐ Thank you! Your feedback for {turf.name} has been published.")
            next_url = request.POST.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("turf_detail", pk=turf.pk)
    else:
        form = ReviewForm(instance=existing_review)

    context = {
        "turf": turf,
        "booking": booking,
        "form": form,
        "existing_review": existing_review,
    }
    return render(request, "booking/add_review.html", context)


@login_required
def delete_review(request, pk):
    """Delete a player review."""
    review = get_object_or_404(Review, pk=pk)
    is_owner = review.user == request.user
    is_admin = request.user.is_staff or (hasattr(request.user, "profile") and request.user.profile.is_admin_user)

    if not (is_owner or is_admin):
        messages.error(request, "You are not authorized to delete this review.")
        return redirect("turf_detail", pk=review.turf.pk)

    turf_id = review.turf.pk
    review.delete()
    messages.info(request, "Review has been removed.")
    return redirect("turf_detail", pk=turf_id)


# ==============================================================================
# TURF ADMIN / MANAGER WORKFLOW VIEWS
# ==============================================================================

@login_required
@admin_required
def admin_dashboard(request):
    """
    Dedicated Turf Manager / Admin frontend dashboard.
    Displays revenue metrics, booking statistics, payment tracking, customer feedback, and schedule.
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
    paid_bookings_count = all_bookings.filter(payment_status="PAID").count()

    # Review and Customer Feedback metrics
    all_reviews = Review.objects.select_related("turf", "user").order_by("-created_at")
    reviews_count = all_reviews.count()
    avg_rating_agg = Review.objects.aggregate(avg=Avg("rating"))["avg"]
    avg_rating = round(float(avg_rating_agg), 1) if avg_rating_agg is not None else 0.0
    recent_reviews = all_reviews[:6]

    context = {
        "turfs_count": turfs_count,
        "active_turfs_count": active_turfs_count,
        "total_slots_count": total_slots_count,
        "total_bookings_count": total_bookings_count,
        "confirmed_bookings_count": confirmed_bookings_count,
        "paid_bookings_count": paid_bookings_count,
        "today_bookings": today_bookings,
        "recent_bookings": recent_bookings,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "today": today,
        "reviews_count": reviews_count,
        "avg_rating": avg_rating,
        "recent_reviews": recent_reviews,
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


def csrf_failure_view(request, reason="", template_name="403_csrf.html"):
    """
    Gracefully handles CSRF token mismatches and session rotations.
    If the user has a same-origin referer, automatically redirects back with an informative message
    so the page is re-rendered with valid, fresh CSRF tokens.
    """
    referer = request.META.get("HTTP_REFERER")
    if referer and request.method == "POST":
        host = request.get_host()
        if host in referer:
            messages.warning(
                request,
                "Your security session was refreshed. Please confirm your selection and proceed."
            )
            return redirect(referer)

    context = {
        "reason": reason,
        "referer": referer,
    }
    return render(request, "booking/403_csrf.html", context, status=403)

