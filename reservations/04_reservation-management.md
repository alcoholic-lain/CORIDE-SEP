# Module 04 · Reservation management

> **Owner:** Selim Aschi · **Django app:** `reservations` · **Branch:** `module-4-reservations`
> **Depends on:** module 1 (`Passenger`), module 3 (`Trip`) · **Used by:** module 5 (chat opens on accepted booking)
> **Sprints:** S1 structure and CRUD → S2 business rules (QR, e-mails, no-show) → S3 AI (recommendations)

## Team

| Member | Own module | Role for this module |
|---|---|---|
| Alaaeddine Guouider | 01 · User management | Hand-off partner: shares an interface with this module (see section 6) |
| Abdallah Salhi | 02 · Vehicle management | Team member: reviews pull requests and joins the sprint events |
| Wasim Snoussi | 03 · Trip management | Hand-off partner: shares an interface with this module (see section 6) |
| Selim Aschi | 04 · Reservation management | **Module owner**: builds and presents this module |
| Ahmed Ridha Lazhari | 05 · Communication & feedback | Hand-off partner: shares an interface with this module (see section 6) |
| Our professor | — | Product Owner: sets the value of each story and accepts work at the sprint review |
| Rotates each sprint | — | Scrum Master: facilitates, removes blockers, protects the sprint goal |

---

**Reading guide.** Rows marked **†** come from the official product backlog (slide 37). The other rows are derived from the module slides; their *Value* and *Complexity* are **proposed** and must be confirmed with the Product Owner. Priority = Value ÷ Complexity.

---

## 1. Scope

| | |
|---|---|
| **Entities** | `Reservation`, enum `ReservationStatus` (8 statuses) |
| **CRUD** | Book one or more seats · driver accepts or refuses · view and cancel reservations · admin: list all reservations |
| **Advanced features** | QR code ticket scanned at pickup · e-mail confirmations · no-show tracking and penalties · "Recommended for you" trips |
| **AI feature** | Trip recommendations based on each passenger's usual routes, days and times |
| **Key rule** | Cancellation is allowed **up to 2 hours before departure**; **3 no-shows in 30 days** block booking for **7 days** |

---

## 2. Product backlog

| ID | User story | Value | Complexity | Priority | MoSCoW | Sprint |
|---|---|---|---|---|---|---|
| 4.1 † | As a passenger, I want to book a seat, so that I travel for less | 100 | 3 | 33.3 | Must | S1 |
| 4.2 | As a driver, I want to accept or refuse a booking request, so that I choose who travels with me | 90 | 3 | 30.0 | Must | S1 → S2 |
| 4.3 | As a passenger, I want to view and cancel my bookings, so that I stay in control of my plans | 70 | 3 | 23.3 | Must | S1 → S2 |
| 4.4 | As a passenger, I want a QR ticket once my booking is accepted, so that I can prove my seat | 60 | 5 | 12.0 | Should | S2 |
| 4.5 | As a driver, I want to scan the QR ticket at pickup, so that I know who is on board | 60 | 5 | 12.0 | Should | S2 |
| 4.6 | As a driver, I want to mark a no-show, and the platform to apply penalties, so that absent passengers are discouraged | 40 | 5 | 8.0 | Could | S2 |
| 4.7 | As a passenger or driver, I want e-mail confirmations, so that I never miss a decision | 40 | 3 | 13.3 | Should | S2 |
| 4.8 | As an administrator, I want to list all reservations, so that I can follow bookings and solve problems | 40 | 2 | 20.0 | Must | S1 → S2 |
| 4.9 | As a passenger, I want recommended trips, so that I find my usual rides without searching | 40 | 8 | 5.0 | Could | S3 |
| 4.10 | As an administrator, I want reservation reports and exports, so that I can follow activity | 40 | 3 | 13.3 | Should | S2 |

---

## 3. Specifications

### 3.1 Data model

```python
# reservations/models.py
class ReservationStatus(models.TextChoices):
    PENDING = "PENDING"        # waiting for the driver
    ACCEPTED = "ACCEPTED"      # QR ticket generated, chat opened
    REFUSED = "REFUSED"
    EXPIRED = "EXPIRED"        # not answered before departure (proposed rule)
    CANCELLED = "CANCELLED"    # by the passenger, or by a cancelled trip
    BOARDED = "BOARDED"        # QR scanned at pickup
    COMPLETED = "COMPLETED"    # trip finished, passenger was on board
    NO_SHOW = "NO_SHOW"

class Reservation(models.Model):
    passenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="reservations")      # Passenger 1 — 0..* books
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE,
                             related_name="reservations")           # Trip 1 — 0..* receives
    seats = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=ReservationStatus.choices,
                              default=ReservationStatus.PENDING)
    ticket_code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    reservation_date = models.DateTimeField(auto_now_add=True)
    status_changed_at = models.DateTimeField(auto_now=True)         # added: needed for the 30-day no-show window

    class Meta:
        indexes = [models.Index(fields=["passenger", "status"]),
                   models.Index(fields=["trip", "status"])]
```

UML methods → Django (put the logic in `reservations/services.py`, not in the views)

| UML method | Implementation |
|---|---|
| `book()` | `book_seats(passenger, trip, seats)` |
| `updateSeats()` | `trip.hold_seats()` / `release_seats()` from module 3 |
| `cancel()` | `cancel_reservation(reservation)` |
| `accept()`, `refuse()` | `accept_reservation()`, `refuse_reservation()` |
| `generateQR()` | `generate_ticket(reservation)` → `ticket_code` + PNG |
| `scanQR()` | `scan_ticket(trip, code)` |
| `markNoShow()` | `mark_no_show(reservation)` |
| `sendEmail()` | `reservations/emails.py` |

**Status flow**

```
PENDING ──accept──▶ ACCEPTED ──scan QR──▶ BOARDED ──trip ends──▶ COMPLETED
   │                   │  └──absent 15 min after departure──▶ NO_SHOW
   ├─refuse──▶ REFUSED └──cancel (≥ 2 h before)──▶ CANCELLED
   ├─cancel──▶ CANCELLED
   └─departure passed──▶ EXPIRED
```

Seats are **held at booking time** (status `PENDING`) and released on `REFUSED`, `CANCELLED` and `EXPIRED`.

### 3.2 Business rules

| Rule | Value | Enforced in |
|---|---|---|
| Seats requested | 1 ≤ seats ≤ `trip.remaining_seats` | `book_seats()` under `transaction.atomic()` + row lock |
| Trip must be bookable | status `OPEN`, departure in the future | `book_seats()` |
| Not your own trip | `trip.driver != passenger` | `book_seats()` |
| Passenger not blocked | `booking_blocked_until` empty or in the past | `book_seats()` |
| One active booking per trip *(proposed)* | a passenger cannot hold two active reservations on the same trip | `book_seats()` |
| Who decides | only the trip's driver accepts or refuses | `AcceptRefuseView` permission |
| Cancellation window | passenger may cancel up to **2 hours before departure** | `cancel_reservation()` |
| QR ticket | generated **when the driver accepts**, unique per reservation | `accept_reservation()` |
| Boarding | ticket must belong to a reservation of **this trip** in `ACCEPTED` status | `scan_ticket()` |
| No-show | the driver may mark it **15 minutes after departure** if the passenger is absent | `mark_no_show()` |
| Penalty | 3 `NO_SHOW` in the last 30 days → `booking_blocked_until = now + 7 days` | `apply_no_show_penalty()` |
| Phone privacy | the other person's phone is visible **only when the reservation is `ACCEPTED`** | privacy template tag (shared with module 1) |
| Booking effort | a booking takes **at most 3 clicks** from the search results | UX check in tests |

`passenger.no_show_count` (class diagram) is increased at each no-show; the 30-day rule is computed from the `NO_SHOW` reservations in the last 30 days (`status_changed_at`), so old no-shows stop counting.

### 3.3 Screens and URLs (`app_name = "reservations"`)

| URL | View | Who | Story |
|---|---|---|---|
| `/trips/<id>/book/` | `BookSeatView` (seat count, confirm) | Passenger | 4.1 |
| `/bookings/` | `MyBookingsView` (tabs: upcoming, past, cancelled) | Passenger | 4.3 |
| `/bookings/<id>/` | `BookingDetailView` (status, driver contact if accepted) | Passenger (owner) | 4.3 |
| `/bookings/<id>/cancel/` | `CancelBookingView` | Passenger (owner) | 4.3 |
| `/bookings/<id>/ticket/` | `TicketView` (QR code image) | Passenger (owner), only if `ACCEPTED` | 4.4 |
| `/driver/requests/` | `BookingRequestsView` (pending requests per trip) | Driver | 4.2 |
| `/driver/requests/<id>/accept/` · `/refuse/` | `AcceptRequestView`, `RefuseRequestView` | Driver (trip owner) | 4.2 |
| `/driver/trips/<id>/passengers/` | `PassengerListView` (accepted passengers, scan area) | Driver (trip owner) | 4.5 |
| `/driver/trips/<id>/scan/` | `ScanTicketView` (camera scan or code entry) | Driver (trip owner) | 4.5 |
| `/driver/reservations/<id>/no-show/` | `MarkNoShowView` | Driver (trip owner) | 4.6 |
| `/recommended/` | `RecommendedTripsView` (also a block on the home page) | Passenger | 4.9 |
| `/manage/reservations/` | `ReservationAdminListView` | Admin | 4.8 |
| `/manage/reservations/export/<fmt>/` | `ReservationExportView` | Admin | 4.10 |

### 3.4 Permissions

- Passenger: only **their own** reservations.
- Driver: only reservations of **trips they published**.
- Administrator: list, filter, export all; no booking on behalf of users.
- Every action view checks both the user type and ownership (HTTP 403 otherwise).

### 3.5 Advanced features

- **E-mails** (4.7): new request (to the driver), accepted with the QR ticket attached, refused, cancelled by passenger or by trip, no-show recorded. A failing SMTP server must **not** roll back the reservation: the error is logged and the e-mail retried.
- **QR ticket** (4.4, 4.5): `qrcode` library generates the image from `ticket_code` (random, unguessable). The driver scans with the browser camera (e.g. `html5-qrcode` in JS) or types the code as a fallback.
- **Request expiry** *(proposed)*: command `expire_pending_requests` sets `EXPIRED` for requests still `PENDING` at departure and releases the seats.
- **Completion:** when module 3 sets a trip to `COMPLETED`, `BOARDED` reservations become `COMPLETED` (this unlocks reviews in module 5).
- **No-show and penalties** (4.6): section 3.2, with a banner "Booking blocked until <date>".
- **Admin tools:** list with filters (status, trip, passenger, date), pagination, PDF, CSV, Excel.

### 3.6 AI feature · Trip recommendations (Sprint 3)

`ai.recommend_trips(passenger, limit=5) -> list[Trip]`

1. **Profile building:** from the passenger's past `ACCEPTED`, `BOARDED`, `COMPLETED` reservations take `(departure_city, arrival_city, weekday, hour)`.
2. **Scoring:** for each upcoming `OPEN` trip, score = weighted similarity of route (strongest), weekday and hour (e.g. frequency-based or a simple scikit-learn nearest-neighbour model). Exclude trips already booked or without seats.
3. **Cold start:** passengers with no history do not see "Recommended for you"; they see the soonest trips from their last searched city instead.
4. Results shown in a "Recommended for you" block (home page and `/recommended/`).

---

## 4. Acceptance criteria

**4.1 Book a seat** *(official, slide 38)*
- **Success** · *Given* Sami is verified and the trip Tunis → Sousse has 3 free seats · *When* Sami books 1 seat · *Then* the request is `PENDING`, the driver is notified, and free seats drop to 2.
- **Failure** · *Given* the trip Tunis → Sousse has no free seats · *When* Sami tries to book 1 seat · *Then* "No seats available" is shown and no reservation is created.
- **Failure (extra)** · *Given* Karim is the driver of the trip, or Sami is blocked until next week · *When* he tries to book · *Then* the booking is refused with the reason.

**4.2 Driver accepts or refuses**
- **Success** · *Given* Sami's request is `PENDING` · *When* Karim accepts · *Then* status becomes `ACCEPTED`, a QR ticket is generated, Sami receives the confirmation e-mail, and a chat opens.
- **Failure** · *Given* Amal is a driver of another trip · *When* she opens the accept URL of Karim's request · *Then* HTTP 403 is returned. A request still `PENDING` after departure becomes `EXPIRED` and its seats are released.
- **Refusal** · *Given* a `PENDING` request · *When* Karim refuses · *Then* status becomes `REFUSED`, seats are released, and Sami receives a refusal e-mail.

**4.3 View and cancel bookings**
- **Success** · *Given* Sami's trip leaves in 3 hours · *When* he cancels · *Then* the status becomes `CANCELLED`, the seat returns to the trip, and the driver is notified.
- **Failure** · *Given* the trip leaves in 90 minutes · *When* Sami tries to cancel · *Then* "Cancellation is closed (2 hours before departure)" is shown and the booking stays.

**4.4 QR ticket**
- **Success** · *Given* the booking is `ACCEPTED` · *When* Sami opens "My bookings" · *Then* he can show the QR ticket.
- **Failure** · *Given* the booking is `PENDING` or `REFUSED`, or belongs to someone else · *When* the ticket URL is opened · *Then* no QR is shown (HTTP 404 or 403).

**4.5 Scan the QR ticket**
- **Success** · *Given* Sami is `ACCEPTED` on Karim's trip · *When* Karim scans the ticket at pickup · *Then* the status becomes `BOARDED` and "Passenger on board" is shown.
- **Failure** · *Given* a ticket from another trip, or one already scanned · *When* Karim scans it · *Then* "Invalid ticket" (or "Already on board") is shown and nothing changes.

**4.6 No-show and penalties**
- **Success** · *Given* Sami is `ACCEPTED` and absent 15 minutes after departure · *When* Karim marks a no-show · *Then* status becomes `NO_SHOW`, Sami's `no_show_count` increases, and he is notified.
- **Penalty** · *Given* Sami already has 2 no-shows in the last 30 days · *When* a third is recorded · *Then* he cannot book for 7 days and sees "Booking blocked until <date>".
- **Failure** · *Given* only 5 minutes have passed since departure · *When* Karim marks a no-show · *Then* it is refused.

**4.7 E-mail confirmations**
- **Success** · *Given* Karim accepts a request · *When* the action completes · *Then* Sami receives an e-mail with the trip details and the QR ticket.
- **Failure** · *Given* the mail server is down · *When* a request is accepted · *Then* the acceptance is kept, the error is logged, and the e-mail is retried.

**4.8 Admin lists all reservations**
- **Success** · *Given* an administrator on the reservation list · *When* he filters by `NO_SHOW` · *Then* only no-show reservations are shown, paginated.
- **Failure** · *Given* a passenger types `/manage/reservations/` · *When* the page loads · *Then* HTTP 403 is returned.

**4.9 Recommended trips**
- **Success** · *Given* Sami booked Tunis → Sousse on Monday mornings several times · *When* he opens the home page · *Then* next Monday's Tunis → Sousse trips appear under "Recommended for you".
- **Failure** · *Given* a new passenger with no booking history · *When* he opens the home page · *Then* no "Recommended for you" block is shown; the soonest trips are shown instead.

**4.10 Reports and exports**
- **Success** · *Given* an administrator picks a date range and "PDF" · *When* he exports · *Then* a PDF listing the reservations is downloaded.
- **Failure** · *Given* a driver calls the export URL · *When* the request arrives · *Then* HTTP 403 is returned.

---

## 5. Tasks by sprint

Branch: `module-4-reservations`. One Trello card per task, one owner.

### Sprint 1 · Structure and CRUD
- [ ] `M4-S1-01` **Shared database design (week 1):** `Reservation` ↔ `Passenger`, `Trip`, `Conversation` *(team)*
- [ ] `M4-S1-02` Model `Reservation`, `ReservationStatus`, indexes, migrations · *4.1*
- [ ] `M4-S1-03` `book_seats()` service with transaction and seat holding (uses module 3) · *4.1*
- [ ] `M4-S1-04` Book-seat view and form, "No seats available" message · *4.1*
- [ ] `M4-S1-05` My bookings list and detail · *4.3*
- [ ] `M4-S1-06` Driver requests page with accept and refuse actions · *4.2*
- [ ] `M4-S1-07` Cancel reservation (without the time rule yet) · *4.3*
- [ ] `M4-S1-08` Admin list of reservations · *4.8*
- [ ] `M4-S1-09` Permissions: passenger-owner, driver-trip-owner, admin · *all*

### Sprint 2 · Business features
- [ ] `M4-S2-01` Booking rules: own trip, blocked passenger, duplicate booking, bookable trip · *4.1*
- [ ] `M4-S2-02` 2-hour cancellation rule and seat release · *4.3*
- [ ] `M4-S2-03` QR generation on accept (`qrcode`) and ticket page · *4.4*
- [ ] `M4-S2-04` Driver passenger list and scan screen (camera + manual code) · *4.5*
- [ ] `M4-S2-05` `scan_ticket()` with invalid / already-used cases · *4.5*
- [ ] `M4-S2-06` Mark no-show (15 min rule), counter, 30-day window, 7-day block · *4.6*
- [ ] `M4-S2-07` Command `expire_pending_requests` · *4.2*
- [ ] `M4-S2-08` E-mail templates: request, accepted + QR, refused, cancelled, no-show; retry on failure · *4.7*
- [ ] `M4-S2-09` Trigger chat opening on acceptance (signal to module 5) and completion hook · *4.2*
- [ ] `M4-S2-10` Privacy tag: phone visible only when `ACCEPTED` · *NFR*
- [ ] `M4-S2-11` Admin filters, pagination, PDF, CSV, Excel exports · *4.8, 4.10*
- [ ] `M4-S2-12` Tests: concurrency on the last seat, all status transitions, penalties · *4.1–4.7*

### Sprint 3 · Artificial intelligence
- [ ] `M4-S3-01` Build the passenger profile from past reservations (route, weekday, hour) · *4.9*
- [ ] `M4-S3-02` `ai.recommend_trips()` scoring and tests with sample histories · *4.9*
- [ ] `M4-S3-03` "Recommended for you" block on the home page and `/recommended/` · *4.9*
- [ ] `M4-S3-04` Cold-start fallback for new passengers · *4.9*
- [ ] `M4-S3-05` Bug fixes, final tests, live demo of booking, acceptance and boarding *(team)*

---

## 6. Interfaces with the other modules

| Other module | What it takes from here | What it gives back |
|---|---|---|
| 1 · Users | `Passenger`, `Driver`, `no_show_count`, `booking_blocked_until` | updates these fields |
| 3 · Trips | `Trip`, `hold_seats()`, `release_seats()`, `departure_datetime` | trip cancellation cascades to reservations; `COMPLETED` trip completes boarded reservations |
| 5 · Communication | — | an `ACCEPTED` reservation opens one conversation; `COMPLETED` reservations allow reviews |

## 7. Definition of done

- Pull request reviewed and merged to `main`.
- Every transition in the status flow tested (allowed and forbidden).
- Concurrency test proves the last seat cannot be double-booked.
- Booking reachable in at most 3 clicks from the search results; works on mobile.
- E-mail failures never break a reservation.
- Trello card in *Done* and shown at the sprint review.
