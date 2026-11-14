from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CommunicationParticipant, Conversation, Message
from .moderation import is_blocked


@transaction.atomic
def open_conversation(
    *,
    reservation_reference,
    trip_reference,
    passenger,
    driver,
    departure_at,
):
    """Create or return the conversation after a reservation is accepted."""
    if passenger.pk == driver.pk:
        raise ValidationError("A passenger cannot open a conversation with themselves.")

    reservation_reference = str(reservation_reference)
    trip_reference = str(trip_reference)
    passenger_participant, _ = CommunicationParticipant.objects.get_or_create(
        user=passenger,
        defaults={
            "display_name": passenger.get_full_name() or passenger.get_username()
        },
    )
    driver_participant, _ = CommunicationParticipant.objects.get_or_create(
        user=driver,
        defaults={"display_name": driver.get_full_name() or driver.get_username()},
    )
    conversation, created = Conversation.objects.get_or_create(
        reservation_reference=reservation_reference,
        defaults={
            "trip_reference": trip_reference,
            "passenger": passenger,
            "driver": driver,
            "participant_one": passenger_participant,
            "participant_two": driver_participant,
            "departure_at": departure_at,
        },
    )
    if not created and (
        conversation.trip_reference != trip_reference
        or conversation.passenger_id != passenger.pk
        or conversation.driver_id != driver.pk
    ):
        raise ValidationError(
            "Reservation reference is already linked to a different conversation."
        )
    return conversation


def close_conversation(reservation_reference, reason):
    try:
        conversation = Conversation.objects.get(
            reservation_reference=str(reservation_reference)
        )
    except Conversation.DoesNotExist:
        return False
    conversation.close(reason)
    return True


def mark_trip_completed(trip_reference, completed_at=None):
    """Called by the trip/reservation integration when a trip is completed."""
    return Conversation.objects.filter(
        trip_reference=str(trip_reference),
        trip_completed_at__isnull=True,
    ).update(trip_completed_at=completed_at or timezone.now())


def create_message(*, conversation, sender, content):
    if not conversation.includes(sender):
        raise PermissionDenied
    if not conversation.is_open:
        raise ValidationError("This conversation is closed.")

    content = content.strip()
    if not content:
        raise ValidationError({"content": "Message cannot be empty."})
    if len(content) > 1000:
        raise ValidationError({"content": "Message cannot exceed 1000 characters."})
    if is_blocked(content):
        raise ValidationError({"content": "Message not sent. Please rephrase it."})

    message = Message(
        conversation=conversation,
        sender=sender.user,
        sender_participant=sender,
        content=content,
    )
    message.full_clean()
    message.save()
    return message


def delete_message(*, message, sender):
    if message.sender_participant_id != sender.pk:
        raise PermissionDenied
    if message.deleted_at is None:
        message.deleted_at = timezone.now()
        message.save(update_fields=["deleted_at"])
    return message
