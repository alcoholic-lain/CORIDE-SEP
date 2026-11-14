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


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "maxlength": 1000,
                    "placeholder": "Write a message…",
                    "required": True,
                }
            )
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
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
