import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0002_conversation_invite_code_conversation_title_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="invite_code",
            field=models.CharField(max_length=40, unique=True),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="participant_one",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversations_as_first",
                to="communication.communicationparticipant",
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="sender_participant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sent_messages",
                to="communication.communicationparticipant",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="reviewer_participant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews_written",
                to="communication.communicationparticipant",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="target_participant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews_received",
                to="communication.communicationparticipant",
            ),
        ),
    ]
