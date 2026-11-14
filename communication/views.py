import csv

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MessageForm, ReviewForm
from .models import Conversation, Message, Review
from .services import create_message, delete_message


def _csv_cell(value):
    value = str(value)
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def index(request):
    return render(request, "communication/index.html")


def _conversation_for_user(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related("passenger", "driver"),
        pk=conversation_id,
    )
    if not conversation.includes(request.user):
        raise PermissionDenied
    return conversation


@login_required
def conversation_list(request):
    conversations = (
        Conversation.objects.filter(
            Q(passenger=request.user) | Q(driver=request.user)
        )
        .select_related("passenger", "driver")
        .annotate(
            unread_count=Count(
                "messages",
                filter=Q(messages__read_at__isnull=True)
                & ~Q(messages__sender=request.user),
            )
        )
    )
    return render(
        request,
        "communication/conversation_list.html",
        {"conversations": conversations},
    )


@login_required
def conversation_detail(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    Message.objects.filter(
        conversation=conversation,
        read_at__isnull=True,
    ).exclude(sender=request.user).update(read_at=timezone.now())
    messages = conversation.messages.select_related("sender").all()
    message_form = MessageForm()
    if not conversation.is_open:
        message_form.fields["content"].disabled = True
    return render(
        request,
        "communication/conversation_detail.html",
        {
            "conversation": conversation,
            "chat_messages": messages,
            "message_form": message_form,
        },
    )


@login_required
def poll_messages(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    try:
        after = int(request.GET.get("after", "0"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid message cursor."}, status=400)
    if after < 0:
        return JsonResponse({"error": "Invalid message cursor."}, status=400)

    messages = list(
        conversation.messages.filter(pk__gt=after)
        .select_related("sender")
        .order_by("pk")[:100]
    )
    unread_ids = [
        message.pk
        for message in messages
        if message.sender_id != request.user.pk and message.read_at is None
    ]
    if unread_ids:
        Message.objects.filter(pk__in=unread_ids).update(read_at=timezone.now())

    return JsonResponse(
        {
            "is_open": conversation.is_open,
            "messages": [
                {
                    "id": message.pk,
                    "sender": message.sender.get_full_name()
                    or message.sender.get_username(),
                    "is_mine": message.sender_id == request.user.pk,
                    "content": "Message deleted"
                    if message.is_deleted
                    else message.content,
                    "deleted": message.is_deleted,
                    "sent_at": message.sent_at.isoformat(),
                    "delete_url": reverse(
                        "communication:message_delete",
                        args=[message.pk],
                    )
                    if message.sender_id == request.user.pk and not message.is_deleted
                    else None,
                }
                for message in messages
            ],
        }
    )


@login_required
@require_POST
def send_message(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    if not conversation.is_open:
        return JsonResponse({"error": "This conversation is closed."}, status=409)

    form = MessageForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {"errors": form.errors.get_json_data()},
            status=400,
        )

    try:
        message = create_message(
            conversation=conversation,
            sender=request.user,
            content=form.cleaned_data["content"],
        )
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)

    return JsonResponse(
        {
            "id": message.pk,
            "content": message.content,
            "sent_at": message.sent_at.isoformat(),
        },
        status=201,
    )


@login_required
@require_POST
def message_delete(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=message_id,
    )
    delete_message(message=message, sender=request.user)
    return JsonResponse({"deleted": True, "id": message.pk})


def _eligible_conversation(request_user, trip_id, target_id):
    return (
        Conversation.objects.filter(
            trip_reference=str(trip_id),
            trip_completed_at__isnull=False,
        )
        .filter(
            Q(passenger=request_user, driver_id=target_id)
            | Q(driver=request_user, passenger_id=target_id)
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
    conversation = _eligible_conversation(request.user, trip_id, target.pk)
    if conversation is None or target.pk == request.user.pk:
        raise PermissionDenied

    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.conversation = conversation
        review.trip_reference = str(trip_id)
        review.reviewer = request.user
        review.target = target
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
    if review.reviewer_id != request.user.pk:
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
            "target": review.target,
            "trip_reference": review.trip_reference,
            "editing": True,
        },
    )


@login_required
@require_POST
def review_delete(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    if review.reviewer_id != request.user.pk:
        raise PermissionDenied
    target_id = review.target_id
    review.delete()
    return redirect("communication:user_reviews", user_id=target_id)


@login_required
def user_reviews(request, user_id):
    target = get_object_or_404(get_user_model(), pk=user_id)
    reviews = Review.objects.filter(target=target).select_related("reviewer")
    summary = reviews.aggregate(count=Count("pk"), average=Avg("rating"))
    average_rating = (
        round(summary["average"], 1) if summary["count"] >= 3 else None
    )
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
        Review.objects.select_related("reviewer", "target").order_by("-review_date"),
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
    for review in Review.objects.select_related("reviewer", "target").order_by(
        "-review_date"
    ):
        writer.writerow(
            [
                _csv_cell(review.trip_reference),
                _csv_cell(review.reviewer.get_username()),
                _csv_cell(review.target.get_username()),
                review.rating,
                _csv_cell(review.comment),
                review.review_date.isoformat(),
            ]
        )
    return response
