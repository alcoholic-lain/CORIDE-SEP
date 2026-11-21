# Developer guide

This repository is a Django project split into module apps. Run commands from the repository root in PowerShell.

## Setup and run

Install the project's pinned dependencies and create or update its environment:

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
| Kizuna landing page | `/` | `kizuna` |
| M4 | `/m4/` | `m4` |
| M5 | `/m5/` | `m5` |
| M3 | `/m3/` | `m3` |
| M2 | `/m2/` | `m2` |
| M1 | `/m1/` | `m1` |
| Django admin | `/admin/` | Django admin |

Add routes in each app's `urls.py`; project-level prefixes are wired in `config/urls.py`. Views belong in the app's `views.py`. Shared landing-page templates are in `kizuna/`, and shared static assets are in `assets/`.

## Module documentation

All module pages are scaffolds for the Nabd subject (see `k-mod/00-index.md`). Each app has a current-state log, specification and screenshot:

| App | Current state | Specification | Screenshot |
|---|---|---|---|
| Kizuna | [AI.log](kizuna/AI.log) | — | [home](kizuna/screenshots/home.png) |
| M4 | [AI.log](m4/AI.log) | [requirements](m4/04_user-space-rewards.md) | [preview](m4/screenshots/users.png) |
| M5 | [AI.log](m5/AI.log) | [requirements](m5/05_steg-space.md) | [preview](m5/screenshots/vehicles.png) |
| M3 | [AI.log](m3/AI.log) | [requirements](m3/03_ai-anomalies.md) | [preview](m3/screenshots/trips.png) |
| M2 | [AI.log](m2/AI.log) | [requirements](m2/02_api-data.md) | [preview](m2/screenshots/reservations.png) |
| M1 | [AI.log](m1/AI.log) | [requirements](m1/01_adapter-simulator.md) | — |

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
uv run manage.py test m3

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

## Android testing and deployment

The `mobile` folder is the native Kotlin Android Studio project. Open `mobile` directly in Android Studio. The APK is a WebView client; Django continues to run on the development computer, not on the phone.

### Django static files on Vercel

Shared assets such as `assets/kizuna/logo.svg` are collected into `STATIC_ROOT` during Vercel's build and served from `STATIC_URL` by the Vercel CDN. Keep `STATIC_ROOT` configured in `config/settings.py`; Django templates should reference assets with the `{% static %}` template tag.

### Turso database on Vercel

The app uses local SQLite unless `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are configured. In Vercel, add both as environment variables for every deployment environment you use; set the URL to the database's `libsql://` endpoint and the token to its auth token. Also configure `DJANGO_SECRET_KEY` with a newly generated secret. Rotate any database token that has been shared in a screenshot or chat. Do not put secrets in URLs or commit them to the repository. Vercel deployments fail clearly if these settings are missing instead of silently creating an ephemeral SQLite database.

For local use of the shared Turso database, pull the variables into `.env.local` with the Vercel CLI. `manage.py` loads that file for local commands (but not test runs, to avoid using a shared database), and `.env.local` is ignored by Git. Run `uv run manage.py migrate` after configuring it to create or update the Turso schema. Without those variables, local development continues using `db.sqlite3`.

### Test on a phone over the same LAN

1. Connect the phone and development computer to the same trusted Wi-Fi/LAN.
2. From the repository root, start the Django server and its local-network announcement:

   ```powershell
   .\run-kizuna.ps1
   ```

   The script chooses the active private IPv4 address, sets `DJANGO_ALLOWED_HOSTS`, and runs `uv run manage.py kizunaserver`. It can also be called by absolute path from another working directory. The server advertises itself with mDNS; the app discovers that service instead of scanning IP addresses. Keep this command running while testing. If prompted, allow inbound TCP port 8000 and UDP port 5353 on the trusted private network.
3. Open `mobile` in Android Studio, select the `app` run configuration and your connected phone, then click **Run**. The app connects to the advertised server automatically; there is no URL field. While searching and connecting, it displays the repository's `kizuna-loader.html` as a local Android asset; Gradle packages the file from the repository root, and the loader WebView blocks network requests. The installed version appears below the loader. The loader, native status text, offline screen, and system bars follow Android's light/dark theme. After each Django page loads, the app injects mobile-only CSS through JavaScript to match the page background and text to Android's current theme; the WebView stays hidden until the styling is applied. No browser controls or server address are shown. The mobile toolbar's menu opens the Django routes (`/`, `/m4/`, `/m5/`, `/m3/`, `/m2/`, and `/m1/`) on that same server. For local testing, keep Django running with `.\run-kizuna.ps1`; no Vercel testing is needed. The hosted Kizuna fallback remains available if no LAN Django server is found, and a branded offline screen with a retry button appears if both servers are unreachable. After connecting, the app stops discovery and does not poll Django in the background.

HTTP is unencrypted and enabled only in debug builds. Use it only on a trusted network and never send real credentials or sensitive data.

### Android CI/CD

- Pushes and pull requests targeting `master`, `m1`, or `mobile`, plus manual **Android debug APK** workflow runs, build the Android project and upload the `kizuna-android-debug` APK artifact.
- Pushes to `mobile` build an APK and, with the persistent signing secret configured, publish a stable GitHub Release. The first automatic release starts at `v0.1.1`; each later release increments the patch version from the latest `vMAJOR.MINOR.PATCH` tag. Version tags also publish releases.
- The APK's Android `versionName` matches the release version, and `versionCode` is the GitHub Actions run number plus 1000.
- In the foreground, the app checks GitHub's latest stable release every two minutes. When it finds a newer version, it asks once for that version whether to open the GitHub release page. **Open GitHub** opens the page in the user's browser; **Not now** dismisses the prompt. The **View update** button remains available. The app does not download or install APKs and does not request package-install permission. Android or Play Protect may still show its own security checks.
- Add the base64-encoded current debug keystore as the repository Actions secret `ANDROID_DEBUG_KEYSTORE_BASE64` so releases remain signed with the same key as the installed app; do not commit the keystore. If the secret is missing, CI builds the APK artifact but skips publishing a release.
- Leave the optional `server_url` workflow input empty for LAN discovery. For a hosted HTTPS test server, set the `MOBILE_SERVER_URL` Actions variable or enter the origin as the workflow input; the app then opens that server directly.
- Pushing a version tag such as `v0.1.0` builds the APK and publishes a stable release under that version tag. The APK is debug-signed and not a Play Store release. This workflow does not deploy Django.

For local builds, install Android Studio and the Android SDK, open `mobile` as the project, and run the `app` configuration on a connected device. The optional `-PmobileServerUrl=<origin>` Gradle property or `MOBILE_SERVER_URL` environment variable bypasses LAN discovery for a hosted server.

## Repository workflow

The shared integration branch is `master`. Module branches are `m4`, `m5`, `m3`, `m2` and `m1`; Android packaging is maintained on `mobile`. Work on your assigned branch and open a pull request to `master`. Coordinate changes to shared settings, URLs or the `kizuna` UI.

```powershell
git status
git fetch origin
git switch m3
git pull

uv run manage.py check
uv run manage.py test m3
git add m3/
git commit -m "Describe the change"
git push
```

Replace `m3` with your module branch. Stage only files related to your change rather than using `git add .`, which can include unrelated work.
