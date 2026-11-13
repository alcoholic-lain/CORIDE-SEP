# Module 03 · Trip management

> **Owner:** Wasim Snoussi · **Django app:** `trips` · **Branch:** `module-3-trips`
> **Depends on:** module 1 (`Driver`), module 2 (`Vehicle`) · **Used by:** module 4 (reservations), module 5 (reviews)
> **Sprints:** S1 structure and CRUD → S2 search, map, business rules → S3 AI (fair price)

## Team

| Member | Own module | Role for this module |
|---|---|---|
| Alaaeddine Guouider | 01 · User management | Hand-off partner: shares an interface with this module (see section 6) |
| Abdallah Salhi | 02 · Vehicle management | Hand-off partner: shares an interface with this module (see section 6) |
| Wasim Snoussi | 03 · Trip management | **Module owner**: builds and presents this module |
| Selim Aschi | 04 · Reservation management | Hand-off partner: shares an interface with this module (see section 6) |
| Ahmed Ridha Lazhari | 05 · Communication & feedback | Hand-off partner: shares an interface with this module (see section 6) |
| Our professor | — | Product Owner: sets the value of each story and accepts work at the sprint review |
| Rotates each sprint | — | Scrum Master: facilitates, removes blockers, protects the sprint goal |

---

**Reading guide.** Rows marked **†** come from the official product backlog (slide 37). The other rows are derived from the module slides; their *Value* and *Complexity* are **proposed** and must be confirmed with the Product Owner. Priority = Value ÷ Complexity.

---

## 1. Scope

| | |
|---|---|
| **Entities** | `Trip`, `Stop`, enum `TripStatus` |
| **CRUD** | Create a trip (route, stops, date, seats, price) · edit and cancel a trip · search and filter trips · admin: list and delete trips |
| **Advanced features** | Suggested fair price · route shown on an OpenStreetMap map · intermediate stops included in search · auto-close when full or past |
| **AI feature** | Fair price suggestion per seat, based on distance, fuel cost and seats |
| **Key rule** | A driver **cannot charge more than 150 %** of the suggested price and **cannot offer more seats than the vehicle has** |

---

## 2. Product backlog

| ID | User story | Value | Complexity | Priority | MoSCoW | Sprint |
|---|---|---|---|---|---|---|
| 3.1 † | As a driver, I want to publish a trip with a suggested price, so that passengers can book my seats | 100 | 5 | 20.0 | Must | S1 → S3 |
| 3.2 † | As a passenger, I want to search trips by route and date, so that I find a ride that suits me | 90 | 3 | 30.0 | Must | S1 → S2 |
| 3.3 | As a driver, I want to edit or cancel my trip, so that I can adapt when my plans change | 70 | 3 | 23.3 | Must | S1 → S2 |
| 3.4 | As a passenger, I want to filter and sort the results, so that I find the best trip faster | 60 | 3 | 20.0 | Should | S2 |
| 3.5 | As a driver, I want to add intermediate stops, so that more passengers can join along the route | 50 | 5 | 10.0 | Should | S2 |
| 3.6 | As a passenger, I want to see the route on a map, so that I know where the trip goes | 60 | 5 | 12.0 | Should | S2 |
| 3.7 | As a driver, I want a fair price suggestion, so that I do not guess the price | 70 | 5 | 14.0 | Should | S3 |
| 3.8 | As an administrator, I want to list and delete trips, so that I can remove problem trips | 50 | 2 | 25.0 | Must | S1 → S2 |
| 3.9 | As a passenger, I want full or past trips to disappear, so that I only see trips I can book | 50 | 3 | 16.7 | Should | S2 |
| 3.10 | As an administrator, I want trip reports and exports, so that I can follow activity | 40 | 3 | 13.3 | Should | S2 |

> Sprint note: in Sprint 1 the driver types the price by hand. The AI suggestion and the 150 % cap arrive in Sprint 3 and are wired into story 3.1.

---

## 3. Specifications

### 3.1 Data model

```python
# trips/models.py
class TripStatus(models.TextChoices):
    OPEN = "OPEN"
    FULL = "FULL"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class Trip(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="published_trips")      # Driver 1 — 0..* Trip
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT,
                                related_name="trips")               # Vehicle 1 — 0..* Trip
    departure_city = models.CharField(max_length=80, db_index=True)
    arrival_city = models.CharField(max_length=80, db_index=True)
    departure_datetime = models.DateTimeField(db_index=True)
    seats = models.PositiveSmallIntegerField()
    remaining_seats = models.PositiveSmallIntegerField()
    price_per_seat = models.DecimalField(max_digits=6, decimal_places=2)
    suggested_price = models.DecimalField(max_digits=6, decimal_places=2, null=True)   # for the 150 % check
    distance_km = models.FloatField()
    duration_minutes = models.PositiveIntegerField(null=True)       # from OSRM, used for overlap check
    route_geometry = models.JSONField(null=True, blank=True)         # polyline for the map
    status = models.CharField(max_length=10, choices=TripStatus.choices, default=TripStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["departure_city", "arrival_city", "departure_datetime"])]

class Stop(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")   # composition
    place = models.CharField(max_length=80, db_index=True)
    order = models.PositiveSmallIntegerField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["trip", "order"], name="unique_stop_order")]
```

UML methods → Django

| UML method | Django implementation |
|---|---|
| `create()`, `edit()`, `cancel()` | `TripCreateView`, `TripUpdateView`, `cancel_trip()` service |
| `search(from, to, date)` | `TripQuerySet.search(...)` + `TripSearchView` |
| `suggestPrice()` | `ai.suggest_price(distance_km, seats)` (Sprint 3) |
| `closeAutomatically()` | management command `close_trips` + status update on seat changes |

The seat counter is changed **only** through methods on `Trip` (`hold_seats(n)`, `release_seats(n)`) using `transaction.atomic()` and `select_for_update()`, so two passengers cannot take the last seat at the same time. Module 4 calls these methods.

### 3.2 Business rules

| Rule | Value | Enforced in |
|---|---|---|
| Who can publish | a `DRIVER` with an `ACCEPTED` vehicle | `TripCreateView` permission + `TripForm` |
| Vehicle must belong to the driver | | `TripForm` queryset |
| Seats offered | 1 ≤ seats ≤ `vehicle.seats` | `TripForm.clean()` |
| Departure window | at least **1 hour** from now and at most **30 days** ahead | `TripForm.clean()` |
| No overlapping trip | same driver cannot have two trips overlapping in time (departure + duration) | `TripForm.clean()` |
| Price cap | `price_per_seat ≤ 1.5 × suggested_price` | `TripForm.clean()` |
| Departure ≠ arrival | | `TripForm.clean()` |
| Stops | ordered, unique `order`, not equal to departure or arrival city | `StopFormSet` |
| Edit lock | once a reservation exists, route and date cannot change; seats cannot go below booked seats | `TripUpdateView` |
| Cancel | trip becomes `CANCELLED`, all active reservations `CANCELLED`, passengers notified | `cancel_trip()` service (calls module 4) |
| Auto-status | `remaining_seats == 0` → `FULL`; a freed seat → `OPEN` again; departure passed → `COMPLETED` | `Trip.hold_seats/release_seats`, `close_trips` command |
| Search visibility | only `OPEN`, future, `remaining_seats > 0` | `TripQuerySet.bookable()` |
| Performance | search results in **under 2 seconds** | DB indexes, `select_related`, pagination |

### 3.3 Screens and URLs (`app_name = "trips"`)

| URL | View | Who | Story |
|---|---|---|---|
| `/trips/` | `TripSearchView` (form + results, filters, sort, pagination) | Everyone logged in | 3.2, 3.4 |
| `/trips/<id>/` | `TripDetailView` (route map, stops, driver rating) | Logged in | 3.6 |
| `/trips/publish/` | `TripCreateView` (route, stops, date, seats, price, suggested price) | Driver | 3.1, 3.5, 3.7 |
| `/trips/mine/` | `MyTripsView` | Driver | 3.3 |
| `/trips/<id>/edit/` | `TripUpdateView` | Driver (owner) | 3.3 |
| `/trips/<id>/cancel/` | `TripCancelView` | Driver (owner) | 3.3 |
| `/trips/route-preview/` | `RoutePreviewView` (AJAX: route + suggested price) | Driver | 3.1, 3.7 |
| `/manage/trips/` | `TripAdminListView` | Admin | 3.8 |
| `/manage/trips/<id>/delete/` | `TripAdminDeleteView` | Admin | 3.8 |
| `/manage/trips/export/<fmt>/` | `TripExportView` | Admin | 3.10 |

### 3.4 Permissions

- Publish, edit, cancel: `Driver` only, and only **their own** trips.
- Search and details: any logged-in user (Visitor sees only the home page).
- Admin: list, delete and export all trips.
- The driver's **phone is never shown** on trip pages (module 4 reveals it after acceptance).

### 3.5 Advanced features

- **Search** (story 3.2): `departure_city`, `arrival_city`, date (and optional time window). Matches an **intermediate stop** too: searching *Hammamet → Sousse* finds *Tunis → Sousse via Hammamet*.
- **Filters and sort** (3.4): maximum price, minimum seats, time of day; sort by departure time, price, driver rating.
- **Map** (3.6): Leaflet + OpenStreetMap tiles; route polyline from `route_geometry`, markers for departure, stops and arrival. If the map service is unavailable, the page still shows all trip details.
- **Route service:** OSRM (`computeRoute(start, stops, end)` → distance, duration, path), called server-side with a short timeout.
- **Auto-close** (3.9): management command `close_trips` run every few minutes (cron or Celery beat) + immediate updates on seat changes.
- **Notifications:** "Notify the passengers" on cancellation (use case `include`).
- **Admin tools:** pagination, search, PDF, CSV, Excel export.

### 3.6 AI feature · Fair price suggestion (Sprint 3)

`ai.suggest_price(distance_km, seats, vehicle=None) -> Decimal`

1. **Baseline formula (works from Sprint 1 as a helper):** fuel cost of the trip = `distance_km × consumption (L/100 km) ÷ 100 × fuel price (TND/L)`, shared between the passengers and the driver: `÷ (seats + 1)`, rounded to 0.1 TND. Consumption and fuel price are **settings**, not hard-coded.
2. **ML refinement:** a scikit-learn regression trained on the baseline plus historical accepted prices (distance, seats, day, time) corrects the baseline. Before enough history exists, the baseline alone is used.
3. The driver sees the suggested price and may change it **up to 150 %** of it. `suggested_price` is stored on the trip so the cap can be checked later.
4. Fallback: if OSRM is down, a straight-line distance estimate is used and the driver sees a notice.

---

## 4. Acceptance criteria

**3.1 Publish a trip**
- **Success** · *Given* Karim is a driver with an accepted 4-seat vehicle · *When* he publishes Tunis → Sousse tomorrow at 08:00, 3 seats, at a price within the cap · *Then* the route and suggested price are shown, the trip is saved as `OPEN`, and "Trip published" is displayed.
- **Failure A** · *Given* the suggested price is 8 TND · *When* Karim enters 13 TND (more than 150 %) · *Then* "Price cap exceeded" is shown and the trip is not saved.
- **Failure B** · *Given* his vehicle has 4 seats · *When* he offers 5 seats, or sets a departure in 30 minutes, or overlaps another of his trips · *Then* a clear error is shown and the trip is not saved.

**3.2 Search trips by route and date**
- **Success** · *Given* three `OPEN` Tunis → Sousse trips exist tomorrow · *When* Sami searches Tunis → Sousse for tomorrow · *Then* the three trips are listed in under 2 seconds.
- **Failure** · *Given* no trip matches · *When* Sami searches · *Then* "No trips found" is shown with a suggestion to try another date. A date in the past is refused.

**3.3 Edit or cancel a trip**
- **Success** · *Given* Karim's trip has 2 accepted passengers · *When* he cancels it · *Then* the trip becomes `CANCELLED`, the reservations are cancelled, and the passengers are notified by e-mail.
- **Failure** · *Given* 2 seats are already booked · *When* Karim tries to reduce the seats to 1, or to change the date · *Then* the change is refused with an explanation.

**3.4 Filter and sort**
- **Success** · *Given* a result list · *When* Sami filters "max 10 TND" and sorts by price · *Then* only trips up to 10 TND are shown, cheapest first.
- **Failure** · *Given* an invalid filter (e.g. negative price) · *When* Sami applies it · *Then* an error message is shown and the list is unchanged.

**3.5 Intermediate stops**
- **Success** · *Given* Karim adds Hammamet as stop 1 on Tunis → Sousse · *When* Sami searches Hammamet → Sousse · *Then* the trip appears.
- **Failure** · *Given* a stop with the same city as the departure, or two stops with the same order · *When* Karim saves · *Then* the stop is rejected.

**3.6 Route on a map**
- **Success** · *Given* a published trip · *When* Sami opens its details · *Then* an OpenStreetMap map shows the route, stops and arrival.
- **Failure** · *Given* the map or route service is unreachable · *When* the page loads · *Then* the trip details are shown without the map and a short notice.

**3.7 Fair price suggestion**
- **Success** · *Given* a route of about 140 km and 3 seats · *When* the driver reaches the price step · *Then* a suggested price per seat is displayed and pre-filled.
- **Failure** · *Given* the ML model is unavailable · *When* the driver reaches the price step · *Then* the baseline formula is used and the driver can still publish.

**3.8 Admin lists and deletes trips**
- **Success** · *Given* a trip with no active reservation · *When* the administrator deletes it · *Then* it is removed from the list.
- **Failure** · *Given* a trip has active reservations · *When* the administrator removes it · *Then* it is cancelled instead and the passengers are notified. A passenger opening `/manage/trips/` gets HTTP 403.

**3.9 Auto-close**
- **Success** · *Given* a trip has 1 free seat · *When* the last seat is accepted · *Then* the trip becomes `FULL` and disappears from search; after departure it becomes `COMPLETED`.
- **Failure (guard)** · *Given* a `FULL` trip · *When* a passenger cancels in time · *Then* the seat is released and the trip is `OPEN` again.

**3.10 Reports and exports**
- **Success** · *Given* an administrator selects a month and "Excel" · *When* he exports · *Then* an Excel file with the trips of that month is downloaded.
- **Failure** · *Given* a driver calls the export URL · *When* the request arrives · *Then* HTTP 403 is returned.

---

## 5. Tasks by sprint

Branch: `module-3-trips`. One Trello card per task, one owner.

### Sprint 1 · Structure and CRUD
- [ ] `M3-S1-01` **Shared database design (week 1):** `Trip` ↔ `Driver`, `Vehicle`, `Reservation` *(team)*
- [ ] `M3-S1-02` Models `Trip`, `Stop`, `TripStatus`, indexes, migrations · *3.1*
- [ ] `M3-S1-03` `TripForm` + `StopFormSet` with seat, date and price validation (manual price) · *3.1*
- [ ] `M3-S1-04` Views and templates: publish, my trips, edit, cancel · *3.1, 3.3*
- [ ] `M3-S1-05` Basic search view (from, to, date) and results list · *3.2*
- [ ] `M3-S1-06` `Trip.hold_seats()` and `release_seats()` with row locking (used by module 4) · *shared*
- [ ] `M3-S1-07` Admin list and delete trips · *3.8*
- [ ] `M3-S1-08` Permissions: driver-only publishing, owner-only edit · *3.1, 3.3*

### Sprint 2 · Business features
- [ ] `M3-S2-01` OSRM client: `compute_route()` with timeout and error handling · *3.6*
- [ ] `M3-S2-02` Leaflet + OpenStreetMap map on trip details and publish preview · *3.6*
- [ ] `M3-S2-03` Departure window (1 h to 30 days) and overlap check · *3.1*
- [ ] `M3-S2-04` Intermediate stops: UI, ordering, included in search · *3.5*
- [ ] `M3-S2-05` Filters (price, seats, time) and sort options · *3.4*
- [ ] `M3-S2-06` Pagination, DB indexes, check search under 2 s with test data · *3.2*
- [ ] `M3-S2-07` Edit lock when reservations exist · *3.3*
- [ ] `M3-S2-08` Cancel trip: cascade to reservations + e-mail to passengers (with module 4) · *3.3*
- [ ] `M3-S2-09` Command `close_trips` (FULL / COMPLETED) · *3.9*
- [ ] `M3-S2-10` Admin filters, PDF, CSV, Excel exports · *3.10*
- [ ] `M3-S2-11` Tests: forms, search queries, concurrency on the last seat · *3.1–3.9*

### Sprint 3 · Artificial intelligence
- [ ] `M3-S3-01` `ai.suggest_price()` baseline formula with settings for consumption and fuel price · *3.7*
- [ ] `M3-S3-02` Collect training data and train the scikit-learn model · *3.7*
- [ ] `M3-S3-03` Show suggested price in the publish form, store `suggested_price` · *3.7*
- [ ] `M3-S3-04` Enforce the 150 % price cap with the stored suggestion · *3.1*
- [ ] `M3-S3-05` Fallbacks: no model → baseline; no OSRM → straight-line estimate · *3.7*
- [ ] `M3-S3-06` Bug fixes, final tests, live demo of "publish a trip with a fair price" *(team)*

---

## 6. Interfaces with the other modules

| Other module | What it takes from here | What it gives back |
|---|---|---|
| 1 · Users | `Driver` as publisher | — |
| 2 · Vehicles | `Vehicle.seats`, `status == ACCEPTED` | prevents vehicle deletion while trips use it |
| 4 · Reservations | `hold_seats()`, `release_seats()`, `remaining_seats`, `departure_datetime` | receives cancellation cascade |
| 5 · Communication | `Trip` as the subject of a review; trip `COMPLETED` status | — |

## 7. Definition of done

- Pull request reviewed and merged to `main`.
- Tests cover every rule in section 3.2 (valid and invalid cases).
- Search verified under 2 seconds on a realistic data set.
- No negative seat count possible under concurrent bookings.
- Map and route features degrade gracefully when external services fail.
- Trello card in *Done* and shown at the sprint review.
