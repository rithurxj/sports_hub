import datetime
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone
from booking.models import Booking, TimeSlot, Turf, UserProfile


class Command(BaseCommand):
    help = "Seeds initial turfs, time slots, demo roles, and sample data."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding turf booking data..."))

        # 1. Create User Groups
        customer_group, _ = Group.objects.get_or_create(name="Customer")
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        # 2. Create Demo Admin User
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@sportshub.com",
                "first_name": "Turf",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        admin_user.set_password("admin123")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        admin_user.groups.add(admin_group)

        admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        admin_profile.role = "ADMIN"
        admin_profile.phone = "+91 99887 76655"
        admin_profile.save()

        self.stdout.write(self.style.SUCCESS("[OK] Admin user configured (admin / admin123)"))

        # 3. Create Demo Customer Users
        customer_user, _ = User.objects.get_or_create(
            username="player1",
            defaults={
                "email": "player1@gmail.com",
                "first_name": "Alex",
                "last_name": "Hunter",
            }
        )
        customer_user.set_password("player123")
        customer_user.save()
        customer_user.groups.add(customer_group)

        cust_profile, _ = UserProfile.objects.get_or_create(user=customer_user)
        cust_profile.role = "CUSTOMER"
        cust_profile.phone = "+91 91234 56789"
        cust_profile.save()

        self.stdout.write(self.style.SUCCESS("[OK] Customer user configured (player1 / player123)"))

        # 4. Create Standard Time Slots
        slot_times = [
            (datetime.time(6, 0), datetime.time(7, 0)),
            (datetime.time(7, 0), datetime.time(8, 0)),
            (datetime.time(8, 0), datetime.time(9, 0)),
            (datetime.time(9, 0), datetime.time(10, 0)),
            (datetime.time(16, 0), datetime.time(17, 0)),
            (datetime.time(17, 0), datetime.time(18, 0)),
            (datetime.time(18, 0), datetime.time(19, 0)),
            (datetime.time(19, 0), datetime.time(20, 0)),
            (datetime.time(20, 0), datetime.time(21, 0)),
            (datetime.time(21, 0), datetime.time(22, 0)),
            (datetime.time(22, 0), datetime.time(23, 0)),
        ]

        created_slots = []
        for start, end in slot_times:
            slot, _ = TimeSlot.objects.get_or_create(
                start_time=start,
                end_time=end,
                defaults={"is_active": True}
            )
            created_slots.append(slot)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(created_slots)} Time Slots active"))

        # 5. Create Football & Cricket Turfs
        turfs_data = [
            {
                "name": "GreenField Football Arena",
                "sport_type": "FOOTBALL",
                "location": "Koramangala 4th Block, Bangalore",
                "price": 1200.00,
                "surface_type": "FIFA Grade 50mm Monofilament Turf",
                "contact_number": "+91 98450 12345",
                "description": "Premium 7-a-side all-weather football ground featuring high-intensity LED floodlights, professional bibs, and locker rooms.",
                "owner": admin_user,
            },
            {
                "name": "Camp Nou Caged Turf",
                "sport_type": "FOOTBALL",
                "location": "100ft Road, Indiranagar, Bangalore",
                "price": 1400.00,
                "surface_type": "High Shock Absorption Artificial Turf",
                "contact_number": "+91 98450 67890",
                "description": "Enclosed 5-a-side caged football turf with cushioned rebound netting, pristine lighting, and complimentary mineral water.",
                "owner": admin_user,
            },
            {
                "name": "Wankhede Box Cricket & Turf",
                "sport_type": "CRICKET",
                "location": "Sector 2, HSR Layout, Bangalore",
                "price": 1000.00,
                "surface_type": "Dense Multi-sport Needle Punch Grass",
                "contact_number": "+91 97410 11223",
                "description": "Dedicated indoor-style box cricket stadium equipped with side boundary netting, automatic bowling machine option, and bats.",
                "owner": admin_user,
            },
            {
                "name": "Lord's Cricket Ground & Nets",
                "sport_type": "CRICKET",
                "location": "ITPL Main Road, Whitefield, Bangalore",
                "price": 1100.00,
                "surface_type": "Reinforced Turf Pitch for Tennis Ball",
                "contact_number": "+91 97410 44556",
                "description": "Full-size box cricket ground with raised spectator gallery, digital scoring display, and night match tournament lighting.",
                "owner": admin_user,
            },
            {
                "name": "Urban Champions Sports Hub",
                "sport_type": "MULTI",
                "location": "Outer Ring Road, Marathahalli, Bangalore",
                "price": 1500.00,
                "surface_type": "Dual-Line Hybrid Sports Turf",
                "contact_number": "+91 98860 99887",
                "description": "State-of-the-art multi-sport complex designed for both fast-paced football matches and weekend cricket tournaments.",
                "owner": admin_user,
            },
            {
                "name": "Thunderbolt Arena 6v6",
                "sport_type": "FOOTBALL",
                "location": "Phase 1, Electronic City, Bangalore",
                "price": 1300.00,
                "surface_type": "High Density European Turf",
                "contact_number": "+91 98860 33445",
                "description": "Spacious 6-a-side ground with automated video replay cameras for match analysis and ample vehicle parking.",
                "owner": admin_user,
            },
        ]

        created_turfs = []
        for t_data in turfs_data:
            turf, _ = Turf.objects.get_or_create(
                name=t_data["name"],
                defaults=t_data,
            )
            created_turfs.append(turf)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(created_turfs)} Turfs created (Football & Cricket)"))

        # 6. Sample Booking for player1
        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)
        if created_turfs and created_slots:
            sample_turf = created_turfs[0]
            sample_slot = created_slots[7]  # 19:00 - 20:00

            booking, created = Booking.objects.get_or_create(
                turf=sample_turf,
                date=tomorrow,
                time_slot=sample_slot,
                defaults={
                    "user": customer_user,
                    "status": "CONFIRMED",
                    "total_amount": sample_turf.price,
                    "notes": "Evening 7v7 friendly match with office team",
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"[OK] Sample booking created for tomorrow ({booking})"))

        self.stdout.write(self.style.SUCCESS("[OK] Seeding complete!"))
