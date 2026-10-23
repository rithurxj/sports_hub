from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Booking, Review, TimeSlot, Turf, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile / Role"


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "get_role", "is_staff", "is_superuser")

    def get_role(self, obj):
        if hasattr(obj, "profile"):
            return obj.profile.get_role_display()
        return "Customer"
    get_role.short_description = "Role"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "phone")


@admin.register(Turf)
class TurfAdmin(admin.ModelAdmin):
    list_display = ("name", "sport_type", "location", "price", "is_active", "owner")
    list_filter = ("sport_type", "is_active")
    search_fields = ("name", "location")


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("start_time", "end_time", "is_active")
    list_filter = ("is_active",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "turf", "user", "date", "time_slot", 
        "total_amount", "status", "payment_status", "razorpay_payment_id", "booked_at"
    )
    list_filter = ("status", "payment_status", "date", "turf")
    search_fields = ("turf__name", "user__username", "user__email", "razorpay_order_id", "razorpay_payment_id")
    date_hierarchy = "date"
    readonly_fields = ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "paid_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("turf", "user", "rating", "title", "is_verified", "created_at")
    list_filter = ("rating", "is_verified", "turf")
    search_fields = ("turf__name", "user__username", "title", "comment")

