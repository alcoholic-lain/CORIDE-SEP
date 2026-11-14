from pathlib import Path

from django import forms

from .models import Message, Review
from .moderation import is_blocked


class GuestNameForm(forms.Form):
    display_name = forms.CharField(
        max_length=80,
        label="Your name",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "nickname",
                "maxlength": 80,
                "placeholder": "How should people see you?",
                "required": True,
            }
        ),
    )

    def clean_display_name(self):
        display_name = self.cleaned_data["display_name"].strip()
        if not display_name:
            raise forms.ValidationError("Enter a name to continue.")
        if any(ord(character) < 32 for character in display_name):
            raise forms.ValidationError("Your name contains unsupported characters.")
        return display_name


class NewConversationForm(forms.Form):
    title = forms.CharField(
        max_length=120,
        required=False,
        label="Chat name",
        widget=forms.TextInput(
            attrs={"maxlength": 120, "placeholder": "e.g. Ride to campus"}
        ),
    )
    initial_message = forms.CharField(
        max_length=1000,
        required=False,
        label="First message",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 1000,
                "placeholder": "Add a message before you share the invite.",
            }
        ),
    )

    def clean_title(self):
        return self.cleaned_data["title"].strip() or "New conversation"

    def clean_initial_message(self):
        content = self.cleaned_data["initial_message"].strip()
        if content and is_blocked(content):
            raise forms.ValidationError("Message not sent. Please rephrase it.")
        return content


class MessageForm(forms.Form):
    MAX_ATTACHMENT_SIZE = 8 * 1024 * 1024
    ATTACHMENT_TYPES = {
        ".gif": ("image/gif", lambda head: head.startswith((b"GIF87a", b"GIF89a"))),
        ".jpeg": ("image/jpeg", lambda head: head.startswith(b"\xff\xd8\xff")),
        ".jpg": ("image/jpeg", lambda head: head.startswith(b"\xff\xd8\xff")),
        ".pdf": ("application/pdf", lambda head: head.startswith(b"%PDF-")),
        ".png": ("image/png", lambda head: head.startswith(b"\x89PNG\r\n\x1a\n")),
        ".webp": (
            "image/webp",
            lambda head: head[:4] == b"RIFF" and head[8:12] == b"WEBP",
        ),
    }

    content = forms.CharField(
        max_length=1000,
        required=False,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "maxlength": 1000,
                "placeholder": "Write a message…",
            }
        ),
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(
            attrs={"accept": "image/gif,image/jpeg,image/png,image/webp,application/pdf"}
        ),
    )
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean_content(self):
        content = self.cleaned_data["content"]
        if is_blocked(content):
            raise forms.ValidationError("Message not sent. Please rephrase it.")
        return content

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment is None:
            return None
        if attachment.size > self.MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError("Attachments must be 8 MB or smaller.")

        extension = Path(attachment.name).suffix.lower()
        attachment_type = self.ATTACHMENT_TYPES.get(extension)
        if attachment_type is None:
            raise forms.ValidationError("Choose a PNG, JPEG, GIF, WebP, or PDF file.")

        content_type, matches = attachment_type
        header = attachment.read(12)
        attachment.seek(0)
        if not matches(header):
            raise forms.ValidationError("The attachment does not match its file type.")
        attachment.validated_content_type = content_type
        return attachment

    def clean(self):
        cleaned_data = super().clean()
        if (
            not cleaned_data.get("content")
            and not cleaned_data.get("attachment")
            and "content" not in self.errors
            and "attachment" not in self.errors
        ):
            raise forms.ValidationError("Write a message or attach a file.")
        return cleaned_data


class MessageEditForm(forms.Form):
    content = forms.CharField(max_length=1000, strip=True)

    def clean_content(self):
        content = self.cleaned_data["content"]
        if not content:
            raise forms.ValidationError("Message cannot be empty.")
        if is_blocked(content):
            raise forms.ValidationError("Message not sent. Please rephrase it.")
        return content


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(
                choices=[
                    (rating, f"{rating} star{'s' if rating != 1 else ''}")
                    for rating in range(1, 6)
                ]
            ),
            "comment": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                    "placeholder": "Share a short comment (optional)",
                }
            ),
        }

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "").strip()
        if comment and is_blocked(comment):
            raise forms.ValidationError("Review refused. Please rephrase your comment.")
        return comment
