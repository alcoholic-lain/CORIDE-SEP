from datetime import timedelta
from pathlib import Path
import secrets
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


def create_invite_code():
    return secrets.token_urlsafe(24)


def message_attachment_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"communication/attachments/{uuid4().hex}{extension}"


class CommunicationParticipant(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="communication_identity",
    )
    session_key = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
    )
    display_name = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, session_key__isnull=True)
                    | Q(user__isnull=True, session_key__isnull=False)
                ),
                name="communication_participant_one_identity",
            ),
        ]

    def __str__(self):
        return self.display_label

    @property
    def is_guest(self):
        return self.user_id is None

    @property
    def display_label(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.get_username()
        return self.display_name or "Guest"

    def matches_identity(self, other):
        if self.pk is not None and self.pk == other.pk:
            return True
        return (
            self.is_guest
            and other.is_guest
            and bool(self.display_name)
            and self.display_name.casefold() == other.display_name.casefold()
        )


class Conversation(models.Model):
    class CloseReason(models.TextChoices):
        CANCELLED = "CANCELLED", "Reservation cancelled"
        REFUSED = "REFUSED", "Reservation refused"
        EXPIRED = "EXPIRED", "Conversation expired"
        MANUAL = "MANUAL", "Closed by staff"

    reservation_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    trip_reference = models.CharField(max_length=100, db_index=True, blank=True, default="")
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="passenger_conversations",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="driver_conversations",
    )
    participant_one = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="conversations_as_first",
    )
    participant_two = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conversations_as_second",
    )
    title = models.CharField(max_length=120, blank=True, default="")
    invite_code = models.CharField(
        max_length=40,
        unique=True,
    )
    departure_at = models.DateTimeField(null=True, blank=True)
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
            models.CheckConstraint(
                condition=Q(participant_two__isnull=True)
                | ~Q(participant_one=F("participant_two")),
                name="communication_room_distinct_participants",
            ),
        ]

    def __str__(self):
        return self.title or f"Conversation {self.pk or ''}".strip()

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = create_invite_code()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.closed_at is None and (
            self.departure_at is None
            or timezone.now() < self.departure_at + timedelta(hours=24)
        )

    def includes(self, participant):
        participant_ids = (self.participant_one_id, self.participant_two_id)
        if participant.pk is not None and participant.pk in participant_ids:
            return True
        if not participant.is_guest or not participant.display_name:
            return False
        return CommunicationParticipant.objects.filter(
            pk__in=participant_ids,
            user__isnull=True,
            display_name__iexact=participant.display_name,
        ).exists()

    def clean(self):
        if self.passenger_id and self.passenger_id == self.driver_id:
            raise ValidationError("A conversation must have two different participants.")
        if (
            self.participant_one_id
            and self.participant_one_id == self.participant_two_id
        ):
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
        null=True,
        blank=True,
        related_name="communication_messages",
    )
    sender_participant = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField(max_length=1000, blank=True)
    attachment = models.FileField(
        upload_to=message_attachment_path,
        blank=True,
        max_length=255,
    )
    attachment_name = models.CharField(max_length=255, blank=True, default="")
    attachment_content_type = models.CharField(max_length=100, blank=True, default="")
    attachment_size = models.PositiveIntegerField(default=0)
    has_attachment = models.BooleanField(default=False)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_by = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pinned_messages",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(content="") | Q(has_attachment=True),
                name="communication_message_content_or_attachment",
            ),
        ]

    def __str__(self):
        return f"Message {self.pk} in conversation {self.conversation_id}"

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def clean(self):
        errors = {}
        if not (self.content or "").strip() and not self.has_attachment:
            errors["content"] = "Add a message or an attachment."
        elif len(self.content or "") > 1000:
            errors["content"] = "Message cannot exceed 1000 characters."
        if (
            self.conversation_id
            and self.sender_participant_id
            and not self.conversation.includes(self.sender_participant)
        ):
            errors["sender_participant"] = (
                "Only conversation participants may send messages."
            )
        if (
            self.reply_to_id
            and self.conversation_id
            and self.reply_to.conversation_id != self.conversation_id
        ):
            errors["reply_to"] = "Replies must be in the same conversation."
        if errors:
            raise ValidationError(errors)


class ConversationTypingStatus(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="typing_statuses",
    )
    participant = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="typing_statuses",
    )
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "participant"],
                name="communication_unique_typing_status",
            ),
        ]


class MessageReaction(models.Model):
    class Emoji(models.TextChoices):
        LIKE = "👍", "Like"
        LOVE = "❤️", "Love"
        LAUGH = "😂", "Laugh"
        WOW = "😮", "Wow"
        SAD = "😢", "Sad"
        CELEBRATE = "🎉", "Celebrate"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    participant = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="message_reactions",
    )
    emoji = models.CharField(max_length=8, choices=Emoji.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "participant", "emoji"],
                name="communication_unique_message_reaction",
            ),
        ]


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
        null=True,
        blank=True,
        related_name="communication_reviews_written",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="communication_reviews_received",
    )
    reviewer_participant = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    target_participant = models.ForeignKey(
        CommunicationParticipant,
        on_delete=models.CASCADE,
        related_name="reviews_received",
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
            models.UniqueConstraint(
                fields=["trip_reference", "reviewer_participant", "target_participant"],
                name="communication_participant_review_unique",
            ),
            models.CheckConstraint(
                condition=~Q(reviewer_participant=F("target_participant")),
                name="communication_no_self_participant_review",
            ),
        ]

    def __str__(self):
        return (
            f"{self.rating}/5 review by {self.reviewer_participant} "
            f"for {self.target_participant}"
        )

    def clean(self):
        errors = {}
        if (
            self.reviewer_participant_id
            and self.reviewer_participant_id == self.target_participant_id
        ):
            errors["target"] = "You cannot review yourself."
        if self.conversation_id:
            conversation = self.conversation
            if self.trip_reference and self.trip_reference != conversation.trip_reference:
                errors["trip_reference"] = "Review trip does not match the conversation."
            if not conversation.trip_completed_at:
                errors["conversation"] = "Reviews are available after the trip is completed."
            if self.reviewer_participant_id and self.target_participant_id and {
                self.reviewer_participant_id,
                self.target_participant_id,
            } != {conversation.participant_one_id, conversation.participant_two_id}:
                errors["target"] = "Only trip participants may review each other."
        if self.comment and len(self.comment) > 500:
            errors["comment"] = "Comment cannot exceed 500 characters."
        if errors:
            raise ValidationError(errors)
