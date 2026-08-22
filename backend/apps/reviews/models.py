from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel
class Review(TimeStampedModel):
    class Status(models.TextChoices): PENDING="pending","Pending"; APPROVED="approved","Approved"; REJECTED="rejected","Rejected"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="reviews"); product=models.ForeignKey("catalog.Product",on_delete=models.CASCADE,related_name="reviews"); order_item=models.ForeignKey("orders.OrderItem",null=True,blank=True,on_delete=models.SET_NULL,related_name="reviews")
    rating=models.PositiveSmallIntegerField(); title=models.CharField(max_length=180,blank=True); comment=models.TextField(); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,db_index=True); verified_purchase=models.BooleanField(default=False,db_index=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(rating__gte=1,rating__lte=5),name="review_rating_1_5"),models.UniqueConstraint(fields=["user","order_item"],condition=Q(order_item__isnull=False),name="one_review_per_order_item")]
        indexes=[models.Index(fields=["product","status","created_at"])]
class ReviewImage(TimeStampedModel):
    review=models.ForeignKey(Review,on_delete=models.CASCADE,related_name="images"); image=models.ImageField(upload_to="reviews/%Y/%m/"); order=models.PositiveIntegerField(default=0)
