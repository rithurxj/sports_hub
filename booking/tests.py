import datetime
from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from booking.models import Booking, TimeSlot, Turf, UserProfile


class RoleBasedAuthAndBookingTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Groups
        self.customer_group = Group.objects.create(name="Customer")
        self.admin_group = Group.objects.create(name="Admin")

        # Admin user
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password="testpassword123",
            email="admin@test.com",
            is_staff=True,
        )
        self.admin_profile = self.admin_user.profile
        self.admin_profile.role = "ADMIN"
        self.admin_profile.save()
        self.admin_user.groups.add(self.admin_group)

        # Customer user
        self.customer_user = User.objects.create_user(
            username="customer_test",
            password="testpassword123",
            email="customer@test.com",
        )
        self.cust_profile = self.customer_user.profile
        self.cust_profile.role = "CUSTOMER"
        self.cust_profile.save()
        self.customer_user.groups.add(self.customer_group)

        # Time Slot
        self.slot = TimeSlot.objects.create(
            start_time=datetime.time(18, 0),
            end_time=datetime.time(19, 0),
            is_active=True,
        )

        # Turf
        self.turf = Turf.objects.create(
            name="Test Arena",
            sport_type="FOOTBALL",
            location="Test Road",
            price=1200.00,
            is_active=True,
        )

    def test_customer_role_profile(self):
        """Test customer has customer role and cannot access admin dashboard."""
        self.assertTrue(self.cust_profile.is_customer_user)
        self.assertFalse(self.cust_profile.is_admin_user)

        self.client.login(username="customer_test", password="testpassword123")
        response = self.client.get(reverse("admin_dashboard"))
        # Should be redirected to customer_dashboard with error message
        self.assertRedirects(response, reverse("customer_dashboard"))

    def test_admin_role_profile(self):
        """Test admin user has admin role and can access admin dashboard."""
        self.assertTrue(self.admin_profile.is_admin_user)
        self.assertFalse(self.admin_profile.is_customer_user)

        self.client.login(username="admin_test", password="testpassword123")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Turf Operations Hub")

    def test_availability_api(self):
        """Test slot availability API accurately reports booked vs free slots."""
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)

        # 1. Check before booking
        response = self.client.get(
            reverse("turf_availability_api", kwargs={"pk": self.turf.pk}),
            {"date": tomorrow.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["slots"]), 1)
        self.assertTrue(data["slots"][0]["is_available"])
        self.assertFalse(data["slots"][0]["is_booked"])

        # 2. Book slot
        Booking.objects.create(
            user=self.customer_user,
            turf=self.turf,
            date=tomorrow,
            time_slot=self.slot,
            status="CONFIRMED",
        )

        # 3. Check after booking
        response2 = self.client.get(
            reverse("turf_availability_api", kwargs={"pk": self.turf.pk}),
            {"date": tomorrow.isoformat()}
        )
        data2 = response2.json()
        self.assertFalse(data2["slots"][0]["is_available"])
        self.assertTrue(data2["slots"][0]["is_booked"])

    def test_duplicate_booking_prevention(self):
        """Ensure system prevents duplicate confirmed bookings for same turf, date, slot."""
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)

        self.client.login(username="customer_test", password="testpassword123")
        # First booking succeeds
        post_data = {
            "date": tomorrow.isoformat(),
            "time_slot": self.slot.id,
            "notes": "First match",
        }
        resp = self.client.post(reverse("book_turf", kwargs={"pk": self.turf.pk}), post_data)
        self.assertRedirects(resp, reverse("my_bookings"))
        self.assertEqual(Booking.objects.filter(turf=self.turf, date=tomorrow, status="CONFIRMED").count(), 1)

        # Second booking attempt on same slot fails with error
        resp2 = self.client.post(reverse("book_turf", kwargs={"pk": self.turf.pk}), post_data)
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "already booked")
        self.assertEqual(Booking.objects.filter(turf=self.turf, date=tomorrow, status="CONFIRMED").count(), 1)
