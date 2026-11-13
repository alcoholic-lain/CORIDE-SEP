# Module 01 · User management

> **Owner:** Alaaeddine Guouider · **Django app:** `users` · **Branch:** `module-1-users`
> **Depends on:** nothing (foundation module) · **Used by:** modules 2, 3, 4, 5
> **Sprints:** S1 structure and CRUD → S2 business rules → S3 AI

## Team

| Member | Own module | Role for this module |
|---|---|---|
| Alaaeddine Guouider | 01 · User management | **Module owner**: builds and presents this module |
| Abdallah Salhi | 02 · Vehicle management | Hand-off partner: shares an interface with this module (see section 6) |
| Wasim Snoussi | 03 · Trip management | Hand-off partner: shares an interface with this module (see section 6) |
| Selim Aschi | 04 · Reservation management | Hand-off partner: shares an interface with this module (see section 6) |
| Ahmed Ridha Lazhari | 05 · Communication & feedback | Hand-off partner: shares an interface with this module (see section 6) |
| Our professor | — | Product Owner: sets the value of each story and accepts work at the sprint review |
| Rotates each sprint | — | Scrum Master: facilitates, removes blockers, protects the sprint goal |

---

**Reading guide.** Rows marked **†** come from the official product backlog (slide 37). The other rows are derived from the module slides; their *Value* and *Complexity* are **proposed** and must be confirmed with the Product Owner at sprint planning. Priority = Value ÷ Complexity.

---

## 1. Scope

| | |
|---|---|
| **Entities** | `User` (abstract in the UML), `Passenger`, `Driver`, `Administrator`, enum `AccountStatus` |
| **CRUD** | Sign up, log in, log out · view, edit and delete a profile · user types: passenger, driver, administrator · admin: list, search, suspend, delete users |
| **Advanced features** | E-mail verification link · password reset by e-mail · lockout after 5 failed logins · user statistics by type and month |
| **AI features** | Face verification · profile photo moderation · fake account detection · help chatbot |
| **Key rule** | Users must be at least 18, the selfie must match the ID card or passport, and **the AI never suspends an account by itself** |

---

## 2. Product backlog

| ID | User story | Value | Complexity | Priority | MoSCoW | Sprint |
|---|---|---|---|---|---|---|
| 1.1 † | As a visitor, I want to sign up with my ID and a selfie, so that my account is verified | 100 | 5 | 20.0 | Must | S1 form → S3 AI |
| 1.2 | As a visitor, I want to confirm my e-mail, so that my account becomes active | 80 | 2 | 40.0 | Must | S1 |
| 1.3 | As a user, I want to log in and out safely, so that nobody can use my account | 90 | 3 | 30.0 | Must | S1 → S2 |
| 1.4 | As a user, I want to view and edit my profile, so that my information stays correct | 60 | 3 | 20.0 | Must | S1 |
| 1.5 | As a user, I want to reset my password by e-mail, so that I can recover my account | 50 | 3 | 16.7 | Should | S2 |
| 1.6 | As a user, I want to delete my account, so that my data is removed when I leave | 30 | 2 | 15.0 | Could | S1 → S2 |
| 1.7 | As an administrator, I want to list, search, suspend and delete users, so that I keep the platform safe | 80 | 5 | 16.0 | Must | S1 → S2 |
| 1.8 | As a user, I want my profile photo to be checked, so that only suitable photos are shown | 40 | 5 | 8.0 | Could | S3 |
| 1.9 | As an administrator, I want a risk score on accounts, so that I can review suspicious ones | 50 | 8 | 6.3 | Should | S3 |
| 1.10 | As a passenger, I want to ask a virtual assistant, so that I get help without waiting | 20 | 8 | 2.5 | Could | S3 |
| 1.11 | As an administrator, I want user statistics and exports, so that I can follow the growth of CoRide | 40 | 3 | 13.3 | Should | S2 |

---

## 3. Specifications

### 3.1 Data model

The UML shows `User` as abstract with `Passenger` and `Administrator` inheriting from it and `Driver` inheriting from `Passenger`. In Django we keep **one concrete `User` table** (simple authentication, one login for all) and expose the three roles as **proxy models**. A driver is a passenger whose `user_type` was promoted.

```python
# users/models.py
class AccountStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"

class UserType(models.TextChoices):
    PASSENGER = "PASSENGER"
    DRIVER = "DRIVER"            # a passenger with an accepted vehicle
    ADMINISTRATOR = "ADMINISTRATOR"

class User(AbstractUser):
    # username unused, e-mail is the login
    email = models.EmailField(unique=True)
    birth_date = models.DateField()
    phone = models.CharField(max_length=20)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True)
    status = models.CharField(max_length=12, choices=AccountStatus.choices,
                              default=AccountStatus.UNVERIFIED)
    user_type = models.CharField(max_length=15, choices=UserType.choices,
                                 default=UserType.PASSENGER)
    identity_verified = models.BooleanField(default=False)
    risk_score = models.FloatField(default=0.0)           # 0.0 – 1.0, AI output
    registration_date = models.DateTimeField(auto_now_add=True)
    # Passenger / Driver attributes (kept on the same table)
    no_show_count = models.PositiveIntegerField(default=0)
    booking_blocked_until = models.DateTimeField(null=True, blank=True)
    became_driver_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "birth_date", "phone"]

class Passenger(User):      class Meta: proxy = True
class Driver(User):         class Meta: proxy = True
class Administrator(User):  class Meta: proxy = True
```

Notes
- `AUTH_USER_MODEL = "users.User"` must be set **before the first migration** of the whole project. This is part of the shared database design in week 1 of Sprint 1.
- Passwords are hashed by Django (`passwordHash` in the UML = Django's `password` field).
- `selfie` and `id_photo` are **never stored** as model fields: they are processed in memory and deleted right after verification.
- `risk_score` is written only by the AI service; `status` is written only by an administrator action or the e-mail confirmation.

### 3.2 Business rules

| Rule | Value | Enforced in |
|---|---|---|
| Minimum age | 18 years at sign-up and on profile edit | `SignUpForm.clean_birth_date`, `ProfileForm` |
| Unique e-mail | one account per e-mail | DB unique + form validation |
| Selfie must match ID card or passport | AI face comparison | `ai.verify_identity()` |
| Confirmation link validity | 24 hours | `TimestampSigner(max_age=86400)` |
| Failed logins | 5 failures lock the account for 15 minutes | `django-axes` (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=15 min`) |
| Unverified account | cannot log in until e-mail is confirmed | auth backend |
| Suspended account | cannot log in | auth backend |
| AI never suspends | AI only writes `risk_score`; suspension is an admin action | `suspend_user` view is admin-only |
| Admin cannot suspend or delete themselves *(proposed)* | | `AdminUserActionView` |
| Privacy | phone number shown only after a booking is accepted | `users.templatetags.privacy` (used by module 4) |

### 3.3 Screens and URLs (`app_name = "users"`)

| URL | View | Who | Story |
|---|---|---|---|
| `/` | `HomeView` | Visitor, all | — |
| `/signup/` | `SignUpView` | Visitor | 1.1 |
| `/verify-email/<token>/` | `VerifyEmailView` | Visitor | 1.2 |
| `/login/` · `/logout/` | `LoginView`, `LogoutView` | All | 1.3 |
| `/password-reset/` + `done/confirm/complete` | Django built-in views | Visitor | 1.5 |
| `/profile/` | `ProfileDetailView` | Logged in | 1.4 |
| `/profile/edit/` | `ProfileUpdateView` | Logged in | 1.4, 1.8 |
| `/profile/delete/` | `AccountDeleteView` | Logged in | 1.6 |
| `/assistant/` | `AssistantView` (chat widget, HTMX/fetch) | Passenger | 1.10 |
| `/manage/users/` | `UserListView` (search, filter, pagination) | Admin | 1.7 |
| `/manage/users/<id>/suspend/` · `/delete/` | `SuspendUserView`, `DeleteUserView` | Admin | 1.7 |
| `/manage/users/suspicious/` | `SuspiciousAccountsView` | Admin | 1.9 |
| `/manage/users/stats/` + `export/<fmt>/` | `UserStatsView`, `UserExportView` | Admin | 1.11 |

### 3.4 Permissions

A reusable mixin used by **every module**:

```python
class UserTypeRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_types = []           # e.g. ["ADMINISTRATOR"]
    def test_func(self):
        return self.request.user.user_type in self.allowed_types
```

Anonymous user → redirect to login. Wrong user type → HTTP 403. This satisfies the non-functional need *"access checks by user type on every page"*.

### 3.5 Advanced features

- **E-mail verification:** signed token, 24 h, "resend link" button.
- **Password reset:** Django's `PasswordResetView` with a custom e-mail template; neutral message for unknown e-mails.
- **Lockout:** after 5 failed logins the account is blocked 15 minutes, with a clear message.
- **Statistics:** new users per month, split by passenger / driver / administrator (chart + table), exported as PDF, CSV and Excel (slide: "PDF reports, CSV and Excel export").
- **Lists:** pagination (10 per page), search by name or e-mail, filter by type and status.

### 3.6 AI features (Sprint 3, package `ai/`)

| Function | Input → output | Notes |
|---|---|---|
| `verify_identity(selfie, id_photo) -> bool` | two images → faces match or not | open-source face embedding model (e.g. DeepFace / `face_recognition`); images deleted right after |
| `check_photo(photo) -> bool` | profile photo → accepted or rejected | must contain exactly one face; reject inappropriate content |
| `compute_risk_score(user) -> float` | account activity → 0–1 | features: age of account, cancellations, no-shows, reports, duplicate phone/IP; start rule-based, then a scikit-learn model |
| `assistant_answer(question) -> str` | question → answer grounded in the CoRide rules | FAQ-based; says "I can't help with that" when out of scope |

Every AI call is wrapped so that **if the model fails, the application still works** (identity check → manual admin review; photo check → photo accepted as "pending review").

---

## 4. Acceptance criteria

> Format: Given / When / Then. Every story has a success case and at least one failure case.

**1.1 Sign up with ID and selfie**
- **Success** · *Given* Sami is 25, uses an unused e-mail and sends a clear selfie and ID photo of the same face · *When* he submits the form · *Then* an account is created as `UNVERIFIED`, the selfie and ID photo are deleted, and a confirmation e-mail is sent.
- **Failure A** · *Given* the birth date makes the visitor 17, or the e-mail already exists · *When* he submits · *Then* an error message is shown and no account is created.
- **Failure B** · *Given* the selfie and the ID photo are of different people · *When* he submits · *Then* "Verification failed, try again" is shown and no account is created.

**1.2 Confirm the e-mail**
- **Success** · *Given* Sami is `UNVERIFIED` and clicks the link after 2 hours · *When* the link is opened · *Then* his status becomes `ACTIVE` and the welcome page is shown.
- **Failure** · *Given* the link is 25 hours old · *When* it is opened · *Then* "Link expired" is shown with a "Send a new link" button, and the status stays `UNVERIFIED`.

**1.3 Log in and out**
- **Success** · *Given* Sami is `ACTIVE` · *When* he enters the right e-mail and password · *Then* he is logged in and sees the home page.
- **Failure A** · *Given* Sami typed a wrong password 4 times · *When* he fails a 5th time · *Then* the account is locked for 15 minutes, even the correct password is refused.
- **Failure B** · *Given* Sami is `UNVERIFIED` or `SUSPENDED` · *When* he logs in · *Then* a message explains why access is refused.

**1.4 View and edit the profile**
- **Success** · *Given* Sami is logged in · *When* he changes his phone number · *Then* the new number is saved and displayed.
- **Failure** · *Given* Sami edits his birth date so that he would be under 18, or enters another user's e-mail · *When* he saves · *Then* the change is rejected with an error message.

**1.5 Reset the password**
- **Success** · *Given* a registered e-mail · *When* the user asks for a reset · *Then* an e-mail with a time-limited link is sent and the new password works after the reset.
- **Failure** · *Given* an unknown e-mail · *When* the user asks for a reset · *Then* the same neutral message is shown and no e-mail is sent (no account enumeration).

**1.6 Delete my account**
- **Success** · *Given* Sami has no upcoming trip or accepted booking · *When* he confirms with his password · *Then* his personal data is deleted or anonymised and he is logged out.
- **Failure** · *Given* Sami has an accepted booking next week · *When* he tries to delete his account · *Then* "Cancel your upcoming trips first" is shown and nothing is deleted.

**1.7 Admin manages users**
- **Success** · *Given* an administrator opens the user list · *When* he suspends a user · *Then* the status becomes `SUSPENDED`, the user can no longer log in and receives an e-mail.
- **Failure** · *Given* a passenger types `/manage/users/` · *When* the page loads · *Then* HTTP 403 is returned. An administrator also cannot suspend himself.

**1.8 Profile photo check**
- **Success** · *Given* a clear photo with one face · *When* it is uploaded · *Then* it is accepted and shown on the profile.
- **Failure** · *Given* a photo with no face or inappropriate content · *When* it is uploaded · *Then* "This photo cannot be used" is shown and the previous photo is kept.

**1.9 Risk score**
- **Success** · *Given* an account with suspicious activity · *When* the nightly job runs · *Then* its `risk_score` rises and it appears at the top of "Suspicious accounts" for the admin.
- **Failure (guard)** · *Given* an account has a risk score of 0.98 · *When* nobody acts · *Then* its status stays `ACTIVE`: only an administrator can suspend it.

**1.10 Virtual assistant**
- **Success** · *Given* a passenger asks "How do I cancel a booking?" · *When* the assistant answers · *Then* the answer mentions the 2-hour rule.
- **Failure** · *Given* a question unrelated to CoRide · *When* the assistant answers · *Then* it says it cannot help and points to the FAQ.

**1.11 Statistics and exports**
- **Success** · *Given* an administrator selects the year 2026 · *When* he opens the statistics page · *Then* users per type and month are shown and can be downloaded as PDF, CSV and Excel.
- **Failure** · *Given* a passenger calls the export URL · *When* the request arrives · *Then* HTTP 403 is returned.

---

## 5. Tasks by sprint

Each task becomes a **Trello card** with one owner. Branch: `module-1-users`, merged to `main` by reviewed pull request.

### Sprint 1 · Structure and CRUD
- [ ] `M1-S1-01` Create Django project, apps, GitHub repo, Trello board *(team)*
- [ ] `M1-S1-02` **Shared database design with the whole team (week 1)**: agree `AUTH_USER_MODEL`, foreign keys, enums *(team)*
- [ ] `M1-S1-03` Custom `User` model, proxy models, enums, migrations · *1.1*
- [ ] `M1-S1-04` `SignUpForm` with age ≥ 18 and unique e-mail checks, selfie + ID upload fields (no AI yet) · *1.1*
- [ ] `M1-S1-05` Confirmation e-mail with signed 24 h token and `VerifyEmailView` · *1.2*
- [ ] `M1-S1-06` Login, logout, "unverified / suspended" messages · *1.3*
- [ ] `M1-S1-07` Profile detail and edit views and templates · *1.4*
- [ ] `M1-S1-08` Delete-account view with password confirmation · *1.6*
- [ ] `M1-S1-09` `UserTypeRequiredMixin` and tests for 403 on every protected view · *all modules*
- [ ] `M1-S1-10` Admin list of users (list, detail, suspend, delete) · *1.7*
- [ ] `M1-S1-11` Base template, navigation by user type, home page · *Visitor*

### Sprint 2 · Business features
- [ ] `M1-S2-01` Integrate `django-axes`: 5 failures, 15 minute lockout, user message · *1.3*
- [ ] `M1-S2-02` Password reset flow with custom e-mail templates · *1.5*
- [ ] `M1-S2-03` Block account deletion when upcoming trips or bookings exist; anonymise data · *1.6*
- [ ] `M1-S2-04` Admin user list: search, filters by type and status, pagination · *1.7*
- [ ] `M1-S2-05` User statistics per type and month (chart) · *1.11*
- [ ] `M1-S2-06` Export statistics to PDF, CSV and Excel · *1.11*
- [ ] `M1-S2-07` Privacy template tag: show phone only for accepted bookings (shared with module 4) · *NFR*
- [ ] `M1-S2-08` Unit and integration tests for business rules · *1.1–1.7*

### Sprint 3 · Artificial intelligence
- [ ] `M1-S3-01` `ai.verify_identity()` + integration in sign-up, delete images after use · *1.1*
- [ ] `M1-S3-02` Fallback to manual admin review when the model fails · *1.1*
- [ ] `M1-S3-03` `ai.check_photo()` on profile photo change · *1.8*
- [ ] `M1-S3-04` `ai.compute_risk_score()` (rules first, then ML) and nightly management command · *1.9*
- [ ] `M1-S3-05` "Suspicious accounts" admin page, **no automatic suspension** · *1.9*
- [ ] `M1-S3-06` Help chatbot widget and `ai.assistant_answer()` · *1.10*
- [ ] `M1-S3-07` Bug fixes, final tests, demo of sign-up with identity verification *(team)*

---

## 6. Interfaces with the other modules

| Other module | What it takes from here | What it gives back |
|---|---|---|
| 2 · Vehicles | `User` as vehicle owner, `UserTypeRequiredMixin` | sets `user_type = DRIVER` and `became_driver_at` when a vehicle is accepted |
| 3 · Trips | `Driver` as publisher | — |
| 4 · Reservations | `Passenger`, `no_show_count`, `booking_blocked_until`, privacy tag | updates `no_show_count` and `booking_blocked_until` |
| 5 · Communication | `User` as reviewer and target | average rating displayed on the profile |

## 7. Definition of done

- Code reviewed in a pull request and merged to `main`.
- Unit tests pass (models, forms, views, permissions); every protected URL tested for anonymous, wrong type and right type.
- All user-facing messages written in English (i18n-ready).
- Works on mobile screen sizes (mobile first).
- Passwords hashed, CSRF active, no secret in the repository.
- Trello card moved to *Done* and shown at the sprint review.

## Current scaffold preview

This screenshot shows the current shared placeholder page, not the implemented user-management features.

![Current users-module placeholder](screenshots/users.png)
