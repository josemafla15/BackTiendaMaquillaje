from __future__ import annotations
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from cloudinary.models import CloudinaryField
from common.models import TimeStampedModel
from apps.catalog.models import Product


class Review(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
    )
    reviewer_email = models.EmailField()  # email del comprador (registrado o invitado)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)

    class Meta:
        db_table = "reviews_reviews"
        unique_together = ("product", "reviewer_email")  # un email = una reseña por producto
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review {self.rating}★ — {self.product.name} by {self.reviewer_email}"


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = CloudinaryField("reviews/photos")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "reviews_images"
        ordering = ["order"]