# Developer guide

This repository is a Django project split into module apps. Run commands from the repository root in PowerShell.

## Setup and run

Install the locked dependencies:

```powershell
uv sync
```

Start Django:

```powershell
uv run manage.py runserver
```

Open `http://127.0.0.1:8000/`. Django reloads Python and template changes automatically.

## URL map

| Area | URL | Django app |
|---|---|---|
| CoRide landing page | `/` | `CORIDE` |
| Users | `/users/` | `utilisateurs` |
| Vehicles | `/vehicles/` | `vehicules` |
| Trips | `/trips/` | `trajets` |
| Reservations | `/reservations/` | `reservations` |
| Communication | `/coms/` | `communication` |
| Django admin | `/admin/` | Django admin |

Add routes in each app's `urls.py`; project-level prefixes are wired in `config/urls.py`. Views belong in the app's `views.py`. Shared landing-page templates are in `CORIDE/`, and shared static assets are in `assets/`.

## Module documentation

The apps are currently scaffolds with shared placeholder pages; their planned features remain to be implemented. Each app has a current-state log, specification and screenshot:

| App | Current state | Specification | Screenshot |
|---|---|---|---|
| CoRide | [AI.log](CORIDE/AI.log) | — | [home](CORIDE/screenshots/home.png) |
| Users | [AI.log](utilisateurs/AI.log) | [requirements](utilisateurs/01_user-management.md) | [preview](utilisateurs/screenshots/users.png) |
| Vehicles | [AI.log](vehicules/AI.log) | [requirements](vehicules/02_vehicle-management.md) | [preview](vehicules/screenshots/vehicles.png) |
| Trips | [AI.log](trajets/AI.log) | [requirements](trajets/03_trip-management.md) | [preview](trajets/screenshots/trips.png) |
| Reservations | [AI.log](reservations/AI.log) | [requirements](reservations/04_reservation-management.md) | [preview](reservations/screenshots/reservations.png) |
| Communication | [AI.log](communication/AI.log) | [requirements](communication/05_communication-feedback.md) | [preview](communication/screenshots/coms.png) |

## Common Django commands

Use `uv run` so each command uses the project's locked environment:

```powershell
# Check settings, installed apps and URL configuration
uv run manage.py check

# Create migration files after changing models
uv run manage.py makemigrations

# Apply migrations
uv run manage.py migrate

# Run all tests or only one app's tests
uv run manage.py test
uv run manage.py test trajets

# Open the Django shell or create an admin login
uv run manage.py shell
uv run manage.py createsuperuser
```

Commit migration files with the model changes that generated them. Do not edit an already shared migration; create a new one instead.

To scaffold an app:

```powershell
uv run manage.py startapp my_app
```

Then add its `AppConfig` to `INSTALLED_APPS` in `config/settings.py`, create `my_app/urls.py`, and include it under a prefix in `config/urls.py`.

## Static files

Shared assets such as `assets/kitty.png` are collected into `STATIC_ROOT` during a Vercel build and served from `STATIC_URL`. Keep `STATIC_ROOT` configured in `config/settings.py`, and reference assets in templates with `{% static %}`. Use Django for local development and testing.

## Repository workflow

The shared integration branch is `master`. Module branches are `utilisateurs`, `vehicules`, `trajets`, `reservations` and `communication`. Work on your assigned branch and open a pull request to `master`; coordinate changes to shared settings, URLs or the `CORIDE` UI.

```powershell
git status
git fetch origin
git switch trajets
git pull

uv run manage.py check
uv run manage.py test trajets
git add trajets/
git commit -m "Describe the change"
git push
```

Replace `trajets` with your module branch. Stage only files related to your change rather than using `git add .`, which can include unrelated work.
