# Developer guide

This repository is a single Django project split into module apps. Run commands from the repository root in PowerShell.

## Setup and run

Install the pinned dependencies and create/update the project environment:

```powershell
uv sync
```

Start the development server:

```powershell
uv run manage.py runserver
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

Add a module route to that app's `urls.py`; project-level prefixes are wired in `config/urls.py`. Views belong in the app's `views.py`. The `CORIDE` app currently supplies the shared landing-page template, and shared static assets such as the kitty image live in `assets/`.

## Module specifications

The apps are currently scaffolds with shared placeholder pages; the planned features below have not yet been implemented. Each app's folder contains its module requirements, current-state log, and captured placeholder preview:

| App | Current state | Specification and screenshot |
|---|---|---|
| CoRide | [AI.log](CORIDE/AI.log) | [Screenshot](CORIDE/screenshots/home.png) |
| Users | [AI.log](utilisateurs/AI.log) | [Specification and screenshot](utilisateurs/01_user-management.md) |
| Vehicles | [AI.log](vehicules/AI.log) | [Specification and screenshot](vehicules/02_vehicle-management.md) |
| Trips | [AI.log](trajets/AI.log) | [Specification and screenshot](trajets/03_trip-management.md) |
| Reservations | [AI.log](reservations/AI.log) | [Specification and screenshot](reservations/04_reservation-management.md) |
| Communication and feedback | [AI.log](communication/AI.log) | [Specification and screenshot](communication/05_communication-feedback.md) |

## Common Django commands

Run Django commands through `uv run` so they use the project's locked environment:

```powershell
# Check settings, installed apps, and URL configuration
uv run manage.py check

# Create migration files after changing models
uv run manage.py makemigrations

# Apply migrations to the local database
uv run manage.py migrate

# Run tests for all apps, or one app
uv run manage.py test
uv run manage.py test trajets

# Open the Django interactive shell
uv run manage.py shell

# Create an admin login
uv run manage.py createsuperuser
```

Commit migration files along with the model changes that generated them. Do not edit an already shared migration; create a new migration instead.

To scaffold another app:

```powershell
uv run manage.py startapp my_app
```

Then add its `AppConfig` to `INSTALLED_APPS` in `config/settings.py`, create `my_app/urls.py`, and include it under a prefix in `config/urls.py`.

## Android test package

The `mobile` branch contains a Capacitor Android wrapper. It loads the Django app from a separate HTTPS test-server origin; it does not bundle or run Django inside Android. The Android package is a debug APK for testing, not a Play Store release.

Set the repository Actions variable `MOBILE_SERVER_URL` to the HTTPS origin of the deployed test server (for example, `https://coride-staging.example.com`). Use the origin only: do not include a path, query, or fragment. Until this variable is set, the workflow reports that the APK build was skipped. Once configured, `.github/workflows/android-debug.yml` builds on pushes and pull requests to `mobile` and uploads `coride-android-debug` as an artifact.

To build locally in PowerShell, use the same test-server URL and install Java 21 and the Android SDK first:

```powershell
cd mobile
$env:MOBILE_SERVER_URL = "https://coride-staging.example.com"
npm ci
npx cap add android
npm run sync:android
Push-Location android
.\gradlew.bat assembleDebug
Pop-Location
```

The APK is written to `mobile/android/app/build/outputs/apk/debug/app-debug.apk`. The generated `android/` directory is build output; the workflow creates it for each run.

## Repository workflow

The shared integration branch is `master`. The module branches are `utilisateurs`, `vehicules`, `trajets`, `reservations`, and `communication`; Android packaging is maintained on `mobile`. Work on your assigned branch rather than directly on `master`. `CORIDE` contains shared landing-page/UI elements, so coordinate changes to it with the other developers and integrate them through a pull request to `master`.

```powershell
# See your current branch and uncommitted files
git status

# Get the latest remote branch list
git fetch origin

# Start work on your module branch
git switch trajets
git pull

# After making and checking changes
uv run manage.py check
uv run manage.py test trajets
git add trajets/
git commit -m "Describe the change"
git push
```

Replace `trajets` with your module branch. Stage only the files for your change (for example, `git add trajets/`) rather than using `git add .`, which can include unrelated work. Before switching branches, commit or otherwise safely preserve your changes. Keep commits focused, push to your module branch, and open a pull request to `master` so module work can be reviewed and integrated. If a change affects shared settings, URLs, or the shared `CORIDE` UI, coordinate with the other module developers.
