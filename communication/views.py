import csv
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    GuestNameForm,
    MessageEditForm,
    MessageForm,
    NewConversationForm,
    ReviewForm,
)
from .identity import (
    create_guest_participant,
    get_request_participant,
    guest_mode_enabled,
    participant_identity_q,
)
from .models import (
    CommunicationParticipant,
    Conversation,
    ConversationMembership,
    ConversationTypingStatus,
    Message,
    MessageRead,
    MessageReaction,
    Review,
)
from .services import create_message, delete_message, edit_message


def _csv_cell(value):
    value = str(value)
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def _safe_next(request, candidate, default):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def _participant_or_redirect(request):
    participant = get_request_participant(request)
    if participant is not None:
        return participant, None
    query = urlencode({"next": request.get_full_path()})
    return None, redirect(f"{reverse('communication:index')}?{query}")


def _reaction_summaries(reactions, participant):
    rows = (
        reactions.values("message_id", "emoji")
        .annotate(
            count=Count("pk"),
            mine=Count(
                "pk",
                filter=participant_identity_q("participant", participant),
            ),
        )
        .order_by("message_id", "emoji")
    )
    summaries = {}
    for row in rows:
        summaries.setdefault(row["message_id"], []).append(
            {
                "emoji": row["emoji"],
                "count": row["count"],
                "reacted": bool(row["mine"]),
            }
        )
    return summaries


def _unread_messages(conversation, participant):
    read_receipts = MessageRead.objects.filter(
        participant_identity_q("participant", participant),
        message_id=OuterRef("pk"),
    )
    return (
        conversation.messages.exclude(
            participant_identity_q("sender_participant", participant)
        )
        .annotate(read_by_participant=Exists(read_receipts))
        .filter(read_by_participant=False)
    )


def _message_attachment(message):
    if message.is_deleted or not message.attachment:
        return None
    return {
        "url": reverse(
            "communication:message_attachment",
            args=[message.pk],
        ),
        "name": message.attachment_name,
        "content_type": message.attachment_content_type,
        "size": message.attachment_size,
    }


def _reply_summary(message):
    if message is None:
        return None
    return {
        "id": message.pk,
        "sender": message.sender_participant.display_label,
        "content": (
            "Message deleted"
            if message.is_deleted
            else message.content or "Attachment"
        )[:160],
    }


def _message_payload(message, participant):
    is_mine = message.sender_participant.matches_identity(participant)
    return {
        "id": message.pk,
        "sender": message.sender_participant.display_label,
        "sender_id": message.sender_participant_id,
        "is_mine": is_mine,
        "content": "Message deleted" if message.is_deleted else message.content,
        "deleted": message.is_deleted,
        "sent_at": message.sent_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "pinned": message.pinned_at is not None,
        "reply": _reply_summary(message.reply_to),
        "attachment": _message_attachment(message),
        "delete_url": reverse(
            "communication:message_delete",
            args=[message.pk],
        )
        if is_mine and not message.is_deleted
        else None,
        "edit_url": reverse(
            "communication:message_edit",
            args=[message.pk],
        )
        if is_mine and not message.is_deleted
        else None,
        "pin_url": reverse(
            "communication:message_pin",
            args=[message.pk],
        )
        if not message.is_deleted
        else None,
        "reaction_url": reverse(
            "communication:message_reaction",
            args=[message.pk],
        )
        if not message.is_deleted
        else None,
    }


def _is_online(participant):
    return bool(
        participant
        and participant.last_seen_at >= timezone.now() - timedelta(minutes=1)
    )


def index(request):
    participant = get_request_participant(request)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    form = GuestNameForm(request.POST or None)

    if request.method == "POST":
        if request.user.is_authenticated:
            participant = get_request_participant(request)
        elif guest_mode_enabled() and form.is_valid():
            participant = create_guest_participant(
                request,
                form.cleaned_data["display_name"],
            )
        elif not guest_mode_enabled():
            form.add_error(None, "Guest access is disabled. Sign in to continue.")

        if participant is not None:
            destination = _safe_next(
                request,
                next_url,
                reverse("communication:conversation_list"),
            )
            return redirect(destination)
    elif participant is not None:
        destination = _safe_next(
            request,
            next_url,
            reverse("communication:conversation_list"),
        )
        return redirect(destination)

    return render(
        request,
        "communication/index.html",
        {
            "guest_mode_enabled": guest_mode_enabled(),
            "name_form": form,
            "next_url": next_url,
            "participant": participant,
        },
    )


def conversation_list(request):
    participant, response = _participant_or_redirect(request)
    if response:
        return response

    query = request.GET.get("q", "").strip()[:120]
    if participant.is_guest:
        member_identity = Q(
            participants__user__isnull=True,
            participants__display_name__iexact=participant.display_name,
        )
    else:
        member_identity = Q(participants__pk=participant.pk)
    read_receipts = MessageRead.objects.filter(
        participant_identity_q("participant", participant),
        message_id=OuterRef("messages__pk"),
    )
    conversations = (
        Conversation.objects.filter(
            participant_identity_q("participant_one", participant)
            | participant_identity_q("participant_two", participant)
            | member_identity
        )
        .select_related("participant_one", "participant_two")
        .prefetch_related("participants")
        .annotate(
            unread_count=Count(
                "messages",
                filter=~participant_identity_q(
                    "messages__sender_participant",
                    participant,
                )
                & ~Exists(read_receipts),
                distinct=True,
            )
        )
    )
    if query:
        conversations = conversations.filter(
            Q(title__icontains=query)
            | Q(participants__display_name__icontains=query)
            | Q(participants__user__username__icontains=query)
            | Q(participants__user__first_name__icontains=query)
            | Q(participants__user__last_name__icontains=query)
            | Q(participant_one__display_name__icontains=query)
            | Q(participant_two__display_name__icontains=query)
            | Q(participant_one__user__username__icontains=query)
            | Q(participant_one__user__first_name__icontains=query)
            | Q(participant_one__user__last_name__icontains=query)
            | Q(participant_two__user__username__icontains=query)
            | Q(participant_two__user__first_name__icontains=query)
            | Q(participant_two__user__last_name__icontains=query)
        )
    conversations = conversations.distinct()
    for conversation in conversations:
        members = list(conversation.participants.all())
        if not members:
            members = [conversation.participant_one]
            if conversation.participant_two_id is not None:
                members.append(conversation.participant_two)
        other_participants = []
        for member in members:
            if member.matches_identity(participant) or any(
                member.matches_identity(existing) for existing in other_participants
            ):
                continue
            other_participants.append(member)
        conversation.other_participants = other_participants
    return render(
        request,
        "communication/conversation_list.html",
        {
            "conversations": conversations,
            "participant": participant,
            "search_query": query,
        },
    )


def create_conversation(request):
    participant, response = _participant_or_redirect(request)
    if response:
        return response

    form = NewConversationForm(request.POST or None, participant=participant)
    if request.method == "POST" and form.is_valid():
        guests = list(form.cleaned_data["guests"])
        with transaction.atomic():
            conversation = Conversation.objects.create(
                participant_one=participant,
                participant_two=guests[0] if guests else None,
                passenger=participant.user,
                title=form.cleaned_data["title"],
            )
            conversation.participants.add(participant, *guests)
            initial_message = form.cleaned_data["initial_message"]
            if initial_message:
                create_message(
                    conversation=conversation,
                    sender=participant,
                    content=initial_message,
                )
        return redirect(
            "communication:conversation_detail",
            conversation_id=conversation.pk,
        )

    return render(
        request,
        "communication/new_conversation.html",
        {
            "form": form,
            "guest_options": form.fields["guests"].queryset,
            "participant": participant,
        },
    )


def join_conversation(request, invite_code):
    conversation = get_object_or_404(Conversation, invite_code=invite_code)
    participant = get_request_participant(request)
    name_form = GuestNameForm(request.POST or None)
    join_error = ""

    if request.method == "POST":
        if participant is None and guest_mode_enabled() and name_form.is_valid():
            participant = create_guest_participant(
                request,
                name_form.cleaned_data["display_name"],
            )
        elif participant is None and not guest_mode_enabled():
            join_error = "Guest access is disabled. Sign in to join this chat."

        if participant is not None:
            try:
                with transaction.atomic():
                    conversation = Conversation.objects.get(pk=conversation.pk)
                    if conversation.includes(participant):
                        return redirect(
                            "communication:conversation_detail",
                            conversation_id=conversation.pk,
                        )
                    if not conversation.is_open:
                        join_error = "This conversation is closed."
                    else:
                        joined = Conversation.objects.filter(
                            pk=conversation.pk,
                            participant_two__isnull=True,
                        ).exclude(
                            participant_one_id=participant.pk
                        ).update(
                            participant_two_id=participant.pk,
                            driver_id=participant.user_id,
                        )
                        if joined:
                            ConversationMembership.objects.get_or_create(
                                conversation_id=conversation.pk,
                                participant=participant,
                            )
                            return redirect(
                                "communication:conversation_detail",
                                conversation_id=conversation.pk,
                            )
                        conversation.refresh_from_db()
                        if conversation.includes(participant):
                            return redirect(
                                "communication:conversation_detail",
                                conversation_id=conversation.pk,
                            )
                        join_error = (
                            "This private chat already has two participants."
                        )
            except IntegrityError:
                join_error = "This private chat already has two participants."

    elif participant is not None:
        if conversation.includes(participant):
            return redirect(
                "communication:conversation_detail",
                conversation_id=conversation.pk,
            )
        if conversation.participant_two_id is not None:
            join_error = "This private chat already has two participants."
        elif not conversation.is_open:
            join_error = "This conversation is closed."

    return render(
        request,
        "communication/join_conversation.html",
        {
            "conversation": conversation,
            "guest_mode_enabled": guest_mode_enabled(),
            "join_error": join_error,
            "name_form": name_form,
            "already_participant": (
                conversation.includes(participant) if participant is not None else False
            ),
            "participant": participant,
        },
    )


def _conversation_for_participant(request, conversation_id):
    participant, response = _participant_or_redirect(request)
    if response:
        return None, participant, response
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "participant_one",
            "participant_two",
            "passenger",
            "driver",
        ).prefetch_related("participants"),
        pk=conversation_id,
    )
    if not conversation.includes(participant):
        raise PermissionDenied
    now = timezone.now()
    if participant.last_seen_at < now - timedelta(seconds=30):
        CommunicationParticipant.objects.filter(
            pk=participant.pk,
            last_seen_at__lt=now - timedelta(seconds=30),
        ).update(last_seen_at=now)
        participant.last_seen_at = now
    return conversation, participant, None


def _other_participants(conversation, participant):
    members = list(conversation.participants.all())
    if not members:
        members = [conversation.participant_one]
        if conversation.participant_two_id is not None:
            members.append(conversation.participant_two)
    other_participants = []
    for member in members:
        if member.matches_identity(participant) or any(
            member.matches_identity(existing) for existing in other_participants
        ):
            continue
        other_participants.append(member)
    return other_participants


def conversation_detail(request, conversation_id):
    conversation, participant, response = _conversation_for_participant(
        request,
        conversation_id,
    )
    if response:
        return response

    now = timezone.now()
    unread_ids = list(
        _unread_messages(conversation, participant).values_list("pk", flat=True)
    )
    if unread_ids:
        MessageRead.objects.bulk_create(
            [
                MessageRead(message_id=message_id, participant=participant)
                for message_id in unread_ids
            ],
            ignore_conflicts=True,
        )
        Message.objects.filter(pk__in=unread_ids, read_at__isnull=True).update(
            read_at=now
        )
    messages = list(
        conversation.messages.select_related(
            "sender_participant",
            "sender",
            "reply_to",
            "reply_to__sender_participant",
        )
    )
    reaction_summaries = _reaction_summaries(
        MessageReaction.objects.filter(
            message_id__in=[message.pk for message in messages]
        ),
        participant,
    )
    for message in messages:
        message.reaction_summaries = reaction_summaries.get(message.pk, [])
        message.is_mine = message.sender_participant.matches_identity(participant)
    message_form = MessageForm()
    if not conversation.is_open:
        message_form.fields["content"].disabled = True

    invite_url = ""
    if conversation.participant_two_id is None:
        invite_url = request.build_absolute_uri(
            reverse(
                "communication:join_conversation",
                args=[conversation.invite_code],
            )
        )

    other_participants = _other_participants(conversation, participant)
    other_participant = next(iter(other_participants), None)
    return render(
        request,
        "communication/conversation_detail.html",
        {
            "conversation": conversation,
            "chat_messages": messages,
            "message_form": message_form,
            "participant": participant,
            "other_participant": other_participant,
            "other_participants": other_participants,
            "other_participant_names": ", ".join(
                member.display_label for member in other_participants
            ),
            "other_online": any(
                _is_online(member) for member in other_participants
            ),
            "other_online_count": sum(
                _is_online(member) for member in other_participants
            ),
            "is_group_chat": len(other_participants) > 1,
            "participant_count": len(other_participants) + 1,
            "invite_url": invite_url,
            "latest_message_id": messages[-1].pk if messages else 0,
            "reaction_choices": MessageReaction.Emoji.choices,
            "pinned_messages": [
                message for message in messages if message.pinned_at is not None
            ],
        },
    )


def poll_messages(request, conversation_id):
    conversation, participant, response = _conversation_for_participant(
        request,
        conversation_id,
    )
    if response:
        return response

    try:
        after = int(request.GET.get("after", "0"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid message cursor."}, status=400)
    if after < 0:
        return JsonResponse({"error": "Invalid message cursor."}, status=400)

    messages = list(
        conversation.messages.filter(pk__gt=after)
        .select_related(
            "sender_participant",
            "reply_to",
            "reply_to__sender_participant",
        )
        .order_by("pk")[:100]
    )
    unread_ids = list(
        _unread_messages(conversation, participant)
        .filter(pk__in=[message.pk for message in messages])
        .values_list("pk", flat=True)
    )
    if unread_ids:
        MessageRead.objects.bulk_create(
            [
                MessageRead(message_id=message_id, participant=participant)
                for message_id in unread_ids
            ],
            ignore_conflicts=True,
        )
        Message.objects.filter(pk__in=unread_ids, read_at__isnull=True).update(
            read_at=timezone.now()
        )

    read_ids = list(
        conversation.messages.filter(
            participant_identity_q("sender_participant", participant),
            read_at__isnull=False,
        )
        .order_by("-pk")
        .values_list("pk", flat=True)[:100]
    )
    other_participants = _other_participants(conversation, participant)
    typing_status = (
        ConversationTypingStatus.objects.filter(
            conversation=conversation,
            updated_at__gte=timezone.now() - timedelta(seconds=5),
        )
        .exclude(participant_identity_q("participant", participant))
        .select_related("participant")
        .first()
    )
    reactions = _reaction_summaries(
        MessageReaction.objects.filter(message__conversation=conversation),
        participant,
    )
    updated_messages = (
        conversation.messages.filter(
            Q(edited_at__isnull=False) | Q(deleted_at__isnull=False)
        )
        .annotate(last_changed=Coalesce("edited_at", "deleted_at"))
        .select_related("sender_participant", "reply_to", "reply_to__sender_participant")
        .order_by("-last_changed")[:100]
    )
    pinned_ids = list(
        conversation.messages.filter(pinned_at__isnull=False).values_list(
            "pk",
            flat=True,
        )
    )
    return JsonResponse(
        {
            "is_open": conversation.is_open,
            "typing": (
                typing_status.participant.display_label if typing_status else None
            ),
            "other_participant": ", ".join(
                member.display_label for member in other_participants
            )
            or None,
            "other_online": any(
                _is_online(member) for member in other_participants
            ),
            "other_online_count": sum(
                _is_online(member) for member in other_participants
            ),
            "other_participants_count": len(other_participants),
            "participant_count": len(other_participants) + 1,
            "has_second_participant": len(other_participants) > 0,
            "read_ids": read_ids,
            "reactions": {
                str(message_id): summaries
                for message_id, summaries in reactions.items()
            },
            "pinned_ids": pinned_ids,
            "messages": [_message_payload(message, participant) for message in messages],
            "updated_messages": [
                _message_payload(message, participant)
                for message in updated_messages
            ],
        }
    )


@require_POST
def typing_status(request, conversation_id):
    conversation, participant, response = _conversation_for_participant(
        request,
        conversation_id,
    )
    if response:
        return response

    is_typing = request.POST.get("is_typing")
    if is_typing not in {"true", "false"}:
        return JsonResponse({"error": "Invalid typing status."}, status=400)
    if is_typing == "true":
        if not conversation.is_open:
            return JsonResponse(
                {"error": "This conversation is closed."},
                status=409,
            )
        ConversationTypingStatus.objects.update_or_create(
            conversation=conversation,
            participant=participant,
            defaults={"updated_at": timezone.now()},
        )
    else:
        ConversationTypingStatus.objects.filter(
            conversation=conversation,
            participant=participant,
        ).delete()
    return JsonResponse({"typing": is_typing == "true"})


@require_POST
def send_message(request, conversation_id):
    conversation, participant, response = _conversation_for_participant(
        request,
        conversation_id,
    )
    if response:
        return response
    if not conversation.is_open:
        return JsonResponse({"error": "This conversation is closed."}, status=409)

    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse(
            {"errors": form.errors.get_json_data()},
            status=400,
        )

    try:
        reply_to_id = form.cleaned_data.get("reply_to")
        reply_to = (
            get_object_or_404(
                conversation.messages.select_related("sender_participant"),
                pk=reply_to_id,
            )
            if reply_to_id
            else None
        )
        message = create_message(
            conversation=conversation,
            sender=participant,
            content=form.cleaned_data["content"],
            attachment=form.cleaned_data.get("attachment"),
            reply_to=reply_to,
        )
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)

    return JsonResponse(_message_payload(message, participant), status=201)


@require_POST
def message_reaction(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=message_id,
    )
    conversation, participant, response = _conversation_for_participant(
        request,
        message.conversation_id,
    )
    if response:
        return response
    if message.is_deleted:
        return JsonResponse(
            {"error": "Deleted messages cannot be reacted to."},
            status=409,
        )

    emoji = request.POST.get("emoji")
    if emoji not in MessageReaction.Emoji.values:
        return JsonResponse({"error": "Unsupported emoji reaction."}, status=400)

    with transaction.atomic():
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            participant=participant,
            emoji=emoji,
        )
        if not created:
            reaction.delete()

    reactions = _reaction_summaries(
        MessageReaction.objects.filter(message=message),
        participant,
    ).get(message.pk, [])
    return JsonResponse(
        {
            "message_id": message.pk,
            "removed": not created,
            "reactions": reactions,
        },
        status=201 if created else 200,
    )


@require_POST
def message_delete(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender_participant"),
        pk=message_id,
    )
    participant, response = _participant_or_redirect(request)
    if response:
        return response
    if not message.conversation.includes(participant):
        raise PermissionDenied
    delete_message(message=message, sender=participant)
    return JsonResponse({"deleted": True, "id": message.pk})


@require_POST
def message_edit(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender_participant"),
        pk=message_id,
    )
    conversation, participant, response = _conversation_for_participant(
        request,
        message.conversation_id,
    )
    if response:
        return response
    if not message.sender_participant.matches_identity(participant):
        raise PermissionDenied
    if message.is_deleted:
        return JsonResponse(
            {"error": "Deleted messages cannot be edited."},
            status=409,
        )
    if not conversation.is_open:
        return JsonResponse({"error": "This conversation is closed."}, status=409)

    form = MessageEditForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {"errors": form.errors.get_json_data()},
            status=400,
        )
    try:
        edit_message(
            message=message,
            sender=participant,
            content=form.cleaned_data["content"],
        )
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
    return JsonResponse(
        {
            "id": message.pk,
            "content": message.content,
            "edited_at": message.edited_at.isoformat(),
        }
    )


@require_POST
def message_pin(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=message_id,
    )
    conversation, participant, response = _conversation_for_participant(
        request,
        message.conversation_id,
    )
    if response:
        return response
    if message.is_deleted:
        return JsonResponse(
            {"error": "Deleted messages cannot be pinned."},
            status=409,
        )

    if message.pinned_at is None:
        message.pinned_at = timezone.now()
        message.pinned_by = participant
    else:
        message.pinned_at = None
        message.pinned_by = None
    message.save(update_fields=["pinned_at", "pinned_by"])
    return JsonResponse(
        {
            "id": message.pk,
            "pinned": message.pinned_at is not None,
            "pinned_ids": list(
                conversation.messages.filter(pinned_at__isnull=False).values_list(
                    "pk",
                    flat=True,
                )
            ),
        }
    )


@require_GET
def message_attachment(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=message_id,
    )
    _, _, response = _conversation_for_participant(
        request,
        message.conversation_id,
    )
    if response:
        return response
    if message.is_deleted or not message.attachment:
        raise Http404

    try:
        file_handle = message.attachment.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error

    content_type = message.attachment_content_type or "application/octet-stream"
    response = FileResponse(
        file_handle,
        as_attachment=not content_type.startswith("image/"),
        filename=message.attachment_name or "attachment",
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _eligible_conversation(reviewer, target, trip_id):
    return (
        Conversation.objects.filter(
            trip_reference=str(trip_id),
            trip_completed_at__isnull=False,
        )
        .filter(
            Q(participant_one=reviewer, participant_two=target)
            | Q(participant_two=reviewer, participant_one=target)
        )
        .order_by("-trip_completed_at")
        .first()
    )


def _add_model_errors(form, error):
    for field, errors in getattr(error, "message_dict", {}).items():
        form.add_error(field if field in form.fields else None, errors)
    if not getattr(error, "message_dict", None):
        form.add_error(None, error.messages)


@login_required
def review_create(request, trip_id, user_id):
    target = get_object_or_404(get_user_model(), pk=user_id)
    reviewer_participant = get_request_participant(request)
    target_participant, _ = CommunicationParticipant.objects.get_or_create(
        user=target,
        defaults={"display_name": target.get_full_name() or target.get_username()},
    )
    conversation = _eligible_conversation(
        reviewer_participant,
        target_participant,
        trip_id,
    )
    if conversation is None or target.pk == request.user.pk:
        raise PermissionDenied

    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.conversation = conversation
        review.trip_reference = str(trip_id)
        review.reviewer = request.user
        review.target = target
        review.reviewer_participant = reviewer_participant
        review.target_participant = target_participant
        try:
            review.full_clean()
            with transaction.atomic():
                review.save()
        except ValidationError as error:
            _add_model_errors(form, error)
        except IntegrityError:
            form.add_error(None, "You already reviewed this person for this trip.")
        else:
            return redirect("communication:user_reviews", user_id=target.pk)

    return render(
        request,
        "communication/review_form.html",
        {"form": form, "target": target, "trip_reference": str(trip_id)},
    )


@login_required
def review_update(request, review_id):
    review = get_object_or_404(
        Review.objects.select_related("conversation", "target"),
        pk=review_id,
    )
    participant = get_request_participant(request)
    if review.reviewer_participant_id != participant.pk:
        raise PermissionDenied

    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        updated_review = form.save(commit=False)
        try:
            updated_review.full_clean()
            updated_review.save()
        except ValidationError as error:
            _add_model_errors(form, error)
        else:
            return redirect(
                "communication:user_reviews",
                user_id=updated_review.target_id,
            )

    return render(
        request,
        "communication/review_form.html",
        {
            "form": form,
            "target": review.target_participant,
            "trip_reference": review.trip_reference,
            "editing": True,
        },
    )


@login_required
@require_POST
def review_delete(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    participant = get_request_participant(request)
    if review.reviewer_participant_id != participant.pk:
        raise PermissionDenied
    target_id = review.target_id
    review.delete()
    return redirect("communication:user_reviews", user_id=target_id)


@login_required
def user_reviews(request, user_id):
    target = get_object_or_404(get_user_model(), pk=user_id)
    target_participant, _ = CommunicationParticipant.objects.get_or_create(
        user=target,
        defaults={"display_name": target.get_full_name() or target.get_username()},
    )
    reviews = Review.objects.filter(
        target_participant=target_participant
    ).select_related("reviewer_participant")
    summary = reviews.aggregate(count=Count("pk"), average=Avg("rating"))
    average_rating = round(summary["average"], 1) if summary["count"] >= 3 else None
    return render(
        request,
        "communication/user_reviews.html",
        {
            "target": target,
            "reviews": reviews,
            "review_count": summary["count"],
            "average_rating": average_rating,
        },
    )


@login_required
def admin_review_list(request):
    if not request.user.is_staff:
        raise PermissionDenied
    paginator = Paginator(
        Review.objects.select_related(
            "reviewer_participant",
            "target_participant",
        ).order_by("-review_date"),
        25,
    )
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "communication/admin_reviews.html", {"page": page})


@login_required
@require_POST
def admin_review_delete(request, review_id):
    if not request.user.is_staff:
        raise PermissionDenied
    get_object_or_404(Review, pk=review_id).delete()
    return redirect("communication:admin_review_list")


@login_required
def admin_review_export_csv(request):
    if not request.user.is_staff:
        raise PermissionDenied
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="coride-reviews.csv"'
    writer = csv.writer(response)
    writer.writerow(["trip", "reviewer", "target", "rating", "comment", "date"])
    reviews = Review.objects.select_related(
        "reviewer_participant",
        "target_participant",
    ).order_by("-review_date")
    for review in reviews:
        writer.writerow(
            [
                _csv_cell(review.trip_reference),
                _csv_cell(review.reviewer_participant.display_label),
                _csv_cell(review.target_participant.display_label),
                review.rating,
                _csv_cell(review.comment),
                review.review_date.isoformat(),
            ]
        )
    return response
