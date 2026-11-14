from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Conversation, Message, Review
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


class ConversationTests(CommunicationTestCase):
    def test_module_home_and_conversation_list_render(self):
        self.client.force_login(self.passenger)

        self.assertEqual(self.client.get(reverse("communication:index")).status_code, 200)
        response = self.client.get(reverse("communication:conversation_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My conversations")
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
            content="Meet by the station",
        )
        self.client.force_login(self.driver)

        response = self.client.get(
            reverse(
                "communication:conversation_detail",
                args=[self.conversation.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meet by the station")
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_only_participants_can_view_and_send_messages(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse(
                "communication:conversation_detail",
                args=[self.conversation.pk],
            )
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("communication:send_message", args=[self.conversation.pk]),
            {"content": "Hello"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.exists())

    def test_message_send_poll_and_read_receipt(self):
        self.client.force_login(self.passenger)
        response = self.client.post(
            reverse("communication:send_message", args=[self.conversation.pk]),
            {"content": "  Hello from the trip  "},
        )

        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual(message.content, "Hello from the trip")

        self.client.force_login(self.driver)
        response = self.client.get(
            reverse("communication:poll_messages", args=[self.conversation.pk]),
            {"after": 0},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], message.content)
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_invalid_cursor_is_rejected(self):
        self.client.force_login(self.passenger)
        response = self.client.get(
            reverse("communication:poll_messages", args=[self.conversation.pk]),
            {"after": "not-a-number"},
        )
        self.assertEqual(response.status_code, 400)

    def test_closed_conversation_rejects_send_and_command_closes_expired_chat(self):
        self.conversation.departure_at = timezone.now() - timedelta(hours=25)
        self.conversation.save(update_fields=["departure_at"])
        self.client.force_login(self.passenger)

        response = self.client.post(
            reverse("communication:send_message", args=[self.conversation.pk]),
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
            reverse("communication:send_message", args=[self.conversation.pk]),
            {"content": "Please remove this"},
        )
        message = Message.objects.get()
        delete_url = reverse("communication:message_delete", args=[message.pk])

        self.client.force_login(self.driver)
        self.assertEqual(self.client.post(delete_url).status_code, 403)

        self.client.force_login(self.passenger)
        self.assertEqual(self.client.post(delete_url).status_code, 200)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.content, "Please remove this")

    @override_settings(COMMUNICATION_BLOCKED_TERMS=("badword",))
    def test_moderation_normalizes_obfuscation_and_uses_whole_words(self):
        self.assertTrue(is_blocked("That is b@dword!"))
        self.assertFalse(is_blocked("notbadwording"))

        self.client.force_login(self.passenger)
        response = self.client.post(
            reverse("communication:send_message", args=[self.conversation.pk]),
            {"content": "b@dword"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.exists())


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
                "communication:review_create",
                args=["1", self.driver.pk],
            )
        )
        self.assertEqual(response.status_code, 403)

        mark_trip_completed(self.conversation.trip_reference)
        response = self.client.post(
            reverse(
                "communication:review_create",
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
            rating=4,
            comment="Existing review",
        )
        self.client.force_login(self.passenger)

        response = self.client.post(
            reverse(
                "communication:review_create",
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
            rating=4,
        )

        self.client.force_login(self.passenger)
        url = reverse("communication:user_reviews", args=[self.driver.pk])
        self.assertContains(self.client.get(url), "Not enough reviews yet")

        Review.objects.create(
            conversation=third_conversation,
            trip_reference="trip-3",
            reviewer=third_passenger,
            target=self.driver,
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
            rating=4,
            comment="=1+1",
        )
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("communication:admin_review_list")).status_code,
            403,
        )

        staff_user = get_user_model().objects.create_user(
            username="moderator",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        export = self.client.get(
            reverse("communication:admin_review_export_csv")
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])
        self.assertIn(b"'=1+1", export.content)
        self.assertContains(
            self.client.get(reverse("communication:admin_review_list")),
            "Review moderation",
        )

        response = self.client.post(
            reverse("communication:admin_review_delete", args=[review.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.exists())
