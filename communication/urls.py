from django.urls import path

from . import views

app_name = "communication"

urlpatterns = [
    path("", views.index, name="index"),
    path("guest/change/", views.change_guest, name="change_guest"),
    path("chat/", views.conversation_list, name="conversation_list"),
    path("chat/new/", views.create_conversation, name="create_conversation"),
    path(
        "chat/join/<str:invite_code>/",
        views.join_conversation,
        name="join_conversation",
    ),
    path(
        "chat/<int:conversation_id>/",
        views.conversation_detail,
        name="conversation_detail",
    ),
    path(
        "chat/<int:conversation_id>/messages/",
        views.poll_messages,
        name="poll_messages",
    ),
    path(
        "chat/<int:conversation_id>/messages/older/",
        views.load_older_messages,
        name="load_older_messages",
    ),
    path(
        "chat/<int:conversation_id>/typing/",
        views.typing_status,
        name="typing_status",
    ),
    path(
        "chat/<int:conversation_id>/voice-call/",
        views.voice_call_action,
        name="voice_call_action",
    ),
    path(
        "chat/<int:conversation_id>/voice-call/state/",
        views.voice_call_state,
        name="voice_call_state",
    ),
    path(
        "chat/voice-calls/incoming/",
        views.incoming_voice_calls_state,
        name="incoming_voice_calls_state",
    ),
    path(
        "chat/<int:conversation_id>/send/",
        views.send_message,
        name="send_message",
    ),
    path(
        "chat/messages/<int:message_id>/reaction/",
        views.message_reaction,
        name="message_reaction",
    ),
    path(
        "chat/messages/<int:message_id>/edit/",
        views.message_edit,
        name="message_edit",
    ),
    path(
        "chat/messages/<int:message_id>/pin/",
        views.message_pin,
        name="message_pin",
    ),
    path(
        "chat/messages/<int:message_id>/attachment/",
        views.message_attachment,
        name="message_attachment",
    ),
    path(
        "chat/messages/<int:message_id>/delete/",
        views.message_delete,
        name="message_delete",
    ),
    path(
        "trips/<int:trip_id>/review/<int:user_id>/",
        views.review_create,
        name="review_create",
    ),
    path("reviews/<int:review_id>/edit/", views.review_update, name="review_update"),
    path(
        "reviews/<int:review_id>/delete/",
        views.review_delete,
        name="review_delete",
    ),
    path("users/<int:user_id>/reviews/", views.user_reviews, name="user_reviews"),
    path("manage/reviews/", views.admin_review_list, name="admin_review_list"),
    path(
        "manage/reviews/<int:review_id>/delete/",
        views.admin_review_delete,
        name="admin_review_delete",
    ),
    path(
        "manage/reviews/export/csv/",
        views.admin_review_export_csv,
        name="admin_review_export_csv",
    ),
]
