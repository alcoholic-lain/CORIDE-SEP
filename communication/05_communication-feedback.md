# Module 05 · Communication & feedback

> **Owner:** Ahmed Ridha Lazhari · **Django app:** `communication` · **Branch:** `module-5-communication`
> **Depends on:** modules 1, 3, 4 (`User`, `Trip`, `Reservation`) · **Used by:** module 1 (average rating on profiles), module 3 (driver rating in search)
> **Sprints:** S1 structure and CRUD → S2 real-time chat and rules → S3 AI (insult filter)

**Reading guide.** Rows marked **†** come from the official product backlog (slide 37). The other rows are derived from the module slides; their *Value* and *Complexity* are **proposed** and must be confirmed with the Product Owner. Priority = Value ÷ Complexity.

---

## 1. Scope

| | |
|---|---|
| **Entities** | `Conversation`, `Message`, `Review` |
| **CRUD** | Send, view and delete messages · write, edit and delete reviews · admin: delete inappropriate reviews |
| **Advanced features** | Chat opens when a booking is accepted · real-time messaging (WebSockets) · average rating shown on profiles |
| **AI feature** | Insult filter on chat messages and reviews |
| **Key rule** | The chat **closes 24 hours after departure**, and each passenger or driver leaves **one review per person per trip** |

---

## 2. Product backlog

| ID | User story | Value | Complexity | Priority | MoSCoW | Sprint |
|---|---|---|---|---|---|---|
| 5.1 † | As a passenger, I want to chat with my driver, so that we agree on the meeting point | 70 | 5 | 14.0 | Should | S1 → S2 |
| 5.2 † | As a passenger or a driver, I want to rate the other person after a trip, so that the community stays trustworthy | 24 | 2 | 12.0 | Could | S1 |
| 5.3 | As a user, I want to delete my own messages, so that I can remove a message sent by mistake | 20 | 1 | 20.0 | Could | S1 |
| 5.4 | As a user, I want to edit or delete my review, so that I can correct it | 20 | 2 | 10.0 | Could | S1 → S2 |
| 5.5 | As a passenger, I want to see a user's average rating, so that I know who I travel with | 30 | 2 | 15.0 | Could | S2 |
| 5.6 | As an administrator, I want to delete inappropriate reviews, so that the platform stays respectful | 50 | 2 | 25.0 | Should | S1 → S2 |
| 5.7 | As a user, I want insulting text blocked, so that chats and reviews stay respectful | 40 | 5 | 8.0 | Should | S3 |
| 5.8 | As a user, I want messages delivered in real time, so that I do not need to refresh the page | 50 | 8 | 6.3 | Should | S2 |
| 5.9 | As the platform, I want the chat to close 24 h after departure, so that old conversations do not stay open | 30 | 2 | 15.0 | Could | S2 |
| 5.10 | As an administrator, I want review reports and exports, so that I can follow community quality | 40 | 3 | 13.3 | Should | S2 |

---

## 3. Specifications

### 3.1 Data model

```python
# communication/models.py
class Conversation(models.Model):
    reservation = models.OneToOneField("reservations.Reservation", on_delete=models.CASCADE,
                                       related_name="conversation")      # Reservation 1 — 0..1 Conversation
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_open(self):
        # closed manually, or 24 h after the trip departure
        limit = self.reservation.trip.departure_datetime + timedelta(hours=24)
        return self.closed_at is None and timezone.now() < limit

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,     # composition
                                     related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="messages_sent")                      # Passenger 1 — 0..* writes
    content = models.TextField(max_length=1000)
    sent_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)                                  # soft delete

    class Meta:
        ordering = ["sent_at"]

class Review(models.Model):
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="reviews")   # about
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="reviews_written")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="reviews_received")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=500, blank=True)
    review_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["trip", "reviewer", "target"], name="one_review_per_person_per_trip"),
            models.CheckConstraint(check=~models.Q(reviewer=models.F("target")), name="no_self_review"),
        ]
```

A review has a **reviewer** (who writes it) and a **target** (who is rated), both users (a driver is a passenger too).

UML methods → Django

| UML method | Implementation |
|---|---|
| `open()`, `close()` | `open_conversation(reservation)` (signal on acceptance), `close_conversation()` |
| `send()`, `delete()` (Message) | WebSocket consumer + `delete_message()` |
| `write()`, `edit()`, `delete()` (Review) | `ReviewCreateView`, `ReviewUpdateView`, `ReviewDeleteView` |
| `filterInsults()` | `ai.filter_insults(text) -> bool` (called by both Message and Review services) |

### 3.2 Business rules

| Rule | Value | Enforced in |
|---|---|---|
| Chat opens | when a reservation becomes `ACCEPTED`; one conversation per reservation | signal from module 4 → `open_conversation()` |
| Chat participants | only the passenger and the driver of that reservation | consumer and view permission |
| Chat closes | **24 hours after the trip's departure** (or when the reservation is cancelled or refused) | `Conversation.is_open`, command `close_conversations` |
| Message length | 1 to 1000 characters, no empty messages | `Message` validation |
| Delete a message | only the sender; the message shows as "Message deleted" for both | `delete_message()` (soft delete) |
| Review allowed | only after the trip is `COMPLETED`, and only between people who travelled together (passenger ↔ driver; reservation `COMPLETED`) | `ReviewForm.clean()` |
| One review per person per trip | unique `(trip, reviewer, target)` | DB constraint + form |
| No self-review | reviewer ≠ target | DB check constraint |
| Rating | integer 1 to 5; comment up to 500 characters (optional) | validators |
| Edit and delete review | only the reviewer; the comment goes through the insult filter again | views |
| Average rating | computed from received reviews; **shown only from 3 reviews** | `User.average_rating` helper / template tag |
| Insulting text | message or review is **refused**, nothing is stored | `ai.filter_insults()` before saving |
| Admin moderation | an administrator may delete any review; the average is recalculated | `ReviewAdminDeleteView` |
| Chat latency | messages delivered in **under 1 second** | WebSocket (Channels + Redis) |

### 3.3 Screens and URLs (`app_name = "communication"`)

| URL | View | Who | Story |
|---|---|---|---|
| `/chat/` | `ConversationListView` (my open and closed conversations, unread count) | Passenger, Driver | 5.1 |
| `/chat/<id>/` | `ConversationView` (history + live input) | the two participants | 5.1, 5.8 |
| `ws://…/ws/chat/<id>/` | `ChatConsumer` (WebSocket) | the two participants | 5.8 |
| `/chat/messages/<id>/delete/` | `MessageDeleteView` | sender | 5.3 |
| `/trips/<id>/review/<user_id>/` | `ReviewCreateView` | participant of a completed trip | 5.2 |
| `/reviews/<id>/edit/` · `/delete/` | `ReviewUpdateView`, `ReviewDeleteView` | reviewer | 5.4 |
| `/users/<id>/reviews/` | `UserReviewsView` (average + list) | Logged in | 5.5 |
| `/manage/reviews/` | `ReviewAdminListView` | Admin | 5.6 |
| `/manage/reviews/<id>/delete/` | `ReviewAdminDeleteView` | Admin | 5.6 |
| `/manage/reviews/export/<fmt>/` | `ReviewExportView` | Admin | 5.10 |

### 3.4 Permissions

- Conversation and messages: **only the two participants** (checked in HTTP views and in the WebSocket `connect()`; anonymous sockets are refused).
- Review: reviewer edits and deletes their own; any logged-in user reads ratings.
- Administrator: list, delete and export reviews. An administrator does **not** read private chats.

### 3.5 Advanced features

- **Real-time chat** (5.8): Django **Channels** with a Redis channel layer. One group per conversation (`chat_<id>`). Session authentication on connect. Messages are saved first, then broadcast. The client auto-reconnects and fetches missed messages by `sent_at`.
- **Unread counter** (`read` field): shown in the navigation bar; set when the recipient opens the conversation.
- **Chat closing** (5.9): `close_conversations` command (cron or Celery beat) + `is_open` check on every send, so a closed chat can never receive messages even if the command is late.
- **Average rating** (5.5): average of `rating` for `target=user`, rounded to 1 decimal, shown on profile and trip details only when the user has **3 or more** reviews, with the review count; otherwise "Not enough reviews yet".
- **Admin tools:** pagination, filter by rating, search by user; PDF, CSV, Excel export.

### 3.6 AI feature · Insult filter (Sprint 3)

`ai.filter_insults(text) -> bool` (True = insulting, must be blocked)

Layered approach, used by `Message` and `Review` services:
1. **Normalisation:** lower case, remove accents and repeated letters, replace common character tricks (`@`→`a`, `0`→`o`, spaces inside words).
2. **Word list** with **whole-word matching** (avoids false positives such as innocent words that contain an insult) for French, Arabic, Tunisian dialect (including Arabizi), and English. Kept in an editable file.
3. **ML classifier** (e.g. TF-IDF + logistic regression, or a pre-trained toxicity model) for insults not in the list. Threshold is a setting.
4. **Outcome:** chat → "Message not sent"; review → "Review refused"; the text is **not stored**. The user can rewrite and resend.
5. **Fallback:** if the ML model is unavailable, the word list alone is used; the app never blocks sending because of a model error.

---

## 4. Acceptance criteria

**5.1 Chat with my driver**
- **Success** · *Given* Karim accepted Sami's booking · *When* Sami opens the chat and sends "Where is the meeting point?" · *Then* the message is saved and Karim sees it in under 1 second.
- **Failure A** · *Given* Sami's booking is still `PENDING` or `REFUSED` · *When* he tries to open a chat · *Then* no conversation exists and access is refused.
- **Failure B** · *Given* the trip left 25 hours ago · *When* Sami tries to send a message · *Then* "This conversation is closed" is shown and nothing is saved. A user who is not one of the two participants gets HTTP 403.

**5.2 Rate the other person**
- **Success** · *Given* the trip is `COMPLETED` and Sami travelled with Karim · *When* Sami gives 5 stars and a polite comment · *Then* the review is saved and Karim's average is updated.
- **Failure A** · *Given* Sami already reviewed Karim for this trip · *When* he writes a second review · *Then* "You already reviewed this person for this trip" is shown.
- **Failure B** · *Given* the trip is not `COMPLETED` or Sami was not on it · *When* he tries to review · *Then* the review is refused.

**5.3 Delete my message**
- **Success** · *Given* Sami sent a message by mistake · *When* he deletes it · *Then* "Message deleted" is shown to both users.
- **Failure** · *Given* Karim's message · *When* Sami calls its delete URL · *Then* HTTP 403 is returned.

**5.4 Edit or delete my review**
- **Success** · *Given* Sami's review has 5 stars · *When* he changes it to 4 · *Then* the review is updated and the average is recalculated.
- **Failure** · *Given* another user's review, or an edit that adds an insult · *When* the change is submitted · *Then* HTTP 403 (not the reviewer) or "Review refused" (insult), and the review stays unchanged.

**5.5 See a user's rating**
- **Success** · *Given* Karim has 3 reviews (5, 4, 5) · *When* Sami opens Karim's profile · *Then* "4.7 (3 reviews)" is shown.
- **Failure** · *Given* Amal has only 2 reviews · *When* Sami opens her profile · *Then* "Not enough reviews yet" is shown instead of an average.

**5.6 Admin deletes an inappropriate review**
- **Success** · *Given* an administrator on the review list · *When* he deletes a review · *Then* it disappears and the target's average is recalculated.
- **Failure** · *Given* a passenger calls the admin delete URL · *When* the request arrives · *Then* HTTP 403 is returned.

**5.7 Insult filter**
- **Success** · *Given* a polite message "See you at 8, thanks!" · *When* it is sent · *Then* it passes the filter and is delivered.
- **Failure** · *Given* a message or review containing an insult · *When* it is sent · *Then* "Message not sent" (or "Review refused") is shown and **nothing is stored**.
- **Failure (false positive guard)** · *Given* a harmless word that merely contains an insulting sequence of letters · *When* it is sent · *Then* it is **not** blocked (whole-word matching).

**5.8 Real-time delivery**
- **Success** · *Given* Sami and Karim have the chat open in two browsers · *When* Sami sends a message · *Then* it appears for Karim without a page refresh.
- **Failure** · *Given* Karim's connection drops for 30 seconds · *When* it comes back · *Then* the page reconnects automatically and shows the missed messages. An anonymous WebSocket connection is refused.

**5.9 Chat closes 24 hours after departure**
- **Success** · *Given* a trip left 24 hours and 1 minute ago · *When* the closing command runs · *Then* `closed_at` is set and the chat becomes read-only.
- **Failure (guard)** · *Given* the command has not run yet · *When* a user sends a message after the limit · *Then* `is_open` is false and the message is refused anyway.

**5.10 Reports and exports**
- **Success** · *Given* an administrator filters reviews with 1 or 2 stars · *When* he exports to CSV · *Then* a CSV with these reviews is downloaded.
- **Failure** · *Given* a passenger calls the export URL · *When* the request arrives · *Then* HTTP 403 is returned.

---

## 5. Tasks by sprint

Branch: `module-5-communication`. One Trello card per task, one owner.

### Sprint 1 · Structure and CRUD
- [ ] `M5-S1-01` **Shared database design (week 1):** `Conversation` ↔ `Reservation`, `Review` ↔ `Trip` and users *(team)*
- [ ] `M5-S1-02` Models `Conversation`, `Message`, `Review`, constraints, migrations · *5.1, 5.2*
- [ ] `M5-S1-03` Signal / service `open_conversation()` called on acceptance (agree interface with module 4) · *5.1*
- [ ] `M5-S1-04` Simple HTTP chat: conversation list, conversation page, send message (no real time yet) · *5.1*
- [ ] `M5-S1-05` Delete my message (soft delete) · *5.3*
- [ ] `M5-S1-06` Review create view and form (1–5 rating, comment) · *5.2*
- [ ] `M5-S1-07` Review edit and delete by reviewer · *5.4*
- [ ] `M5-S1-08` Admin review list and delete · *5.6*
- [ ] `M5-S1-09` Permissions: participants only, reviewer only, admin only · *all*

### Sprint 2 · Business features
- [ ] `M5-S2-01` Install Channels + Redis, ASGI configuration, `ChatConsumer` with session auth · *5.8*
- [ ] `M5-S2-02` Chat front end: live messages, auto-reconnect, fetch missed messages · *5.8*
- [ ] `M5-S2-03` Unread counter in the navbar · *5.1*
- [ ] `M5-S2-04` `Conversation.is_open` rule + command `close_conversations` · *5.9*
- [ ] `M5-S2-05` Review rules: completed trip only, one per person per trip, no self-review · *5.2*
- [ ] `M5-S2-06` Average rating helper (≥ 3 reviews) shown on profile and trip details · *5.5*
- [ ] `M5-S2-07` Recalculate average on create, edit, delete and admin delete · *5.4, 5.6*
- [ ] `M5-S2-08` Admin filters, pagination, PDF, CSV, Excel exports · *5.10*
- [ ] `M5-S2-09` Tests: channel consumer (auth, delivery), review constraints, closing rule · *5.1–5.9*

### Sprint 3 · Artificial intelligence
- [ ] `M5-S3-01` Collect and prepare an insult word list (French, Arabic, Tunisian dialect, Arabizi, English) · *5.7*
- [ ] `M5-S3-02` Text normalisation + whole-word matching `ai.filter_insults()` · *5.7*
- [ ] `M5-S3-03` Train or integrate the ML toxicity classifier, set threshold · *5.7*
- [ ] `M5-S3-04` Plug the filter into message sending and review create / edit · *5.7*
- [ ] `M5-S3-05` Fallback to word list when the model fails; test false positives · *5.7*
- [ ] `M5-S3-06` Bug fixes, final tests, live demo of chat with the insult filter and a review *(team)*

---

## 6. Interfaces with the other modules

| Other module | What it takes from here | What it gives back |
|---|---|---|
| 1 · Users | — | `average_rating` shown on the profile |
| 3 · Trips | `Trip` and its `COMPLETED` status | driver rating shown in search results and details |
| 4 · Reservations | `ACCEPTED` status opens a conversation; `COMPLETED` allows reviews | — |
| `ai/` shared package | — | exposes `filter_insults()` also usable by other modules |

## 7. Definition of done

- Pull request reviewed and merged to `main`.
- Tests cover chat permissions (participant, outsider, anonymous), closing rule and review constraints.
- Real-time delivery measured under 1 second on a local network.
- Insulting text is never stored; false-positive tests included.
- Chat and reviews usable on mobile.
- Trello card in *Done* and shown at the sprint review.

## Current scaffold preview

This screenshot shows the current shared placeholder page, not the implemented communication and feedback features.

![Current communication-module placeholder](screenshots/coms.png)
