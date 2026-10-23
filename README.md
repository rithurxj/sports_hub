# Sports Hub - Turfs & Courts Booking Management System

A full-stack web-based platform for booking football turfs, cricket pitches/arenas, badminton courts, and tennis courts with **Role-Based Authentication** (`Customer / Player` vs `Turf Admin / Manager`), real-time interactive slot availability, and a sports-tech user interface.

---

## 🌟 Key Features

### 1. Role-Based Authentication & Authorization
- **Customer / Player**:
  - Sign up as a player.
  - Browse and search venues filtered by sport (`Football ⚽`, `Cricket 🏏`, `Badminton 🏸`, `Tennis 🎾`, `Multi-Sport 🏆`).
  - View detailed court & ground specs (surface type like wooden synthetic / clay / grass, floodlights, amenities, pricing).
  - Real-time slot availability check (green for available, red for booked, gray for past).
  - Book playing grounds and courts with duplicate conflict prevention.
  - **Player Dashboard**: Track upcoming games, total reservations, and cancel bookings.
- **Turf & Court Admin / Manager**:
  - Sign up as a manager or use pre-configured admin access.
  - **Admin Operations Dashboard**: Live metrics on total venues, active grounds & courts, today's schedule, total revenue (₹), and recent bookings.
  - **Grounds & Courts Management**: Add new venues, edit pricing, surface types, contact info, and toggle active status.
  - **Time Slot Management**: Define daily playing intervals.
  - **Bookings Registry**: Filter all reservations by venue, date, and status with one-click Confirm, Cancel, or Complete actions.
  - Access to both custom frontend management portal and Django Admin (`/admin/`).

### 2. Razorpay Payment Gateway Integration
- **Seamless Checkout**: Customers are guided to a secure Razorpay checkout page after slot selection.
- **Multiple Payment Modes**: Supports UPI (GPay, PhonePe, Paytm), Credit & Debit Cards (Visa, MasterCard, RuPay), Netbanking, and Digital Wallets.
- **HMAC SHA256 Signature Verification**: Server-side verification using the official `razorpay` Python SDK.
- **Offline / Developer Simulation Sandbox**: Built-in 1-click test payment mode so examiners and developers can evaluate the entire end-to-end checkout and receipt generation even without active live API credentials.
- **Payment Lifecycle & Receipts**: Full tracking of `payment_status` (`PENDING`, `PAID`, `FAILED`, `REFUNDED`), Razorpay Payment ID, and instantaneous confirmation receipts.

### 3. Ground Reviews & Feedback System
- **Player Reviews**: 5-star rating breakdown and detailed feedback on artificial grass condition, lighting, changing rooms, and amenities.
- **Verified Match Badges**: Automatic detection of verified reservations, awarding a green `✓ Verified Match` badge to genuine players.
- **Turf Ratings & Sentiment**: Real-time average star ratings (e.g., `★ 4.8`) and distribution bars displayed on ground detail pages, search results, and turf cards.
- **Admin Visibility**: Turf managers track player satisfaction scores and incoming player feedback streams directly from the admin dashboard.

---

## 🛠️ Technology Stack
- **Frontend**: HTML5, Vanilla CSS3 (Sports Obsidian & Pitch Emerald theme, Plus Jakarta Sans + Inter typography), Vanilla JavaScript for AJAX slot availability and Razorpay Checkout modal.
- **Backend**: Python 3.12+, Django 5.x
- **Payments**: Razorpay Python SDK (`razorpay>=2.0.0`) & Razorpay Checkout.js
- **Database**: MySQL / SQLite (configured with seamless fallback)
- **Authentication**: Role-based Django Authentication with `UserProfile` model and Django Groups.

---

## 🚀 Quick Start Guide

### 1. Virtual Environment Setup
```powershell
# Windows
.\env\Scripts\activate
```

### 2. Database & Razorpay Configuration
By default, the project connects to MySQL (`sports_hub` database) and uses development Razorpay sandbox keys.
You can customize these in `.env`:
```ini
DB_NAME=sports_hub
DB_USER=root
DB_PASSWORD=your_password
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
```

To run on **SQLite** instead:
```powershell
$env:USE_SQLITE="1"
```

### 3. Run Migrations
```powershell
python manage.py makemigrations
python manage.py migrate
```

### 4. Load Demo Data (Turfs, Slots, and Roles)
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
Run the comprehensive test suite:
```powershell
python manage.py test booking
```
Verifies:
- Customer role profile restrictions.
- Admin role profile access.
- Real-time slot availability API.
- Booking creation and Razorpay payment checkout.
- Razorpay payment signature verification & payment status update to `PAID`.
- Player feedback submission, verified badge assignment, and average rating computation.

