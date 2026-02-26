from django.db import migrations, models
import django.core.validators


def seed_shipping_rates(apps, schema_editor):
    ShippingRate = apps.get_model("shipping", "ShippingRate")

    rates = [
        # Ciudades principales
        dict(name="Bogotá", city="Bogotá", department="Cundinamarca",
             price=8_000, free_shipping_from=150_000,
             estimated_days_min=1, estimated_days_max=2),
        dict(name="Medellín", city="Medellín", department="Antioquia",
             price=9_000, free_shipping_from=150_000,
             estimated_days_min=1, estimated_days_max=2),
        dict(name="Cali", city="Cali", department="Valle del Cauca",
             price=9_000, free_shipping_from=150_000,
             estimated_days_min=1, estimated_days_max=2),
        dict(name="Barranquilla", city="Barranquilla", department="Atlántico",
             price=10_000, free_shipping_from=150_000,
             estimated_days_min=2, estimated_days_max=3),
        dict(name="Cartagena", city="Cartagena", department="Bolívar",
             price=10_000, free_shipping_from=150_000,
             estimated_days_min=2, estimated_days_max=3),
        dict(name="Bucaramanga", city="Bucaramanga", department="Santander",
             price=10_000, free_shipping_from=150_000,
             estimated_days_min=2, estimated_days_max=3),
        dict(name="Pereira", city="Pereira", department="Risaralda",
             price=9_000, free_shipping_from=150_000,
             estimated_days_min=1, estimated_days_max=2),
        dict(name="Manizales", city="Manizales", department="Caldas",
             price=9_000, free_shipping_from=150_000,
             estimated_days_min=2, estimated_days_max=3),
        dict(name="Pasto", city="Pasto", department="Nariño",
             price=11_000, free_shipping_from=200_000,
             estimated_days_min=2, estimated_days_max=4),
        dict(name="Cúcuta", city="Cúcuta", department="Norte de Santander",
             price=11_000, free_shipping_from=200_000,
             estimated_days_min=2, estimated_days_max=4),
        dict(name="Ibagué", city="Ibagué", department="Tolima",
             price=10_000, free_shipping_from=150_000,
             estimated_days_min=2, estimated_days_max=3),
        dict(name="Santa Marta", city="Santa Marta", department="Magdalena",
             price=11_000, free_shipping_from=200_000,
             estimated_days_min=2, estimated_days_max=4),
        dict(name="Villavicencio", city="Villavicencio", department="Meta",
             price=11_000, free_shipping_from=200_000,
             estimated_days_min=2, estimated_days_max=4),
        dict(name="Resto del país", city="", department="",
             price=14_000, free_shipping_from=250_000,
             estimated_days_min=3, estimated_days_max=7, is_default=True),
    ]
    for data in rates:
        ShippingRate.objects.create(**data)


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ShippingRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100,
                    help_text="Nombre descriptivo. Ej: 'Bogotá', 'Antioquia', 'Resto del país'")),
                ("city", models.CharField(blank=True, db_index=True, max_length=100,
                    help_text="Nombre exacto de la ciudad.")),
                ("department", models.CharField(blank=True, db_index=True, max_length=100,
                    help_text="Departamento.")),
                ("price", models.DecimalField(decimal_places=2, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(0)])),
                ("free_shipping_from", models.DecimalField(blank=True, decimal_places=2,
                    max_digits=12, null=True)),
                ("estimated_days_min", models.PositiveSmallIntegerField(default=1)),
                ("estimated_days_max", models.PositiveSmallIntegerField(default=3)),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
            ],
            options={"db_table": "shipping_rates", "ordering": ["department", "city"]},
        ),
        migrations.AddConstraint(
            model_name="shippingrate",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_default=True, is_active=True),
                fields=["is_default"],
                name="unique_active_default_shipping_rate",
            ),
        ),
        migrations.RunPython(seed_shipping_rates, migrations.RunPython.noop),
    ]