from django.urls import path
from . import views

urlpatterns = [
    # Public & Discovery
    path("", views.home, name="home"),
    path("turfs/", views.turf_list, name="turf_list"),
    path("turfs/<int:pk>/", views.turf_detail, name="turf_detail"),
    path("turfs/<int:pk>/book/", views.book_turf, name="book_turf"),
    path("api/turfs/<int:pk>/availability/", views.turf_availability_api, name="turf_availability_api"),

    # Authentication
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Customer Workflow
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),

    # Admin / Turf Manager Workflow
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/turfs/", views.admin_turf_list, name="admin_turf_list"),
    path("admin-dashboard/turfs/add/", views.admin_turf_add, name="admin_turf_add"),
    path("admin-dashboard/turfs/<int:pk>/edit/", views.admin_turf_edit, name="admin_turf_edit"),
    path("admin-dashboard/turfs/<int:pk>/toggle/", views.admin_turf_toggle, name="admin_turf_toggle"),
    path("admin-dashboard/slots/", views.admin_slot_list, name="admin_slot_list"),
    path("admin-dashboard/slots/<int:pk>/delete/", views.admin_slot_delete, name="admin_slot_delete"),
    path("admin-dashboard/bookings/", views.admin_booking_list, name="admin_booking_list"),
    path("admin-dashboard/bookings/<int:pk>/status/<str:new_status>/", views.admin_booking_status, name="admin_booking_status"),
]
