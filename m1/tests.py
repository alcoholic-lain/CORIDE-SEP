import json
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import (
    CommunicationParticipant,
    Conversation,
    ConversationTypingStatus,
    Message,
    MessageReaction,
    Review,
    VoiceCall,
    VoiceCallSignal,
)
from .moderation import is_blocked
from .services import mark_trip_completed, open_conversation


class CommunicationTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.passenger = user_model.objects.create_user(
            username="passenger",
            password="test-password",
        )
        self.driver = user_model.objects.create_user(
            username="driver",
            password="test-password",
        )
        self.outsider = user_model.objects.create_user(
            username="outsider",
            password="test-password",
        )
        self.conversation = open_conversation(
            reservation_reference="reservation-1",
            trip_reference="1",
            passenger=self.passenger,
            driver=self.driver,
            departure_at=timezone.now() + timedelta(days=1),
        )
        self.passenger_participant = CommunicationParticipant.objects.get(
            user=self.passenger
        )
        self.driver_participant = CommunicationParticipant.objects.get(
            user=self.driver
        )


class ConversationTests(CommunicationTestCase):
    def test_module_home_and_conversation_list_render(self):
        self.client.force_login(self.passenger)

        response = self.client.get(reverse("m1:index"))
        self.assertRedirects(
            response,
            reverse("m1:conversation_list"),
            fetch_redirect_response=False,
        )
        response = self.client.get(reverse("m1:conversation_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your chats")
        self.assertContains(response, "driver")
        self.assertContains(response, 'id="incoming-call-notifications"')
        self.assertContains(response, "incoming_calls.js")

    def test_room_search_matches_titles_and_participants_without_leaking_rooms(self):
        outsider_participant, _ = CommunicationParticipant.objects.get_or_create(
            user=self.outsider,
            defaults={"display_name": self.outsider.get_username()},
        )
        matching_conversation = Conversation.objects.create(
            participant_one=self.passenger_participant,
            participant_two=outsider_participant,
            passenger=self.passenger,
            driver=self.outsider,
            title="Airport pickup",
        )
        private_conversation = Conversation.objects.create(
            participant_one=self.driver_participant,
            participant_two=outsider_participant,
            passenger=self.driver,
            driver=self.outsider,
            title="Private airport plan",
        )
        self.client.force_login(self.passenger)

        response = self.client.get(
            reverse("m1:conversation_list"),
            {"q": "airport"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Airport pickup")
        self.assertNotContains(response, "Private airport plan")
        self.assertEqual(
            [conversation.pk for conversation in response.context["conversations"]],
            [matching_conversation.pk],
        )
        self.assertNotIn(
            private_conversation.pk,
            [conversation.pk for conversation in response.context["conversations"]],
        )

        response = self.client.get(
            reverse("m1:conversation_list"),
            {"q": "driver"},
        )
        self.assertContains(response, "driver")

    def test_open_conversation_is_idempotent_and_rejects_mismatched_reference(self):
        conversation = open_conversation(
            reservation_reference="reservation-1",
            trip_reference="1",
            passenger=self.passenger,
            driver=self.driver,
            departure_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(conversation.pk, self.conversation.pk)

        with self.assertRaises(ValidationError):
            open_conversation(
                reservation_reference="reservation-1",
                trip_reference="another-trip",
                passenger=self.passenger,
                driver=self.driver,
                departure_at=timezone.now() + timedelta(days=1),
            )

    def test_participant_can_open_chat_and_mark_messages_read(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Meet by the station",
        )
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse(
                "m1:conversation_detail",
                args=[self.conversation.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meet by the station")
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_conversation_detail_loads_latest_page_and_marks_only_loaded_messages_read(self):
        messages = [
            Message.objects.create(
                conversation=self.conversation,
                sender=self.passenger,
                sender_participant=self.passenger_participant,
                content=f"History message {index}",
            )
            for index in range(12)
        ]
        self.client.force_login(self.driver)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse(
                    "m1:conversation_detail",
                    args=[self.conversation.pk],
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "conversation_detail.js")
        auth_user_queries = [
            query
            for query in queries
            if 'from "auth_user"' in query["sql"].lower()
        ]
        self.assertLessEqual(len(auth_user_queries), 3)
        self.assertEqual(
            [message.pk for message in response.context["chat_messages"]],
            [message.pk for message in messages[-10:]],
        )
        self.assertTrue(response.context["has_older_messages"])
        for message in messages[:2]:
            message.refresh_from_db()
            self.assertIsNone(message.read_at)

        older_response = self.client.get(
            reverse(
                "m1:load_older_messages",
                args=[self.conversation.pk],
            ),
            {"before": messages[-10].pk},
        )

        self.assertEqual(older_response.status_code, 200)
        older_data = older_response.json()
        self.assertEqual(
            [message["id"] for message in older_data["messages"]],
            [message.pk for message in messages[:2]],
        )
        self.assertFalse(older_data["has_older"])
        for message in messages[:2]:
            message.refresh_from_db()
            self.assertIsNotNone(message.read_at)

    def test_older_message_cursor_must_be_positive_integer(self):
        self.client.force_login(self.driver)
        older_url = reverse(
            "m1:load_older_messages",
            args=[self.conversation.pk],
        )

        for cursor in ("", "not-a-number", "0", "-1"):
            with self.subTest(cursor=cursor):
                response = self.client.get(older_url, {"before": cursor})
                self.assertEqual(response.status_code, 400)

    def test_only_participants_can_view_and_send_messages(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse(
                "m1:conversation_detail",
                args=[self.conversation.pk],
            )
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("m1:send_message", args=[self.conversation.pk]),
            {"content": "Hello"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.exists())

    def test_message_send_poll_and_read_receipt(self):
        self.client.force_login(self.passenger)
        response = self.client.post(
            reverse("m1:send_message", args=[self.conversation.pk]),
            {"content": "  Hello from the trip  "},
        )

        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual(message.content, "Hello from the trip")

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], message.content)
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_typing_status_is_visible_to_the_other_participant_and_can_be_cleared(self):
        typing_url = reverse(
            "m1:typing_status",
            args=[self.conversation.pk],
        )
        self.client.force_login(self.passenger)

        response = self.client.post(typing_url, {"is_typing": "sometimes"})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(typing_url, {"is_typing": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ConversationTypingStatus.objects.count(), 1)

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )
        self.assertEqual(
            response.json()["typing"],
            self.passenger_participant.display_label,
        )

        ConversationTypingStatus.objects.filter(
            conversation=self.conversation,
            participant=self.passenger_participant,
        ).update(updated_at=timezone.now() - timedelta(seconds=10))
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )
        self.assertIsNone(response.json()["typing"])

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(typing_url, {"is_typing": "true"}).status_code,
            403,
        )

        self.client.force_login(self.passenger)
        self.client.post(typing_url, {"is_typing": "true"})
        self.assertEqual(
            self.client.post(typing_url, {"is_typing": "false"}).status_code,
            200,
        )
        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )
        self.assertIsNone(response.json()["typing"])

    def test_message_reactions_toggle_and_sync_through_polling(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Meet at the station",
        )
        reaction_url = reverse(
            "m1:message_reaction",
            args=[message.pk],
        )
        self.client.force_login(self.passenger)

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(reaction_url, {"emoji": "👍"}).status_code,
            403,
        )
        self.client.force_login(self.passenger)
        response = self.client.post(reaction_url, {"emoji": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MessageReaction.objects.exists())

        response = self.client.post(reaction_url, {"emoji": "👍"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["reactions"],
            [{"emoji": "👍", "count": 1, "reacted": True}],
        )

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )
        self.assertEqual(
            response.json()["reactions"][str(message.pk)],
            [{"emoji": "👍", "count": 1, "reacted": False}],
        )

        self.client.force_login(self.passenger)
        response = self.client.post(reaction_url, {"emoji": "👍"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["removed"])
        self.assertEqual(response.json()["reactions"], [])
        self.assertFalse(MessageReaction.objects.exists())

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": message.pk, "visible": str(message.pk)},
        )
        self.assertEqual(response.json()["reactions"][str(message.pk)], [])

    def test_sender_can_edit_and_edits_sync_through_polling(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Original message",
        )
        edit_url = reverse("m1:message_edit", args=[message.pk])
        self.client.force_login(self.driver)
        self.assertEqual(
            self.client.post(edit_url, {"content": "Not my message"}).status_code,
            403,
        )

        self.client.force_login(self.passenger)
        response = self.client.post(edit_url, {"content": "Updated message"})
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.content, "Updated message")
        self.assertIsNotNone(message.edited_at)

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": message.pk},
        )
        self.assertEqual(
            response.json()["updated_messages"][0]["content"],
            "Updated message",
        )
        self.client.force_login(self.passenger)
        self.assertEqual(
            self.client.post(edit_url, {"content": "   "}).status_code,
            400,
        )

    def test_poll_syncs_reactions_and_message_state_only_for_visible_messages(self):
        old_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Older message",
        )
        visible_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Visible message",
        )
        MessageReaction.objects.create(
            message=old_message,
            participant=self.passenger_participant,
            emoji=MessageReaction.Emoji.LIKE,
        )
        MessageReaction.objects.create(
            message=visible_message,
            participant=self.passenger_participant,
            emoji=MessageReaction.Emoji.LOVE,
        )
        visible_message.pinned_at = timezone.now()
        visible_message.save(update_fields=["pinned_at"])
        outsider_participant, _ = CommunicationParticipant.objects.get_or_create(
            user=self.outsider,
            defaults={"display_name": self.outsider.get_username()},
        )
        other_conversation = Conversation.objects.create(
            participant_one=self.passenger_participant,
            participant_two=outsider_participant,
            passenger=self.passenger,
            driver=self.outsider,
        )
        foreign_message = Message.objects.create(
            conversation=other_conversation,
            sender=self.outsider,
            sender_participant=outsider_participant,
            content="Private message",
        )
        MessageReaction.objects.create(
            message=foreign_message,
            participant=outsider_participant,
            emoji=MessageReaction.Emoji.WOW,
        )
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {
                "after": visible_message.pk,
                "visible": f"{visible_message.pk},{foreign_message.pk}",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(list(data["reactions"]), [str(visible_message.pk)])
        self.assertEqual(data["pinned_ids"], [visible_message.pk])
        self.assertEqual(data["synced_ids"], [str(visible_message.pk)])
        self.assertNotIn(str(old_message.pk), data["reactions"])
        self.assertNotIn(str(foreign_message.pk), data["reactions"])
        self.assertEqual(
            self.client.get(
                reverse("m1:poll_messages", args=[self.conversation.pk]),
                {
                    "after": visible_message.pk,
                    "visible": ",".join(
                        str(message_id)
                        for message_id in range(1, 52)
                    ),
                },
            ).status_code,
            400,
        )

    def test_deleted_messages_sync_through_polling(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Remove this message",
        )
        self.client.force_login(self.passenger)
        delete_url = reverse("m1:message_delete", args=[message.pk])
        self.assertEqual(self.client.post(delete_url).status_code, 200)

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": message.pk},
        )
        updated_messages = response.json()["updated_messages"]
        self.assertEqual(len(updated_messages), 1)
        self.assertEqual(updated_messages[0]["id"], message.pk)
        self.assertTrue(updated_messages[0]["deleted"])
        self.assertEqual(updated_messages[0]["content"], "Message deleted")

    def test_replies_are_scoped_to_the_conversation_and_sync_in_poll(self):
        original = Message.objects.create(
            conversation=self.conversation,
            sender=self.driver,
            sender_participant=self.driver_participant,
            content="Where should we meet?",
        )
        other_conversation = Conversation.objects.create(
            participant_one=self.passenger_participant,
            participant_two=None,
            title="Another chat",
        )
        foreign_message = Message.objects.create(
            conversation=other_conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Private reply target",
        )
        self.client.force_login(self.passenger)
        send_url = reverse(
            "m1:send_message",
            args=[self.conversation.pk],
        )

        response = self.client.post(
            send_url,
            {"content": "At the main entrance", "reply_to": original.pk},
        )
        self.assertEqual(response.status_code, 201)
        reply = Message.objects.get(conversation=self.conversation, reply_to=original)
        self.assertEqual(reply.content, "At the main entrance")

        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": original.pk},
        )
        self.assertEqual(
            response.json()["messages"][0]["reply"],
            {
                "id": original.pk,
                "sender": self.driver_participant.display_label,
                "content": "Where should we meet?",
            },
        )
        response = self.client.post(
            send_url,
            {"content": "Cross-chat reply", "reply_to": foreign_message.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_message_pin_is_shared_and_toggleable_by_participants(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.passenger,
            sender_participant=self.passenger_participant,
            content="Pickup is at the north gate",
        )
        pin_url = reverse("m1:message_pin", args=[message.pk])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(pin_url).status_code, 403)

        self.client.force_login(self.driver)
        response = self.client.post(pin_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["pinned"])
        message.refresh_from_db()
        self.assertEqual(message.pinned_by, self.driver_participant)

        self.client.force_login(self.passenger)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )
        self.assertEqual(response.json()["pinned_ids"], [message.pk])
        response = self.client.post(pin_url)
        self.assertFalse(response.json()["pinned"])
        message.refresh_from_db()
        self.assertIsNone(message.pinned_at)

    def test_private_image_attachment_upload_download_and_type_validation(self):
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        send_url = reverse(
            "m1:send_message",
            args=[self.conversation.pk],
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.client.force_login(self.passenger)
                response = self.client.post(
                    send_url,
                    {
                        "content": "",
                        "attachment": SimpleUploadedFile(
                            "pickup.png",
                            image_bytes,
                            content_type="image/png",
                        ),
                    },
                )
                self.assertEqual(response.status_code, 201)
                message = Message.objects.get()
                self.assertTrue(message.has_attachment)
                self.assertEqual(message.attachment_content_type, "image/png")
                self.assertEqual(response.json()["attachment"]["name"], "pickup.png")

                attachment_url = reverse(
                    "m1:message_attachment",
                    args=[message.pk],
                )
                self.client.force_login(self.outsider)
                self.assertEqual(self.client.get(attachment_url).status_code, 403)

                self.client.force_login(self.driver)
                response = self.client.get(attachment_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(b"".join(response.streaming_content), image_bytes)

                self.client.force_login(self.passenger)
                invalid = self.client.post(
                    send_url,
                    {
                        "content": "",
                        "attachment": SimpleUploadedFile(
                            "not-an-image.png",
                            b"not a PNG",
                            content_type="image/png",
                        ),
                    },
                )
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(Message.objects.count(), 1)

                self.client.post(
                    reverse("m1:message_delete", args=[message.pk])
                )
                self.assertEqual(self.client.get(attachment_url).status_code, 404)

    def test_invalid_cursor_is_rejected(self):
        self.client.force_login(self.passenger)
        response = self.client.get(
            reverse("m1:poll_messages", args=[self.conversation.pk]),
            {"after": "not-a-number"},
        )
        self.assertEqual(response.status_code, 400)

    def test_closed_conversation_rejects_send_and_command_closes_expired_chat(self):
        self.conversation.departure_at = timezone.now() - timedelta(hours=25)
        self.conversation.save(update_fields=["departure_at"])
        self.client.force_login(self.passenger)

        response = self.client.post(
            reverse("m1:send_message", args=[self.conversation.pk]),
            {"content": "Too late"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Message.objects.exists())
        call_command("close_conversations")
        self.conversation.refresh_from_db()
        self.assertEqual(
            self.conversation.close_reason,
            Conversation.CloseReason.EXPIRED,
        )

    def test_only_sender_can_soft_delete_message(self):
        self.client.force_login(self.passenger)
        self.client.post(
            reverse("m1:send_message", args=[self.conversation.pk]),
            {"content": "Please remove this"},
        )
        message = Message.objects.get()
        delete_url = reverse("m1:message_delete", args=[message.pk])
        MessageReaction.objects.create(
            message=message,
            participant=self.passenger_participant,
            emoji=MessageReaction.Emoji.LIKE,
        )

        self.client.force_login(self.driver)
        self.assertEqual(self.client.post(delete_url).status_code, 403)

        self.client.force_login(self.passenger)
        self.assertEqual(self.client.post(delete_url).status_code, 200)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.content, "Please remove this")
        self.assertFalse(message.reactions.exists())

    @override_settings(COMMUNICATION_BLOCKED_TERMS=("badword",))
    def test_moderation_normalizes_obfuscation_and_uses_whole_words(self):
        self.assertTrue(is_blocked("That is b@dword!"))
        self.assertFalse(is_blocked("notbadwording"))

        self.client.force_login(self.passenger)
        response = self.client.post(
            reverse("m1:send_message", args=[self.conversation.pk]),
            {"content": "b@dword"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.exists())


class VoiceCallTests(CommunicationTestCase):
    def setUp(self):
        super().setUp()
        self.owner = Client()
        self.owner.force_login(self.passenger)
        self.guest = Client()
        self.guest.force_login(self.driver)
        self.action_url = reverse(
            "m1:voice_call_action",
            args=[self.conversation.pk],
        )
        self.state_url = reverse(
            "m1:voice_call_state",
            args=[self.conversation.pk],
        )
        self.incoming_url = reverse("m1:incoming_voice_calls_state")

    def post_action(self, client, action, **data):
        return client.post(
            self.action_url,
            json.dumps({"action": action, **data}),
            content_type="application/json",
        )

    def test_participants_can_start_join_exchange_signals_and_leave(self):
        started = self.post_action(self.owner, "start")
        self.assertEqual(started.status_code, 201)
        call = VoiceCall.objects.get(conversation=self.conversation)
        self.assertEqual(
            started.json()["call"]["participants"][0]["id"],
            self.passenger_participant.pk,
        )
        self.assertEqual(
            started.json()["call"]["started_by"],
            self.passenger_participant.pk,
        )
        self.assertTrue(started.json()["call"]["joined"])

        ringing = self.guest.get(self.state_url).json()["call"]
        self.assertEqual(
            ringing["participants"][0]["id"],
            self.passenger_participant.pk,
        )
        self.assertEqual(ringing["started_by"], self.passenger_participant.pk)
        self.assertFalse(ringing["joined"])
        self.assertFalse(ringing["previously_joined"])
        joined = self.post_action(self.guest, "join")
        self.assertEqual(joined.status_code, 200)
        self.assertTrue(joined.json()["call"]["joined"])
        self.assertTrue(joined.json()["call"]["previously_joined"])
        self.assertEqual(call.participants.count(), 2)

        signal = self.post_action(
            self.owner,
            "signal",
            recipient=self.driver_participant.pk,
            type="offer",
            payload={"type": "offer", "sdp": "test-sdp"},
        )
        self.assertEqual(signal.status_code, 201)
        self.assertTrue(
            VoiceCallSignal.objects.filter(
                call=call,
                sender=self.passenger_participant,
                recipient=self.driver_participant,
            ).exists()
        )

        synced = self.post_action(self.guest, "sync", after=0)
        self.assertEqual(synced.status_code, 200)
        self.assertEqual(synced.json()["signals"][0]["payload"]["sdp"], "test-sdp")

        self.assertEqual(self.post_action(self.owner, "leave").status_code, 200)
        call.refresh_from_db()
        self.assertIsNone(call.ended_at)
        self.assertEqual(self.post_action(self.guest, "leave").status_code, 200)
        call.refresh_from_db()
        self.assertIsNotNone(call.ended_at)

    def test_incoming_call_notifications_follow_the_recipient_across_chats(self):
        started = self.post_action(self.owner, "start")
        self.assertEqual(started.status_code, 201)
        call_id = started.json()["call"]["id"]

        caller_calls = self.owner.get(self.incoming_url).json()["calls"]
        recipient_calls = self.guest.get(self.incoming_url).json()["calls"]
        outsider = Client()
        outsider.force_login(self.outsider)
        outsider_calls = outsider.get(self.incoming_url).json()["calls"]

        self.assertEqual(caller_calls, [])
        self.assertEqual(outsider_calls, [])
        self.assertEqual(
            recipient_calls,
            [
                {
                    "id": call_id,
                    "conversation_id": self.conversation.pk,
                    "caller": self.passenger_participant.display_label,
                    "conversation_url": reverse(
                        "m1:conversation_detail",
                        args=[self.conversation.pk],
                    ),
                }
            ],
        )

        self.assertEqual(self.post_action(self.guest, "join").status_code, 200)
        self.assertEqual(self.guest.get(self.incoming_url).json()["calls"], [])

    def test_call_actions_require_a_member_and_validate_signals(self):
        outsider = Client()
        outsider.force_login(self.outsider)
        outsider_response = outsider.get(self.state_url)
        self.assertEqual(outsider_response.status_code, 403)

        self.assertEqual(
            self.post_action(self.owner, "start").status_code,
            201,
        )
        duplicate = self.post_action(self.guest, "start")
        self.assertEqual(duplicate.status_code, 409)

        invalid_signal = self.post_action(
            self.owner,
            "signal",
            recipient=self.driver_participant.pk,
            type="offer",
            payload={"sdp": "not joined"},
        )
        self.assertEqual(invalid_signal.status_code, 409)
        malformed = self.owner.post(
            self.action_url,
            "{",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)

    def test_group_chats_do_not_offer_voice_calls(self):
        group = Conversation.objects.create(
            participant_one=self.passenger_participant,
            chat_type=Conversation.ChatType.GROUP,
        )
        group.participants.add(
            self.passenger_participant,
            self.driver_participant,
        )
        group_action_url = reverse(
            "m1:voice_call_action",
            args=[group.pk],
        )
        group_state_url = reverse(
            "m1:voice_call_state",
            args=[group.pk],
        )

        state = self.owner.get(group_state_url)
        self.assertEqual(state.status_code, 200)
        self.assertFalse(state.json()["supported"])
        start = self.owner.post(
            group_action_url,
            json.dumps({"action": "start"}),
            content_type="application/json",
        )
        self.assertEqual(start.status_code, 409)
        self.assertFalse(VoiceCall.objects.filter(conversation=group).exists())


class GuestConversationTests(TestCase):
    def setUp(self):
        self.owner = Client()

    def start_guest(self, client, name):
        return client.post(
            reverse("m1:index"),
            {"display_name": name},
        )

    def test_new_chat_invite_page_has_no_picker_or_optional_fields(self):
        self.start_guest(self.owner, "Owner")
        response = self.owner.get(reverse("m1:create_conversation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private chat")
        self.assertContains(response, "Group chat")
        self.assertNotContains(response, "Chat name")
        self.assertNotContains(response, "First message")
        self.assertNotContains(response, "Choose chat contacts")
        self.assertEqual(
            list(response.context["form"].fields),
            ["chat_type"],
        )

    def test_new_chat_does_not_add_submitted_contacts_to_an_invite(self):
        self.start_guest(self.owner, "Owner")
        owner = CommunicationParticipant.objects.get(
            session_key=self.owner.session.session_key
        )
        unrelated_guest = Client()
        self.start_guest(unrelated_guest, "Unrelated")
        unrelated_participant = CommunicationParticipant.objects.get(
            session_key=unrelated_guest.session.session_key
        )

        response = self.owner.post(
            reverse("m1:create_conversation"),
            {
                "chat_type": "PRIVATE",
                "guests": [str(unrelated_participant.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get()
        self.assertEqual(conversation.participant_one, owner)
        self.assertIsNone(conversation.participant_two_id)
        self.assertEqual(conversation.participants.count(), 1)
        self.assertFalse(
            conversation.participants.filter(pk=unrelated_participant.pk).exists()
        )

    def test_creator_can_share_a_group_invite_with_multiple_guests(self):
        self.start_guest(self.owner, "Owner")
        invited_clients = [Client(), Client()]
        for client, name in zip(invited_clients, ("Sam", "Lee")):
            self.start_guest(client, name)

        response = self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "GROUP"},
        )

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get(chat_type=Conversation.ChatType.GROUP)
        self.assertEqual(conversation.participants.count(), 1)
        join_url = reverse(
            "m1:join_conversation",
            args=[conversation.invite_code],
        )
        first_client, second_client = invited_clients
        for client in (first_client, second_client):
            self.assertContains(client.get(join_url), "Join chat")
            joined = client.post(join_url)
            self.assertRedirects(
                joined,
                reverse("m1:conversation_detail", args=[conversation.pk]),
                fetch_redirect_response=False,
            )
        self.assertEqual(conversation.participants.count(), 3)
        detail = first_client.get(
            reverse("m1:conversation_detail", args=[conversation.pk])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Private group chat")

        outsider = Client()
        self.start_guest(outsider, "Outsider")
        denied = outsider.get(
            reverse(
                "m1:conversation_detail",
                args=[conversation.pk],
            )
        )
        self.assertEqual(denied.status_code, 403)

    def test_private_and_group_invites_need_no_contact_selection(self):
        self.start_guest(self.owner, "Owner")
        private_response = self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "PRIVATE"},
        )
        group_response = self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "GROUP"},
        )

        self.assertEqual(private_response.status_code, 302)
        self.assertEqual(group_response.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 2)
        self.assertEqual(
            list(
                Conversation.objects.order_by("chat_type").values_list(
                    "chat_type",
                    flat=True,
                )
            ),
            ["GROUP", "PRIVATE"],
        )
        self.assertEqual(
            [
                conversation.participants.count()
                for conversation in Conversation.objects.all()
            ],
            [1, 1],
        )

    def test_guest_can_create_invite_chat_send_and_receive_messages(self):
        response = self.start_guest(self.owner, "Alex")
        self.assertRedirects(
            response,
            reverse("m1:conversation_list"),
            fetch_redirect_response=False,
        )
        owner = CommunicationParticipant.objects.get(display_name="Alex")
        self.assertTrue(owner.is_guest)
        self.assertIsNone(owner.user_id)

        response = self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "PRIVATE"},
        )
        conversation = Conversation.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(conversation.participant_one, owner)
        self.assertIsNone(conversation.participant_two)
        self.assertFalse(Message.objects.filter(conversation=conversation).exists())

        response = self.owner.get(
            reverse(
                "m1:conversation_detail",
                args=[conversation.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Copy invite link")
        self.assertContains(response, conversation.invite_code)

        invited_client = Client()
        join_url = reverse(
            "m1:join_conversation",
            args=[conversation.invite_code],
        )
        self.assertContains(invited_client.get(join_url), "Your name")
        response = invited_client.post(join_url, {"display_name": "Sam"})
        self.assertRedirects(
            response,
            reverse(
                "m1:conversation_detail",
                args=[conversation.pk],
            ),
            fetch_redirect_response=False,
        )
        invited_client.get(
            reverse(
                "m1:conversation_detail",
                args=[conversation.pk],
            )
        )
        conversation.refresh_from_db()
        invited_participant = conversation.participant_two
        self.assertEqual(invited_participant.display_name, "Sam")

        response = invited_client.post(
            reverse("m1:send_message", args=[conversation.pk]),
            {"content": "On my way"},
        )
        self.assertEqual(response.status_code, 201)
        response = self.owner.get(
            reverse("m1:poll_messages", args=[conversation.pk]),
            {"after": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "On my way")
        self.assertFalse(response.json()["messages"][0]["is_mine"])

    def test_guest_can_return_to_name_entry_without_deleting_guest_data(self):
        self.start_guest(self.owner, "Alex")
        participant = CommunicationParticipant.objects.get(
            session_key=self.owner.session.session_key
        )
        self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "PRIVATE"},
        )
        conversation = Conversation.objects.get(participant_one=participant)

        chat_list = self.owner.get(reverse("m1:conversation_list"))
        self.assertContains(chat_list, "Change guest")

        response = self.owner.post(reverse("m1:change_guest"))
        self.assertRedirects(
            response,
            reverse("m1:index"),
            fetch_redirect_response=False,
        )
        response = self.owner.get(reverse("m1:index"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["participant"])
        self.assertIsNone(response.context["name_form"]["display_name"].value())
        self.assertTrue(
            CommunicationParticipant.objects.filter(pk=participant.pk).exists()
        )
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_guest_sessions_are_isolated_and_invite_accepts_only_one_person(self):
        self.start_guest(self.owner, "Owner")
        self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "PRIVATE"},
        )
        conversation = Conversation.objects.get()
        join_url = reverse(
            "m1:join_conversation",
            args=[conversation.invite_code],
        )

        invited_client = Client()
        invited_client.post(join_url, {"display_name": "Invitee"})
        outsider = Client()
        self.start_guest(outsider, "Outsider")

        response = outsider.get(
            reverse(
                "m1:conversation_detail",
                args=[conversation.pk],
            )
        )
        self.assertEqual(response.status_code, 403)
        response = outsider.get(reverse("m1:conversation_list"))
        self.assertEqual(list(response.context["conversations"]), [])

        response = outsider.get(join_url)
        self.assertContains(response, "already has two participants")

    def test_guest_name_reconnects_to_all_chats_with_the_same_name(self):
        first_nour = CommunicationParticipant.objects.create(
            session_key="first-nour-session",
            display_name="Nour",
        )
        second_nour = CommunicationParticipant.objects.create(
            session_key="second-nour-session",
            display_name="nour",
        )
        lain = CommunicationParticipant.objects.create(
            session_key="lain-session",
            display_name="Lain",
        )
        lamya = CommunicationParticipant.objects.create(
            session_key="lamya-session",
            display_name="Lamya",
        )
        lain_chat = Conversation.objects.create(
            participant_one=first_nour,
            participant_two=lain,
            title="Lain",
        )
        test_chat = Conversation.objects.create(
            participant_one=lamya,
            participant_two=second_nour,
            title="Test",
        )
        old_message = Message.objects.create(
            conversation=lain_chat,
            sender_participant=first_nour,
            content="Old message from Nour",
        )
        self.start_guest(self.owner, "nour")
        current_nour = CommunicationParticipant.objects.get(
            session_key=self.owner.session.session_key
        )

        response = self.owner.get(reverse("m1:conversation_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {chat.pk for chat in response.context["conversations"]},
            {lain_chat.pk, test_chat.pk},
        )
        response = self.owner.get(
            reverse("m1:conversation_detail", args=[lain_chat.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old message from Nour")
        self.assertContains(response, 'class="message message-mine"')
        self.assertEqual(response.context["chat_messages"][0].pk, old_message.pk)
        self.assertTrue(response.context["chat_messages"][0].is_mine)
        self.assertEqual(response.context["other_participant"], lain)

        response = self.owner.post(
            reverse("m1:send_message", args=[lain_chat.pk]),
            {"content": "Nour is back"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_mine"])
        self.assertEqual(
            Message.objects.get(content="Nour is back").sender_participant,
            current_nour,
        )

    @override_settings(COMMUNICATION_GUEST_MODE=False)
    def test_guest_mode_can_be_disabled(self):
        response = self.owner.post(
            reverse("m1:index"),
            {"display_name": "No access"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Guest mode is turned off")
        self.assertFalse(
            CommunicationParticipant.objects.filter(
                display_name="No access"
            ).exists()
        )

    def test_disabling_guest_mode_revokes_existing_guest_access(self):
        self.start_guest(self.owner, "Temporary guest")
        self.owner.post(
            reverse("m1:create_conversation"),
            {"chat_type": "PRIVATE"},
        )
        conversation = Conversation.objects.get()

        with override_settings(COMMUNICATION_GUEST_MODE=False):
            response = self.owner.get(
                reverse(
                    "m1:conversation_detail",
                    args=[conversation.pk],
                )
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("m1:index")))


class ReviewTests(CommunicationTestCase):
    def setUp(self):
        super().setUp()
        mark_trip_completed(self.conversation.trip_reference)

    def test_review_creation_requires_completed_trip_and_trip_participants(self):
        self.conversation.trip_completed_at = None
        self.conversation.save(update_fields=["trip_completed_at"])
        self.client.force_login(self.passenger)

        response = self.client.get(
            reverse(
                "m1:review_create",
                args=["1", self.driver.pk],
            )
        )
        self.assertEqual(response.status_code, 403)

        mark_trip_completed(self.conversation.trip_reference)
        response = self.client.post(
            reverse(
                "m1:review_create",
                args=["1", self.driver.pk],
            ),
            {"rating": "5", "comment": "Great ride"},
        )

        self.assertEqual(response.status_code, 302)
        review = Review.objects.get()
        self.assertEqual(review.reviewer, self.passenger)
        self.assertEqual(review.target, self.driver)
        self.assertEqual(review.trip_reference, "1")

    def test_duplicate_review_is_rejected(self):
        Review.objects.create(
            conversation=self.conversation,
            trip_reference=self.conversation.trip_reference,
            reviewer=self.passenger,
            target=self.driver,
            reviewer_participant=self.passenger_participant,
            target_participant=self.driver_participant,
            rating=4,
            comment="Existing review",
        )
        self.client.force_login(self.passenger)

        response = self.client.post(
            reverse(
                "m1:review_create",
                args=["1", self.driver.pk],
            ),
            {"rating": "5", "comment": "Second review"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), 1)

    def test_average_is_hidden_until_three_reviews(self):
        second_passenger = get_user_model().objects.create_user(
            username="passenger-two",
            password="test-password",
        )
        third_passenger = get_user_model().objects.create_user(
            username="passenger-three",
            password="test-password",
        )
        Review.objects.create(
            conversation=self.conversation,
            trip_reference="1",
            reviewer=self.passenger,
            target=self.driver,
            reviewer_participant=self.passenger_participant,
            target_participant=self.driver_participant,
            rating=5,
        )
        second_conversation = open_conversation(
            reservation_reference="reservation-2",
            trip_reference="trip-2",
            passenger=second_passenger,
            driver=self.driver,
            departure_at=timezone.now() - timedelta(days=1),
        )
        third_conversation = open_conversation(
            reservation_reference="reservation-3",
            trip_reference="trip-3",
            passenger=third_passenger,
            driver=self.driver,
            departure_at=timezone.now() - timedelta(days=1),
        )
        mark_trip_completed("trip-2")
        mark_trip_completed("trip-3")
        Review.objects.create(
            conversation=second_conversation,
            trip_reference="trip-2",
            reviewer=second_passenger,
            target=self.driver,
            reviewer_participant=CommunicationParticipant.objects.get(
                user=second_passenger
            ),
            target_participant=self.driver_participant,
            rating=4,
        )

        self.client.force_login(self.passenger)
        url = reverse("m1:user_reviews", args=[self.driver.pk])
        self.assertContains(self.client.get(url), "Not enough reviews yet")

        Review.objects.create(
            conversation=third_conversation,
            trip_reference="trip-3",
            reviewer=third_passenger,
            target=self.driver,
            reviewer_participant=CommunicationParticipant.objects.get(
                user=third_passenger
            ),
            target_participant=self.driver_participant,
            rating=3,
        )
        response = self.client.get(url)
        self.assertContains(response, "4.0")
        self.assertContains(response, "3 reviews")

    def test_staff_can_moderate_and_export_reviews(self):
        review = Review.objects.create(
            conversation=self.conversation,
            trip_reference=self.conversation.trip_reference,
            reviewer=self.passenger,
            target=self.driver,
            reviewer_participant=self.passenger_participant,
            target_participant=self.driver_participant,
            rating=4,
            comment="=1+1",
        )
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("m1:admin_review_list")).status_code,
            403,
        )

        staff_user = get_user_model().objects.create_user(
            username="moderator",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        export = self.client.get(
            reverse("m1:admin_review_export_csv")
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])
        self.assertIn(b"'=1+1", export.content)
        self.assertContains(
            self.client.get(reverse("m1:admin_review_list")),
            "Review moderation",
        )

        response = self.client.post(
            reverse("m1:admin_review_delete", args=[review.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.exists())
