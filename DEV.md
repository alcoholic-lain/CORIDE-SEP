# Developer guide

This repository is a single Django project split into module apps. Run commands from the repository root in PowerShell.

## Setup and run

Install the pinned dependencies and create/update the project environment:

```powershell
uv sync
```

Start the development server:

```powershell
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Django reloads Python and template changes automatically while the server is running.

## URL map

Each module has its own URL prefix and URL configuration:

| Area | URL | Django app |
|---|---|---|
| CoRide landing page | `/` | `CORIDE` |
| Users | `/users/` | `utilisateurs` |
| Vehicles | `/vehicles/` | `vehicules` |
| Trips | `/trips/` | `trajets` |
| Reservations | `/reservations/` | `reservations` |
| Communication | `/coms/` | `communication` |
| Django admin | `/admin/` | Django admin |

Add a module route to that app's `urls.py`; project-level prefixes are wired in `config/urls.py`. Views belong in the app's `views.py`. The `CORIDE` app currently supplies the shared landing-page template and kitty image used by the module placeholders.

## Module specifications

Each app's folder contains its module requirements and design notes:

- Users: [utilisateurs/01_user-management.md](utilisateurs/01_user-management.md)
- Vehicles: [vehicules/02_vehicle-management.md](vehicules/02_vehicle-management.md)
- Trips: [trajets/03_trip-management.md](trajets/03_trip-management.md)
- Reservations: [reservations/04_reservation-management.md](reservations/04_reservation-management.md)
- Communication and feedback: [communication/05_communication-feedback.md](communication/05_communication-feedback.md)

## Common Django commands

Run Django commands through `uv run` so they use the project's locked environment:

```powershell
# Check settings, installed apps, and URL configuration
uv run python manage.py check

# Create migration files after changing models
uv run python manage.py makemigrations

# Apply migrations to the local database
uv run python manage.py migrate

# Run tests for all apps, or one app
uv run python manage.py test
uv run python manage.py test trajets

# Open the Django interactive shell
uv run python manage.py shell

# Create an admin login
uv run python manage.py createsuperuser
```

Commit migration files along with the model changes that generated them. Do not edit an already shared migration; create a new migration instead.

To scaffold another app:

```powershell
uv run python manage.py startapp my_app
```

Then add its `AppConfig` to `INSTALLED_APPS` in `config/settings.py`, create `my_app/urls.py`, and include it under a prefix in `config/urls.py`.

## Repository workflow

The shared integration branch is `master`. The module branches are `utilisateurs`, `vehicules`, `trajets`, `reservations`, and `communication`. Work on your module branch rather than directly on `master`. `CORIDE` contains shared landing-page/UI elements, so coordinate changes to it with the other developers and integrate them through a pull request to `master`.

```powershell
# See your current branch and uncommitted files
git status

# Get the latest remote branch list
git fetch origin

# Start work on your module branch
git switch trajets
git pull

# After making and checking changes
uv run python manage.py check
uv run python manage.py test trajets
git add trajets/
git commit -m "Describe the change"
git push
```

Replace `trajets` with your module branch. Stage only the files for your change (for example, `git add trajets/`) rather than using `git add .`, which can include unrelated work. Before switching branches, commit or otherwise safely preserve your changes. Keep commits focused, push to your module branch, and open a pull request to `master` so module work can be reviewed and integrated. If a change affects shared settings, URLs, or the shared `CORIDE` UI, coordinate with the other module developers.
