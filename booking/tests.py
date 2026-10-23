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
        # First booking creates pending reservation and redirects to payment checkout
        post_data = {
            "date": tomorrow.isoformat(),
            "time_slot": self.slot.id,
            "notes": "First match",
        }
        resp = self.client.post(reverse("book_turf", kwargs={"pk": self.turf.pk}), post_data)
        booking = Booking.objects.filter(turf=self.turf, date=tomorrow, user=self.customer_user).first()
        self.assertIsNotNone(booking)
        self.assertRedirects(resp, reverse("payment_checkout", kwargs={"pk": booking.pk}))

        # Follow redirect to checkout page which sets razorpay_order_id
        checkout_resp = self.client.get(resp.url)
        self.assertEqual(checkout_resp.status_code, 200)
        booking.refresh_from_db()

        # Complete payment via verify endpoint
        verify_data = {
            "booking_id": booking.id,
            "razorpay_payment_id": "pay_test_12345",
            "razorpay_order_id": booking.razorpay_order_id or "order_test_12345",
            "razorpay_signature": "sim_signature_12345",
            "is_simulation": "1",
        }
        verify_resp = self.client.post(reverse("payment_verify"), verify_data)
        self.assertRedirects(verify_resp, reverse("payment_confirmation", kwargs={"pk": booking.pk}))
        booking.refresh_from_db()
        self.assertEqual(booking.status, "CONFIRMED")
        self.assertEqual(booking.payment_status, "PAID")

        # Second booking attempt on same slot fails because it's already confirmed
        resp2 = self.client.post(reverse("book_turf", kwargs={"pk": self.turf.pk}), post_data)
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "already booked")
        self.assertEqual(Booking.objects.filter(turf=self.turf, date=tomorrow, status="CONFIRMED").count(), 1)

    def test_razorpay_checkout_and_verification(self):
        """Test Razorpay checkout page loads and payment verification completes."""
        tomorrow = timezone.localdate() + datetime.timedelta(days=2)
        booking = Booking.objects.create(
            user=self.customer_user,
            turf=self.turf,
            date=tomorrow,
            time_slot=self.slot,
            status="PENDING",
            payment_status="PENDING",
            total_amount=self.turf.price,
        )

        self.client.login(username="customer_test", password="testpassword123")
        checkout_resp = self.client.get(reverse("payment_checkout", kwargs={"pk": booking.pk}))
        self.assertEqual(checkout_resp.status_code, 200)
        self.assertContains(checkout_resp, "Razorpay Secure Checkout")
        booking.refresh_from_db()

        # Simulate successful payment
        post_data = {
            "booking_id": booking.id,
            "razorpay_payment_id": "pay_sim_98765",
            "razorpay_order_id": booking.razorpay_order_id or "order_test_98765",
            "razorpay_signature": "sim_sig_test",
            "is_simulation": "1",
        }
        verify_resp = self.client.post(reverse("payment_verify"), post_data)
        self.assertRedirects(verify_resp, reverse("payment_confirmation", kwargs={"pk": booking.pk}))

        booking.refresh_from_db()
        self.assertEqual(booking.status, "CONFIRMED")
        self.assertEqual(booking.payment_status, "PAID")
        self.assertEqual(booking.razorpay_payment_id, "pay_sim_98765")
        self.assertIsNotNone(booking.paid_at)

    def test_feedback_and_review_workflow(self):
        """Test submitting player feedback and review, and computing average rating."""
        from booking.models import Review

        # Create confirmed booking for verified status
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        booking = Booking.objects.create(
            user=self.customer_user,
            turf=self.turf,
            date=tomorrow,
            time_slot=self.slot,
            status="CONFIRMED",
            payment_status="PAID",
        )

        self.client.login(username="customer_test", password="testpassword123")

        # GET review page
        get_resp = self.client.get(reverse("add_review", kwargs={"turf_id": self.turf.pk}), {"booking": booking.id})
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "Rate & Review Ground")


        # POST review
        post_data = {
            "rating": 5,
            "title": "Superb playing turf",
            "comment": "FIFA standard artificial grass, smooth ball bounce, bright floodlights!",
            "booking_id": booking.id,
        }
        post_resp = self.client.post(reverse("add_review", kwargs={"turf_id": self.turf.pk}), post_data)
        self.assertRedirects(post_resp, reverse("turf_detail", kwargs={"pk": self.turf.pk}))

        review = Review.objects.filter(turf=self.turf, user=self.customer_user).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)
        self.assertTrue(review.is_verified)
        self.assertEqual(self.turf.average_rating, 5.0)
        self.assertEqual(self.turf.reviews_count, 1)

        # Check turf detail contains review
        detail_resp = self.client.get(reverse("turf_detail", kwargs={"pk": self.turf.pk}))
        self.assertContains(detail_resp, "Superb playing turf")
        self.assertContains(detail_resp, "Verified Match")

    def test_badminton_and_tennis_court_booking_and_filters(self):
        """Test badminton court and tennis court creation, icons, filtering, and booking."""
        badminton_court = Turf.objects.create(
            name="Apex Indoor Badminton Arena",
            sport_type="BADMINTON",
            location="Indiranagar, Bangalore",
            price=600.00,
            surface_type="BWF Approved Wooden Court",
            is_active=True,
        )
        tennis_court = Turf.objects.create(
            name="Grand Slam Tennis Arena",
            sport_type="TENNIS",
            location="Koramangala, Bangalore",
            price=900.00,
            surface_type="DecoTurf Championship Hard Court",
            is_active=True,
        )

        self.assertEqual(badminton_court.sport_icon, "🏸")
        self.assertEqual(badminton_court.get_sport_type_display(), "Badminton Court")
        self.assertEqual(tennis_court.sport_icon, "🎾")
        self.assertEqual(tennis_court.get_sport_type_display(), "Tennis Court")

        # Test filtering by BADMINTON
        resp_badminton = self.client.get(reverse("turf_list"), {"sport": "BADMINTON"})
        self.assertEqual(resp_badminton.status_code, 200)
        self.assertContains(resp_badminton, "Apex Indoor Badminton Arena")
        self.assertNotContains(resp_badminton, "Grand Slam Tennis Arena")

        # Test filtering by TENNIS
        resp_tennis = self.client.get(reverse("turf_list"), {"sport": "TENNIS"})
        self.assertEqual(resp_tennis.status_code, 200)
        self.assertContains(resp_tennis, "Grand Slam Tennis Arena")
        self.assertNotContains(resp_tennis, "Apex Indoor Badminton Arena")

        # Test booking a badminton court slot
        self.client.login(username="customer_test", password="testpassword123")
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        book_resp = self.client.post(
            reverse("book_turf", kwargs={"pk": badminton_court.pk}),
            {
                "date": tomorrow.isoformat(),
                "time_slot": self.slot.id,
                "notes": "Singles badminton practice",
            }
        )
        # Should redirect to payment checkout
        booking = Booking.objects.filter(turf=badminton_court, date=tomorrow, time_slot=self.slot).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.total_amount, 600.00)
        self.assertRedirects(book_resp, reverse("payment_checkout", kwargs={"pk": booking.pk}))

    def test_scoreboard_access_and_roles(self):
        """Test live scoreboard is accessible by customer users and hidden from admins."""
        # 1. Anonymous user redirected to login
        anon_resp = self.client.get(reverse("scoreboard"))
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn(reverse("login"), anon_resp.url)

        # 2. Customer login -> 200 OK with all 4 sports panels
        self.client.login(username="customer_test", password="testpassword123")
        cust_resp = self.client.get(reverse("scoreboard"))
        self.assertEqual(cust_resp.status_code, 200)
        self.assertContains(cust_resp, "Box Cricket")
        self.assertContains(cust_resp, "Football / Futsal")
        self.assertContains(cust_resp, "Tennis Court Scoreboard")
        self.assertContains(cust_resp, "Badminton 21-Point Arena")

        # 3. Customer sees Scoreboard option near Explore Grounds in navbar
        home_resp = self.client.get(reverse("home"))
        self.assertContains(home_resp, "Scoreboard")

        # 4. Admin user is redirected away with message and does not have Scoreboard in navbar
        self.client.login(username="admin_test", password="testpassword123")
        admin_resp = self.client.get(reverse("scoreboard"))
        self.assertRedirects(admin_resp, reverse("admin_dashboard"))

        admin_home_resp = self.client.get(reverse("home"))
        # Scoreboard link should not be rendered in admin nav
        self.assertNotContains(admin_home_resp, reverse("scoreboard"))

    def test_csrf_failure_handling(self):
        """Test custom csrf_failure_view graceful redirect and 403 template rendering."""
        from django.test import RequestFactory
        from booking.views import csrf_failure_view

        factory = RequestFactory()

        # Case 1: POST request with same-host referer redirects back with message
        request = factory.post("/turfs/1/book/", HTTP_REFERER="http://testserver/turfs/1/book/")
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, "session", self.client.session)
        messages_storage = FallbackStorage(request)
        setattr(request, "_messages", messages_storage)

        response = csrf_failure_view(request, reason="CSRF token from POST incorrect.")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://testserver/turfs/1/book/")

        # Case 2: Request without referer renders 403_csrf template with 403 status
        no_ref_request = factory.get("/turfs/1/book/")
        setattr(no_ref_request, "session", self.client.session)
        no_ref_request._messages = FallbackStorage(no_ref_request)
        no_ref_resp = csrf_failure_view(no_ref_request, reason="CSRF cookie not set.")
        self.assertEqual(no_ref_resp.status_code, 403)
        self.assertContains(no_ref_resp, "Security Token Refreshed", status_code=403)




