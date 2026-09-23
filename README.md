# Sports Hub - Turf Booking Management System

A full-stack web-based mini project for booking football and cricket turfs with **Role-Based Authentication** (`Customer / Player` vs `Turf Admin / Manager`), real-time interactive slot availability, and a sports-tech user interface.

---

## 🌟 Key Features

### 1. Role-Based Authentication & Authorization
- **Customer / Player**:
  - Sign up as a player.
  - Browse and search turfs filtered by sport (`Football ⚽`, `Cricket 🏏`, `Multi-Sport 🏆`).
  - View detailed ground specs (surface type, floodlights, amenities, pricing).
  - Real-time slot availability check (green for available, red for booked, gray for past).
  - Book playing grounds with duplicate conflict prevention.
  - **Player Dashboard**: Track upcoming games, total reservations, and cancel bookings.
- **Turf Admin / Manager**:
  - Sign up as a manager or use pre-configured admin access.
  - **Admin Operations Dashboard**: Live metrics on total turfs, active grounds, today's schedule, total revenue (₹), and recent bookings.
  - **Grounds Management**: Add new turfs, edit pricing, surface types, contact info, and toggle active status.
  - **Time Slot Management**: Define daily playing intervals.
  - **Bookings Registry**: Filter all reservations by turf, date, and status with one-click Confirm, Cancel, or Complete actions.
  - Access to both custom frontend management portal and Django Admin (`/admin/`).

---

## 🛠️ Technology Stack
- **Frontend**: HTML5, Vanilla CSS3 (Sports Obsidian & Pitch Emerald theme, Outfit + Inter typography, responsive glassmorphism), Vanilla JavaScript for AJAX slot availability.
- **Backend**: Python 3.12+, Django 5.x
- **Database**: MySQL / SQLite (configured with seamless fallback)
- **Authentication**: Role-based Django Authentication with `UserProfile` model and Django Groups.

---

## 🚀 Quick Start Guide

### 1. Virtual Environment Setup
```powershell
# Windows
.\env\Scripts\activate
```

### 2. Database Configuration
By default, the project connects to MySQL (`sports_hub` database).
To run on **SQLite** instead, set:
```powershell
$env:USE_SQLITE="1"
```

### 3. Run Migrations
```powershell
python manage.py makemigrations
python manage.py migrate
```

### 4. Load Demo Data (Turfs, Slots, and Roles)
Run the built-in seed command to populate 6 football & cricket turfs, standard time slots, and pre-configured accounts:
```powershell
python manage.py seed_data
```

### 5. Start Development Server
```powershell
python manage.py runserver
```
Visit: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🔑 Pre-Configured Demo Accounts

| Role | Username | Password | Dashboard URL |
| :--- | :--- | :--- | :--- |
| **Turf Admin / Manager** | `admin` | `admin123` | [http://127.0.0.1:8000/admin-dashboard/](http://127.0.0.1:8000/admin-dashboard/) |
| **Player / Customer** | `player1` | `player123` | [http://127.0.0.1:8000/customer-dashboard/](http://127.0.0.1:8000/customer-dashboard/) |

---

## 🧪 Automated Testing
Run the test suite:
```powershell
python manage.py test booking
```
Verifies:
- Customer role profile restrictions (customers cannot access admin portal).
- Admin role profile access.
- Real-time availability API returning slot states.
- Duplicate booking conflict prevention.
