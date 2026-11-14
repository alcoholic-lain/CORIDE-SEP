from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Conversation(models.Model):
    class CloseReason(models.TextChoices):
        CANCELLED = "CANCELLED", "Reservation cancelled"
        REFUSED = "REFUSED", "Reservation refused"
        EXPIRED = "EXPIRED", "Conversation expired"
        MANUAL = "MANUAL", "Closed by staff"

    reservation_reference = models.CharField(max_length=100, unique=True)
    trip_reference = models.CharField(max_length=100, db_index=True)
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passenger_conversations",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_conversations",
    )
    departure_at = models.DateTimeField()
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(
        max_length=10,
        choices=CloseReason.choices,
        blank=True,
    )
    trip_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(passenger=F("driver")),
                name="communication_conversation_distinct_participants",
            ),
        ]

    def __str__(self):
        return f"Conversation for reservation {self.reservation_reference}"

    @property
    def is_open(self):
        return (
            self.closed_at is None
            and timezone.now() < self.departure_at + timedelta(hours=24)
        )

    def includes(self, user):
        return user.pk in (self.passenger_id, self.driver_id)

    def clean(self):
        if self.passenger_id and self.passenger_id == self.driver_id:
            raise ValidationError("A conversation must have two different participants.")

    def close(self, reason):
        if reason not in self.CloseReason.values:
            raise ValidationError({"close_reason": "Choose a valid close reason."})
        if self.closed_at is None:
            self.closed_at = timezone.now()
            self.close_reason = reason
            self.save(update_fields=["closed_at", "close_reason"])


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_messages",
    )
    content = models.TextField(max_length=1000)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(content=""),
                name="communication_message_not_empty",
            ),
        ]

    def __str__(self):
        return f"Message {self.pk} in conversation {self.conversation_id}"

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def clean(self):
        errors = {}
        if not self.content or not self.content.strip():
            errors["content"] = "Message cannot be empty."
        elif len(self.content) > 1000:
            errors["content"] = "Message cannot exceed 1000 characters."
        if self.conversation_id and self.sender_id and not self.conversation.includes(self.sender):
            errors["sender"] = "Only conversation participants may send messages."
        if errors:
            raise ValidationError(errors)


class Review(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    trip_reference = models.CharField(max_length=100, db_index=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_reviews_written",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_reviews_received",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=500, blank=True)
    review_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-review_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_reference", "reviewer", "target"],
                name="communication_one_review_per_person_trip",
            ),
            models.CheckConstraint(
                condition=~Q(reviewer=F("target")),
                name="communication_no_self_review",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="communication_review_rating_range",
            ),
        ]

    def __str__(self):
        return f"{self.rating}/5 review by {self.reviewer_id} for {self.target_id}"

    def clean(self):
        errors = {}
        if self.reviewer_id and self.target_id and self.reviewer_id == self.target_id:
            errors["target"] = "You cannot review yourself."
        if self.conversation_id:
            conversation = self.conversation
            if self.trip_reference and self.trip_reference != conversation.trip_reference:
                errors["trip_reference"] = "Review trip does not match the conversation."
            if not conversation.trip_completed_at:
                errors["conversation"] = "Reviews are available after the trip is completed."
            if self.reviewer_id and self.target_id and {
                self.reviewer_id,
                self.target_id,
            } != {conversation.passenger_id, conversation.driver_id}:
                errors["target"] = "Only trip participants may review each other."
        if self.comment and len(self.comment) > 500:
            errors["comment"] = "Comment cannot exceed 500 characters."
        if errors:
            raise ValidationError(errors)
