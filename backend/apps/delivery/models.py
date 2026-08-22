from django.db import models

from apps.common.models import TimeStampedModel


class DeliveryModule(TimeStampedModel):
    """Configurable geographical delivery pricing bucket."""

    class Code(models.TextChoices):
        INSIDE_DHAKA = "inside_dhaka", "Inside Dhaka"
        OUTSIDE_DHAKA = "outside_dhaka", "Outside Dhaka"
        SUBAREA = "subarea", "Subarea"

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40, choices=Code.choices, unique=True)
    charge = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.name} - ৳{self.charge}"


class City(TimeStampedModel):
    """District/city imported from the supplied legacy city JSON."""

    source_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=120, db_index=True)
    delivery_module = models.ForeignKey(
        DeliveryModule,
        on_delete=models.PROTECT,
        related_name="cities",
    )
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("name", "id")
        indexes = [models.Index(fields=("active", "name"))]

    def __str__(self):
        return self.name


class Thana(TimeStampedModel):
    """Thana/area under a district.

    delivery_module is an optional override. When empty, pricing inherits the
    parent City's delivery module. This is how selected Dhaka outskirts or
    other special areas can be charged using the Subarea module.
    """

    source_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="thanas")
    name = models.CharField(max_length=160, db_index=True)
    delivery_module = models.ForeignKey(
        DeliveryModule,
        on_delete=models.PROTECT,
        related_name="thanas",
        null=True,
        blank=True,
        help_text="Optional override. Leave empty to inherit the district delivery module.",
    )
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(fields=("city", "name"), name="delivery_unique_thana_per_city")
        ]
        indexes = [models.Index(fields=("city", "active", "name"))]

    @property
    def effective_delivery_module(self):
        return self.delivery_module or self.city.delivery_module

    def __str__(self):
        return f"{self.name}, {self.city.name}"
