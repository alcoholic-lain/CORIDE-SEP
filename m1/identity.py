import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.utils import timezone

from .models import CommunicationParticipant


def participant_identity_q(field_name, participant):
    if participant.is_guest:
        return Q(
            **{
                f"{field_name}__user__isnull": True,
                f"{field_name}__display_name__iexact": participant.display_name,
            }
        )
    return Q(**{f"{field_name}_id": participant.pk})


def guest_mode_enabled():
    value = getattr(
        settings,
        "COMMUNICATION_GUEST_MODE",
        os.environ.get("KIZUNA_M1_GUEST_MODE", "true"),
    )
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        "COMMUNICATION_GUEST_MODE must be a boolean or a boolean-like string."
    )


def get_request_participant(request, *, display_name=None):
    if request.user.is_authenticated:
        participant, _ = CommunicationParticipant.objects.get_or_create(
            user=request.user,
            defaults={
                "display_name": request.user.get_full_name()
                or request.user.get_username()
            },
        )
        return participant

    if not guest_mode_enabled():
        return None

    session_key = request.session.session_key
    if not session_key:
        return None

    participant = CommunicationParticipant.objects.filter(
        session_key=session_key
    ).first()
    if participant is None:
        return None

    if display_name and participant.display_name != display_name:
        participant.display_name = display_name
        participant.save(update_fields=["display_name"])
    return participant


def create_guest_participant(request, display_name):
    if not guest_mode_enabled():
        return None
    session_key = request.session.session_key
    participant = (
        CommunicationParticipant.objects.filter(session_key=session_key).first()
        if session_key
        else None
    )
    if participant is None:
        if session_key:
            request.session.cycle_key()
        else:
            request.session.create()
        participant = CommunicationParticipant.objects.create(
            session_key=request.session.session_key,
            display_name=display_name,
        )
    elif participant.display_name != display_name:
        participant.display_name = display_name
        participant.save(update_fields=["display_name"])
    participant.last_seen_at = timezone.now()
    participant.save(update_fields=["last_seen_at"])
    return participant
