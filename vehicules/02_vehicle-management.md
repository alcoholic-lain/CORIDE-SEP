# Module 02 · Vehicle management

> **Owner:** Abdallah Salhi · **Django app:** `vehicles` · **Branch:** `module-2-vehicles`
> **Depends on:** module 1 (`User`) · **Used by:** module 3 (a trip needs an accepted vehicle)
> **Sprints:** S1 structure and CRUD → S2 business rules → S3 AI (OCR)

## Team

| Member | Own module | Role for this module |
|---|---|---|
| Alaaeddine Guouider | 01 · User management | Hand-off partner: shares an interface with this module (see section 6) |
| Abdallah Salhi | 02 · Vehicle management | **Module owner**: builds and presents this module |
| Wasim Snoussi | 03 · Trip management | Hand-off partner: shares an interface with this module (see section 6) |
| Selim Aschi | 04 · Reservation management | Team member: reviews pull requests and joins the sprint events |
| Ahmed Ridha Lazhari | 05 · Communication & feedback | Team member: reviews pull requests and joins the sprint events |
| Our professor | — | Product Owner: sets the value of each story and accepts work at the sprint review |
| Rotates each sprint | — | Scrum Master: facilitates, removes blockers, protects the sprint goal |

---

**Reading guide.** Rows marked **†** come from the official product backlog (slide 37). The other rows are derived from the module slides; their *Value* and *Complexity* are **proposed** and must be confirmed with the Product Owner. Priority = Value ÷ Complexity.

---

## 1. Scope

| | |
|---|---|
| **Entities** | `Vehicle`, `Document`, enums `VehicleStatus`, `DocumentType`, `DocumentStatus` |
| **CRUD** | Add, edit, delete vehicles · upload license, registration, insurance · admin: validate or reject with a reason · admin: list and search vehicles |
| **Advanced features** | Automatic reading of documents (OCR) · expiry alerts 30 and 7 days before · Tunisian plate format check · up to 3 vehicles per driver |
| **AI feature** | OCR reads the license, registration and insurance, and fills in the fields |
| **Key rule** | A passenger becomes a driver **only once one of their vehicles is validated by the administrator** |

---

## 2. Product backlog

| ID | User story | Value | Complexity | Priority | MoSCoW | Sprint |
|---|---|---|---|---|---|---|
| 2.1 † | As a passenger, I want to register my vehicle and its documents, so that I can become a driver | 90 | 5 | 18.0 | Must | S1 → S2 |
| 2.2 | As an administrator, I want to accept or refuse a vehicle with a reason, so that only safe vehicles are used | 90 | 5 | 18.0 | Must | S1 → S2 |
| 2.3 | As a driver, I want to edit and delete my vehicles, so that my information stays correct | 60 | 3 | 20.0 | Must | S1 |
| 2.4 | As an administrator, I want to list and search vehicles, so that I find any vehicle quickly | 40 | 3 | 13.3 | Should | S1 → S2 |
| 2.5 | As a passenger, I want my documents to be read automatically, so that I do not type everything | 60 | 8 | 7.5 | Should | S3 |
| 2.6 | As a driver, I want expiry alerts, so that my documents never expire without warning | 40 | 3 | 13.3 | Should | S2 |
| 2.7 | As a passenger, I want my plate number checked, so that typing mistakes are caught early | 50 | 2 | 25.0 | Must | S2 |
| 2.8 | As the platform, I want to limit a driver to 3 vehicles, so that the fleet stays manageable | 40 | 1 | 40.0 | Must | S1 |
| 2.9 | As a driver, I want to renew my documents, so that my vehicle can be used again | 50 | 3 | 16.7 | Should | S2 |
| 2.10 | As an administrator, I want vehicle reports and exports, so that I can follow validations | 40 | 3 | 13.3 | Should | S2 |

---

## 3. Specifications

### 3.1 Data model

```python
# vehicles/models.py
class VehicleStatus(models.TextChoices):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REFUSED = "REFUSED"
    DOCUMENTS_EXPIRED = "DOCUMENTS_EXPIRED"

class DocumentType(models.TextChoices):
    LICENSE = "LICENSE"
    REGISTRATION = "REGISTRATION"
    INSURANCE = "INSURANCE"

class DocumentStatus(models.TextChoices):
    PENDING = "PENDING"
    VALID = "VALID"
    EXPIRED = "EXPIRED"

class Vehicle(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="vehicles")           # Passenger 1 — 0..3 Vehicle
    brand = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)
    plate_number = models.CharField(max_length=20, unique=True, validators=[validate_tunisian_plate])
    seats = models.PositiveSmallIntegerField()                   # seats offered to passengers
    status = models.CharField(max_length=20, choices=VehicleStatus.choices,
                              default=VehicleStatus.PENDING)
    refusal_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE,    # composition: deleted with vehicle
                                related_name="documents")
    type = models.CharField(max_length=15, choices=DocumentType.choices)
    number = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to="documents/", validators=[validate_document_file])
    status = models.CharField(max_length=10, choices=DocumentStatus.choices,
                              default=DocumentStatus.PENDING)
    last_alert_days = models.PositiveSmallIntegerField(null=True, blank=True)  # 30 or 7, avoids duplicates

    class Meta:
        constraints = [models.UniqueConstraint(fields=["vehicle", "type"], name="one_document_per_type")]
```

Class diagram methods → Django equivalents

| UML method | Django implementation |
|---|---|
| `add()`, `edit()`, `delete()` | `CreateView`, `UpdateView`, `DeleteView` |
| `checkPlateFormat()` | `validate_tunisian_plate` validator |
| `accept()`, `refuse(reason)` | `vehicles.services.accept_vehicle()` / `refuse_vehicle()` |
| `upload()` | `DocumentForm` + `validate_document_file` |
| `readWithOCR()` | `ai.read_document(file)` (Sprint 3) |
| `isExpired()` | `Document.is_expired` property |
| `sendExpiryAlert()` | management command `send_expiry_alerts` |

### 3.2 Business rules

| Rule | Value | Enforced in |
|---|---|---|
| Vehicles per owner | 0 to 3 | `VehicleForm.clean()` + service check |
| Documents per vehicle | exactly 3 (license, registration, insurance) | `VehicleCreateView` formset, `UniqueConstraint` |
| File type and size | JPG, PNG or PDF, **5 MB max** | `validate_document_file` |
| Plate format | Tunisian plate, e.g. `123 TUN 4567` | `validate_tunisian_plate` (regex, spaces tolerated, upper-cased). The team lists any other accepted formats before Sprint 2 |
| Unique plate | one vehicle per plate number | DB unique |
| Expiry date | must be in the future when uploading | `DocumentForm.clean_expiry_date` |
| Validation | only an administrator accepts or refuses; refusal **requires a reason** | `AdminVehicleDecisionForm` |
| Driver promotion | on first `ACCEPTED` vehicle: `owner.user_type = DRIVER`, `became_driver_at = now` | `accept_vehicle()` (calls module 1) |
| Sensitive edit *(proposed)* | changing plate number or seats of an accepted vehicle sends it back to `PENDING` | `Vehicle.save()` / service |
| Expired document | document `EXPIRED` → vehicle `DOCUMENTS_EXPIRED` → cannot be used to publish trips | `send_expiry_alerts` command + module 3 check |
| Deletion | blocked while the vehicle is used by an `OPEN` or `FULL` trip | `VehicleDeleteView` |

### 3.3 Screens and URLs (`app_name = "vehicles"`)

| URL | View | Who | Story |
|---|---|---|---|
| `/vehicles/` | `MyVehiclesView` | Passenger, Driver | 2.1, 2.3 |
| `/vehicles/add/` | `VehicleCreateView` (3 document uploads, OCR pre-fill) | Passenger, Driver | 2.1, 2.5, 2.7, 2.8 |
| `/vehicles/<id>/` | `VehicleDetailView` (status, refusal reason, documents) | Owner, Admin | 2.1 |
| `/vehicles/<id>/edit/` | `VehicleUpdateView` | Owner | 2.3 |
| `/vehicles/<id>/delete/` | `VehicleDeleteView` | Owner | 2.3 |
| `/vehicles/<id>/renew/` | `DocumentRenewView` | Owner | 2.9 |
| `/vehicles/ocr/` | `OcrDocumentView` (AJAX: file → number and expiry) | Owner | 2.5 |
| `/manage/vehicles/` | `VehicleAdminListView` (search, filter by status, pagination) | Admin | 2.4 |
| `/manage/vehicles/<id>/accept/` · `/refuse/` | `AcceptVehicleView`, `RefuseVehicleView` | Admin | 2.2 |
| `/manage/vehicles/export/<fmt>/` | `VehicleExportView` | Admin | 2.10 |

### 3.4 Permissions

- Passenger and Driver: only **their own** vehicles (queryset filtered by `owner=request.user`).
- Administrator: all vehicles, accept and refuse, export.
- Visitor: no access.
- Document files are served through a view that checks owner or admin (not public media URLs).

### 3.5 Advanced features

- **Tunisian plate check** (story 2.7): immediate message under the field.
- **Limit of 3 vehicles** (story 2.8): "Add a vehicle" button hidden at 3, server check too.
- **Expiry alerts** (story 2.6): command `send_expiry_alerts`, run daily (cron or Celery beat). Sends an e-mail at **30 days** and again at **7 days** before expiry, once per threshold (`last_alert_days`). On the expiry date: document `EXPIRED`, vehicle `DOCUMENTS_EXPIRED`.
- **Renewal** (story 2.9): the driver uploads new documents, the vehicle returns to `PENDING`, the administrator accepts it again and the vehicle goes back to `ACCEPTED`.
- **Notifications** to the owner by e-mail on accept and on refusal with the reason (use case "Notify the owner").
- **Admin lists:** search by plate, brand, owner; filter by status; pagination.
- **Exports:** PDF, CSV and Excel of vehicles by status.

### 3.6 AI feature · Document OCR (Sprint 3)

`ai.read_document(file, doc_type) -> {"number": str | None, "expiry_date": date | None}`

- Pipeline: image or PDF page → pre-processing (grayscale, deskew) → OCR engine (e.g. Tesseract with Arabic + French, or EasyOCR) → extraction by document type (regex for number and date patterns).
- The result **only pre-fills the form**; the user can correct it (the `opt [a field read by OCR is wrong]` branch of the sequence diagram).
- If OCR fails or is unsure: fields left empty and the message *"We could not read the document, please fill in the fields."* The flow is never blocked.
- The administrator always sees the original file next to the extracted values.

---

## 4. Acceptance criteria

**2.1 Register a vehicle and its documents**
- **Success** · *Given* Sami is a logged-in passenger with 0 vehicles · *When* he adds a Peugeot 208, plate `123 TUN 4567`, 4 seats, and uploads license, registration and insurance · *Then* the vehicle and its 3 documents are saved as `PENDING` and "Vehicle pending validation" is shown.
- **Failure A** · *Given* a document is an 8 MB file or a `.docx` · *When* Sami uploads it · *Then* the file is rejected with the reason and nothing is saved.
- **Failure B** · *Given* one of the three documents is missing · *When* Sami submits · *Then* the form asks for the missing document.

**2.2 Administrator accepts or refuses**
- **Success** · *Given* a `PENDING` vehicle with valid documents · *When* the administrator accepts it · *Then* status becomes `ACCEPTED`, the owner becomes a driver and receives "Vehicle accepted, you can publish trips".
- **Failure** · *Given* the administrator refuses a vehicle without a reason · *When* he submits · *Then* the form blocks until a reason is typed; with a reason, status becomes `REFUSED` and the owner receives the reason by e-mail.

**2.3 Edit and delete my vehicles**
- **Success** · *Given* Karim owns an accepted vehicle with no trip · *When* he deletes it · *Then* the vehicle and its 3 documents are deleted.
- **Failure** · *Given* the vehicle is used by an `OPEN` trip · *When* Karim deletes it · *Then* "Cancel or finish your trips with this vehicle first" is shown and nothing is deleted. Changing the plate of an accepted vehicle sends it back to `PENDING`.

**2.4 List and search vehicles**
- **Success** · *Given* an administrator on the vehicle list · *When* he searches `4567` · *Then* the matching vehicle is listed.
- **Failure** · *Given* no vehicle matches · *When* he searches · *Then* "No vehicle found" is shown. A passenger opening `/manage/vehicles/` gets HTTP 403.

**2.5 Automatic document reading**
- **Success** · *Given* a clear photo of an insurance paper · *When* it is uploaded · *Then* the number and expiry date fields are filled in and the user can edit them.
- **Failure** · *Given* a blurry photo · *When* OCR runs · *Then* the fields stay empty with "We could not read the document, please fill in the fields", and the user can still submit.

**2.6 Expiry alerts**
- **Success** · *Given* an insurance expires in 30 days · *When* the daily command runs · *Then* the driver receives one e-mail, and another one 7 days before expiry.
- **Failure (guard)** · *Given* the command runs twice on the same day · *When* the threshold was already notified · *Then* no duplicate e-mail is sent. An expired document sets the vehicle to `DOCUMENTS_EXPIRED` and the driver cannot publish with it.

**2.7 Plate format check**
- **Success** · *Given* the plate `123 TUN 4567` · *When* the form is validated · *Then* it is accepted.
- **Failure** · *Given* the plate `123 4567` · *When* the form is validated · *Then* "Invalid Tunisian plate format" is shown and the vehicle is not saved.

**2.8 Limit of 3 vehicles**
- **Success** · *Given* Karim has 2 vehicles · *When* he adds a third · *Then* it is saved.
- **Failure** · *Given* Karim already has 3 vehicles · *When* he tries to add a fourth (button or direct URL) · *Then* "Maximum 3 vehicles" is shown and nothing is saved.

**2.9 Renew documents**
- **Success** · *Given* Karim's insurance is `EXPIRED` · *When* he uploads a new one with a future expiry date · *Then* the vehicle becomes `PENDING` and, once the administrator accepts, `ACCEPTED` again.
- **Failure** · *Given* the new expiry date is in the past · *When* he submits · *Then* the renewal is rejected with an error message.

**2.10 Reports and exports**
- **Success** · *Given* an administrator selects "ACCEPTED" and "CSV" · *When* he exports · *Then* a CSV with the accepted vehicles is downloaded.
- **Failure** · *Given* a driver calls the export URL · *When* the request arrives · *Then* HTTP 403 is returned.

---

## 5. Tasks by sprint

Branch: `module-2-vehicles`. One Trello card per task, one owner, pull request reviewed by another member.

### Sprint 1 · Structure and CRUD
- [ ] `M2-S1-01` **Shared database design (week 1):** `Vehicle` ↔ `User`, `Vehicle` ↔ `Trip`, statuses *(team)*
- [ ] `M2-S1-02` Models `Vehicle`, `Document`, the three enums, migrations · *2.1*
- [ ] `M2-S1-03` `VehicleForm` + document formset (3 uploads) · *2.1*
- [ ] `M2-S1-04` Views and templates: my vehicles, add, detail, edit, delete · *2.1, 2.3*
- [ ] `M2-S1-05` Limit of 3 vehicles (form + server check) · *2.8*
- [ ] `M2-S1-06` Admin vehicle list and detail with documents · *2.4*
- [ ] `M2-S1-07` Admin accept and refuse with reason, status change · *2.2*
- [ ] `M2-S1-08` Promotion to driver on first accepted vehicle (calls module 1) · *2.2*
- [ ] `M2-S1-09` Permissions: owner-only querysets, admin-only views · *all*

### Sprint 2 · Business features
- [ ] `M2-S2-01` `validate_tunisian_plate` + unit tests with valid and invalid plates · *2.7*
- [ ] `M2-S2-02` `validate_document_file` (type JPG/PNG/PDF, 5 MB) · *2.1*
- [ ] `M2-S2-03` Secure document download view (owner or admin) · *2.1*
- [ ] `M2-S2-04` E-mail "vehicle accepted / refused (with reason)" · *2.2*
- [ ] `M2-S2-05` Command `send_expiry_alerts` (30 and 7 days, no duplicates, expiry → `DOCUMENTS_EXPIRED`) · *2.6*
- [ ] `M2-S2-06` Renewal flow (`/renew/`, back to `PENDING`) · *2.9*
- [ ] `M2-S2-07` Block deletion when a trip uses the vehicle (hook with module 3) · *2.3*
- [ ] `M2-S2-08` Admin search, filters, pagination · *2.4*
- [ ] `M2-S2-09` PDF, CSV, Excel exports · *2.10*
- [ ] `M2-S2-10` Tests: model, form, view and permission tests · *2.1–2.9*

### Sprint 3 · Artificial intelligence
- [ ] `M2-S3-01` Choose and install the OCR engine, test on real Tunisian documents *(spike)* · *2.5*
- [ ] `M2-S3-02` `ai.read_document()` for license, registration, insurance · *2.5*
- [ ] `M2-S3-03` AJAX pre-fill in the add-vehicle form, editable fields · *2.5*
- [ ] `M2-S3-04` Fallback when OCR fails; show original file to the admin · *2.5*
- [ ] `M2-S3-05` Accuracy check on a sample set, note the result in the report · *2.5*
- [ ] `M2-S3-06` Bug fixes, final tests, live demo of "add vehicle then validate it" *(team)*

---

## 6. Interfaces with the other modules

| Other module | What it takes from here | What it gives back |
|---|---|---|
| 1 · Users | — | sets `user_type = DRIVER`, `became_driver_at` on first accepted vehicle |
| 3 · Trips | `Vehicle` (must be `ACCEPTED`, `seats`) | blocks vehicle deletion while trips use it |
| Admin dashboard | vehicle counts by status | — |

## 7. Definition of done

- Pull request reviewed and merged to `main`.
- Tests pass for validators, status transitions, permissions (owner vs other user vs admin).
- Uploaded files validated on the server, never only in the browser.
- Works on mobile; uploads usable from a phone camera.
- Trello card in *Done* and demonstrated at the sprint review.
