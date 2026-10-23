from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.utils import timezone
from .models import Booking, Review, TimeSlot, Turf, UserProfile


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = [
        ("CUSTOMER", "⚽🏸 Player / Customer (Browse & Book Grounds & Courts)"),
        ("ADMIN", "🏟️ Venue Admin / Manager (Manage Venues & Bookings)"),
    ]

    first_name = forms.CharField(max_length=30, required=True, label="Full Name", widget=forms.TextInput(attrs={
        "placeholder": "Enter your full name",
        "class": "form-control",
    }))
    email = forms.EmailField(required=True, label="Email Address", widget=forms.EmailInput(attrs={
        "placeholder": "name@example.com",
        "class": "form-control",
    }))
    phone = forms.CharField(max_length=15, required=False, label="Phone Number", widget=forms.TextInput(attrs={
        "placeholder": "+91 98765 43210",
        "class": "form-control",
    }))
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial="CUSTOMER",
        widget=forms.RadioSelect(attrs={"class": "role-radio"}),
        label="I am registering as:",
        help_text="Choose Player to book grounds & courts, or Venue Manager to list and manage your venues."
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "phone", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "placeholder": "Choose a username",
            "class": "form-control",
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        
        selected_role = self.cleaned_data.get("role", "CUSTOMER")
        if selected_role == "ADMIN":
            user.is_staff = True  # Allows turf managers staff permissions

        if commit:
            user.save()
            # Ensure UserProfile is saved with role and phone
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = selected_role
            profile.phone = self.cleaned_data.get("phone", "")
            profile.save()

            # Synchronize Django group
            group_name = "Admin" if selected_role == "ADMIN" else "Customer"
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        return user


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        "placeholder": "Enter your username",
        "class": "form-control",
        "autofocus": True,
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "placeholder": "Enter your password",
        "class": "form-control",
    }))


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("date", "time_slot", "notes")
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control date-picker",
                "id": "booking-date-input",
            }),
            "time_slot": forms.Select(attrs={
                "class": "form-control",
                "id": "time-slot-select",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Optional: Team name, match notes, equipment needed...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.fields["time_slot"].empty_label = "-- Choose a time slot --"
        self.fields["time_slot"].queryset = TimeSlot.objects.filter(is_active=True)


class TurfForm(forms.ModelForm):
    class Meta:
        model = Turf
        fields = (
            "name",
            "sport_type",
            "location",
            "price",
            "surface_type",
            "contact_number",
            "image_url",
            "description",
            "is_active",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Apex Badminton Arena or GreenField Turf"}),
            "sport_type": forms.Select(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Koramangala, Bangalore"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 600"}),
            "surface_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Synthetic Mat, Teak Wood, Hard Court, or Turf"}),
            "contact_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 98765 43210"}),
            "image_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com/venue.jpg (optional)"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Describe court dimensions, lighting, amenities, non-marking shoe requirements..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ("start_time", "end_time", "is_active")
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "title", "comment")
        widgets = {
            "rating": forms.Select(attrs={
                "class": "form-control rating-select",
                "id": "review-rating-select",
            }),
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Headline of your review (e.g. Great floodlights & crisp artificial turf!)",
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Tell other players about grass quality, lighting, parking, ball bounce, amenities...",
                "required": True,
            }),
        }

