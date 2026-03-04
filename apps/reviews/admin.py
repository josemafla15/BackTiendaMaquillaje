from django.contrib import admin
from .models import Review, ReviewImage


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "is_verified_purchase", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating"]
    list_editable = ["is_approved"]
    inlines = [ReviewImageInline]