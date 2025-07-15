# Birdnest PMS Documentation

## Overview
Birdnest PMS is a Django-based Property Management System for hotels, providing reservation, guest, and room management features with a modern web interface.

## Project Structure
- `hotel_pms/` – Django project settings and root URLs
- `pms/` – Main app for hotel management
  - `models.py` – Data models: Room, Guest, Reservation
  - `views.py` – Business logic and endpoints
  - `forms.py` – Django forms for reservations and guests
  - `templates/pms/` – HTML templates for UI
  - `urls.py` – App-specific URL routing
  - `admin.py` – Django admin customizations

## Key Features
- Create, edit, and manage reservations
- Add and manage guests
- Room status tracking (vacant, occupied, dirty, clean)
- AJAX-powered guest addition and dynamic dropdown updates
- Calendar and dashboard views for occupancy

## Main Endpoints
- `/reservations/create/` – Create a new reservation
- `/guests/` – Add a new guest (POST)
- `/guests/json/` – Get guest list as JSON (GET, AJAX)
- `/rooms/` – Room status management
- `/dashboard/` – Occupancy and reservation overview

## AJAX Endpoints
- `POST /guests/` – Add guest via modal
- `GET /guests/json/` – Fetch guest list for dropdown

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Start server: `python manage.py runserver`
4. Access at `http://localhost:8000/`

## Testing
- Add tests in `pms/tests.py` and run with `python manage.py test pms`

## Contribution Guidelines
- Follow Django best practices
- Write docstrings for all new functions/classes
- Add/Update tests for new features
- Keep code style consistent (PEP8)

## Contact
For questions or contributions, please contact the project maintainer.