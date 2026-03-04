from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.catalog.models import Brand, Product, Variant
from apps.inventory.models import Stock
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review

from decimal import Decimal

User = get_user_model()


def make_product():
    brand = Brand.objects.create(name="Brand", slug="brand")
    return Product.objects.create(
        name="Producto", slug="producto", brand=brand, description="desc"
    )


def make_user(email="u@test.com"):
    username = email.split("@")[0]
    return User.objects.create_user(username=username, email=email, password="pass1234")


def make_delivered_order(user, product):
    variant = Variant.objects.create(
        product=product, sku="SKU-REV", name="Var", price=Decimal("50000")
    )
    Stock.objects.create(variant=variant, quantity=10)
    order = Order.objects.create(
        user=user,
        status=Order.Status.DELIVERED,
        subtotal=Decimal("50000"),
        total=Decimal("59500"),
        shipping_name="Test",
        shipping_address="Calle 1",
        shipping_city="Bogotá",
        shipping_department="Cundinamarca",
        shipping_phone="3001234567",
    )
    OrderItem.objects.create(
        order=order, variant=variant,
        product_name=product.name, variant_name=variant.name,
        sku=variant.sku, unit_price=variant.price,
        quantity=1, subtotal=variant.price,
    )
    return order


# ══════════════════════════════════════════════════════════════════════════════
# Model Tests
# ══════════════════════════════════════════════════════════════════════════════

class ReviewModelTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    def test_create_review(self):
        review = Review.objects.create(
            product=self.product, user=self.user,
            rating=5, title="Excelente", body="Lo amo"
        )
        self.assertEqual(str(review), f"Review 5★ — {self.product.name} by {self.user.email}")

    def test_unique_per_user_product(self):
        from django.db import IntegrityError
        Review.objects.create(product=self.product, user=self.user, rating=4)
        with self.assertRaises(IntegrityError):
            Review.objects.create(product=self.product, user=self.user, rating=3)


# ══════════════════════════════════════════════════════════════════════════════
# API Tests
# ══════════════════════════════════════════════════════════════════════════════

class ReviewAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        self.url = "/api/reviews/"

    def test_list_reviews_public(self):
        Review.objects.create(product=self.product, user=self.user, rating=4)
        res = self.client.get(f"{self.url}?product={self.product.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_create_review_requires_auth(self):
        res = self.client.post(self.url, {"product": self.product.id, "rating": 5})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_review_authenticated(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {
            "product": self.product.id,
            "rating": 5,
            "title": "Bueno",
            "body": "Me gustó",
        }, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["rating"], 5)

    def test_verified_purchase_flag(self):
        make_delivered_order(self.user, self.product)
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {
            "product": self.product.id,
            "rating": 5,
        }, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["is_verified_purchase"])

    def test_not_verified_without_purchase(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {
            "product": self.product.id,
            "rating": 3,
        }, format="multipart")
        self.assertFalse(res.data["is_verified_purchase"])

    def test_delete_own_review(self):
        review = Review.objects.create(
            product=self.product, user=self.user, rating=4
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.delete(f"{self.url}{review.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_other_user_review_forbidden(self):
        other = make_user(email="other@test.com")
        review = Review.objects.create(
            product=self.product, user=other, rating=4
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.delete(f"{self.url}{review.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_review_hidden_from_public(self):
        Review.objects.create(
            product=self.product, user=self.user,
            rating=2, is_approved=False
        )
        res = self.client.get(f"{self.url}?product={self.product.id}")
        self.assertEqual(res.data["count"], 0)