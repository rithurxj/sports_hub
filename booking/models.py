from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("CUSTOMER", "Customer / Player"),
        ("ADMIN", "Turf Admin / Manager"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="CUSTOMER")
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        return self.role == "ADMIN" or self.user.is_superuser or self.user.is_staff

    @property
    def is_customer_user(self):
        return self.role == "CUSTOMER" and not (self.user.is_superuser or self.user.is_staff)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        role = "ADMIN" if instance.is_superuser or instance.is_staff else "CUSTOMER"
        UserProfile.objects.get_or_create(user=instance, defaults={"role": role})
    else:
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if (instance.is_superuser or instance.is_staff) and profile.role != "ADMIN":
            profile.role = "ADMIN"
            profile.save(update_fields=["role"])


class Turf(models.Model):
    SPORT_CHOICES = [
        ("FOOTBALL", "Football"),
        ("CRICKET", "Cricket"),
        ("BADMINTON", "Badminton Court"),
        ("TENNIS", "Tennis Court"),
        ("MULTI", "Multi-Sport"),
    ]

    name = models.CharField(max_length=120)
    sport_type = models.CharField(max_length=20, choices=SPORT_CHOICES, default="FOOTBALL")
    location = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per slot (in ₹)")
    surface_type = models.CharField(max_length=100, default="Artificial Grass (FIFA Approved)")
    contact_number = models.CharField(max_length=20, blank=True, default="+91 98765 43210")
    image_url = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_turfs",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_sport_type_display()})"

    @property
    def sport_icon(self):
        if self.sport_type == "FOOTBALL":
            return "⚽"
        elif self.sport_type == "CRICKET":
            return "🏏"
        elif self.sport_type == "BADMINTON":
            return "🏸"
        elif self.sport_type == "TENNIS":
            return "🎾"
        return "🏆"

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(models.Avg("rating"))["rating__avg"]
        return round(float(agg), 1) if agg is not None else 0.0

    @property
    def reviews_count(self):
        return self.reviews.count()

    @property
    def rating_stars_display(self):
        avg = self.average_rating
        if avg == 0:
            return "No reviews yet"
        full = int(round(avg))
        return "★" * full + "☆" * (5 - full)

    @property
    def rating_breakdown(self):
        total = self.reviews.count()
        if total == 0:
            return {star: {"count": 0, "pct": 0} for star in range(5, 0, -1)}
        breakdown = {}
        for star in range(5, 0, -1):
            count = self.reviews.filter(rating=star).count()
            breakdown[star] = {
                "count": count,
                "pct": int(round((count / total) * 100))
            }
        return breakdown


class TimeSlot(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["start_time", "end_time"],
                name="unique_time_slot"
            )
        ]

    def __str__(self):
        return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Payment Pending"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
        ("COMPLETED", "Completed"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE, related_name="bookings")
    date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name="bookings")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="CONFIRMED")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="PAID")
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "time_slot__start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["turf", "date", "time_slot"],
                condition=models.Q(status="CONFIRMED"),
                name="unique_confirmed_turf_date_slot",
            )
        ]

    def clean(self):
        if self.date and self.date < __import__("datetime").date.today():
            raise ValidationError("Booking date cannot be in the past.")

    def save(self, *args, **kwargs):
        if not self.total_amount and self.turf:
            self.total_amount = self.turf.price
        super().save(*args, **kwargs)

    @property
    def is_paid(self):
        return self.payment_status == "PAID"

    def __str__(self):
        return f"{self.turf.name} - {self.date} - {self.time_slot} ({self.status})"


class Review(models.Model):
    RATING_CHOICES = [
        (5, "5 ★ - Excellent"),
        (4, "4 ★ - Very Good"),
        (3, "3 ★ - Good"),
        (2, "2 ★ - Fair"),
        (1, "1 ★ - Poor"),
    ]

    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField(help_text="Detailed feedback about turf grass, lighting, amenities, etc.")
    is_verified = models.BooleanField(default=True, help_text="Verified player who booked this ground")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.turf.name} ({self.rating}★)"

