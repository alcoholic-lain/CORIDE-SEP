from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("trip_reference", "reviewer", "target", "rating", "review_date")
    list_filter = ("rating", "review_date")
    search_fields = (
        "trip_reference",
        "reviewer__username",
        "target__username",
        "comment",
    )
    readonly_fields = (
        "conversation",
        "trip_reference",
        "reviewer",
        "target",
        "rating",
        "comment",
        "review_date",
    )

    def has_add_permission(self, request):
        return False
