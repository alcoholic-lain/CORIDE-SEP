from django import forms

from .models import Message, Review
from .moderation import is_blocked


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
