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

## Android testing and deployment

The `mobile` folder is the native Kotlin Android Studio project. Open `mobile` directly in Android Studio. The APK is a WebView client; Django continues to run on the development computer, not on the phone.

### Django static files on Vercel

Shared assets such as `assets/kitty.png` are collected into `STATIC_ROOT` during Vercel's build and served from `STATIC_URL` by the Vercel CDN. Keep `STATIC_ROOT` configured in `config/settings.py`; Django templates should reference assets with the `{% static %}` template tag.

### Test on a phone over the same LAN

1. Connect the phone and development computer to the same trusted Wi-Fi/LAN.
2. From the repository root, start the Django server and its local-network announcement:

   ```powershell
   .\run-coride.ps1
   ```

   The script chooses the active private IPv4 address, sets `DJANGO_ALLOWED_HOSTS`, and runs `uv run manage.py corideserver`. It can also be called by absolute path from another working directory. The server advertises itself with mDNS; the app discovers that service instead of scanning IP addresses. Keep this command running while testing. If prompted, allow inbound TCP port 8000 and UDP port 5353 on the trusted private network.
3. Open `mobile` in Android Studio, select the `app` run configuration and your connected phone, then click **Run**. The app connects to the advertised server automatically; there is no URL field. While searching and connecting, it displays the repository's `coride-loader.html` as a local Android asset; Gradle packages the file from the repository root, and the loader WebView blocks network requests. The installed version appears below the loader. The loader, native status text, offline screen, and system bars follow Android's light/dark theme. The app WebView stays hidden until the server page is ready, so no browser controls or server address are shown. After connecting, the mobile toolbar's menu opens the Django routes (`/`, `/users/`, `/vehicles/`, `/trips/`, `/reservations/`, and `/coms/`) on that same server. For local testing, keep Django running with `.\run-coride.ps1`; no Vercel testing is needed. The hosted CoRide fallback remains available if no LAN Django server is found, and a branded offline screen with a retry button appears if both servers are unreachable. After connecting, the app stops discovery and does not poll Django in the background.

HTTP is unencrypted and enabled only in debug builds. Use it only on a trusted network and never send real credentials or sensitive data.

### Android CI/CD

- Every push to `mobile`, pull request targeting `mobile`, and manual **Android debug APK** workflow run builds the Android project and uploads the `coride-android-debug` APK artifact.
- Every push to `mobile` builds an APK; with the persistent signing secret configured, it also publishes a stable GitHub Release. The first automatic release starts at `v0.1.1`; each later release increments the patch version from the latest `vMAJOR.MINOR.PATCH` tag.
- The APK's Android `versionName` matches the release version, and `versionCode` is the GitHub Actions run number plus 1000.
- In the foreground, the app checks GitHub's latest stable release every two minutes. It downloads a newer APK only after verifying the release URL, package, version, SHA-256 digest when provided, and signing certificate. Android still requires the user to allow installs from CoRide and confirm each update in the system installer.
- For installable releases, add the base64-encoded current debug keystore as the repository Actions secret `ANDROID_DEBUG_KEYSTORE_BASE64`. The key must match the installed app's signer; do not commit the keystore. If the secret is missing, CI builds the APK artifact but skips publishing a release. This prevents releases signed with a different key from breaking in-app updates.
- Leave the optional `server_url` workflow input empty for LAN discovery. For a hosted HTTPS test server, set the `MOBILE_SERVER_URL` Actions variable or enter the origin as the workflow input; the app then opens that server directly.
- Pushing a version tag such as `v0.1.0` builds the APK and publishes a stable release under that version tag. The APK is debug-signed and not a Play Store release. This workflow does not deploy Django.

For local builds, install Android Studio and the Android SDK, open `mobile` as the project, and run the `app` configuration on a connected device. The optional `-PmobileServerUrl=<origin>` Gradle property or `MOBILE_SERVER_URL` environment variable bypasses LAN discovery for a hosted server.

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
