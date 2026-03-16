# SmartApprove — Full Setup Guide (Windows)

## Credentials (ready to use)
- URL:      http://localhost:8000/auth/login
- Email:    admin@smartapprove.com
- Password: Admin1234

---

## Step-by-Step Setup

### Step 1 — Unzip
Extract the zip anywhere, e.g.:
  C:\Users\YourName\Downloads\smartapprove\

### Step 2 — Open Command Prompt in that folder
  - Open the smartapprove folder
  - Click the address bar, type cmd, press Enter

### Step 3 — Create virtual environment
  python -m venv venv

### Step 4 — Activate it
  venv\Scripts\activate
  (You'll see "(venv)" appear at the start of the line)

### Step 5 — Install dependencies
  pip install -r requirements.txt

### Step 6 — Run the server
  python run.py

### Step 7 — Open browser
  http://localhost:8000/auth/login

That's it. Done.

---

## User Roles

| Role     | Can Do                                              |
|----------|-----------------------------------------------------|
| Employee | Submit requests, view own, comment, attach files    |
| Manager  | All above + approve/reject requests assigned to them|
| Admin    | Everything + user management via /admin panel       |

To promote a user to Manager/Admin:
1. Login as admin
2. Go to http://localhost:8000/admin
3. Change role in the dropdown next to the user

---

## Common Errors & Fixes

ERROR: No module named 'pydantic_settings'
FIX:   pip install pydantic-settings

ERROR: 'cp' is not recognized
FIX:   You're on Windows. The .env file is already included. Skip that step.

ERROR: Application startup failed
FIX:   Delete smartapprove.db and run again: del smartapprove.db

ERROR: Port already in use
FIX:   Change port in run.py from 8000 to 8001

---

## Project Structure

smartapprove/
  app/
    main.py          — App entry point, router registration
    config.py        — Settings from .env
    database.py      — SQLAlchemy setup
    models/          — Database models (User, Request, etc.)
    routers/
      auth.py        — /auth/login  /auth/register  /auth/logout
      requests.py    — /requests/   /requests/new   /requests/{id}
      dashboard.py   — /dashboard   /admin          /notifications
    services/
      auth.py        — JWT + bcrypt password hashing
      files.py       — Secure file upload
    templates/       — Jinja2 HTML templates
    static/          — CSS, JS, uploaded files
  run.py             — Start server
  .env               — Configuration
  requirements.txt   — Dependencies
