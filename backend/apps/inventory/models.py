from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from apps.common.models import TimeStampedModel
from apps.catalog.models import Product, ProductVariant

class Warehouse(TimeStampedModel):
    name=models.CharField(max_length=150,unique=True); code=models.CharField(max_length=40,unique=True)
    address=models.TextField(blank=True); is_active=models.BooleanField(default=True,db_index=True)
    def __str__(self): return self.name

class StockItem(TimeStampedModel):
    product=models.OneToOneField(Product,null=True,blank=True,on_delete=models.CASCADE,related_name="stock_item")
    variant=models.OneToOneField(ProductVariant,null=True,blank=True,on_delete=models.CASCADE,related_name="stock_item")
    class Meta:
        constraints=[models.CheckConstraint(condition=(Q(product__isnull=False,variant__isnull=True)|Q(product__isnull=True,variant__isnull=False)),name="stock_item_exactly_one_target")]
    def clean(self):
        if bool(self.product_id)==bool(self.variant_id): raise ValidationError("Exactly one of product or variant must be set.")
        if self.product_id and self.product.product_type!=Product.ProductType.SIMPLE: raise ValidationError({"product":"Direct stock is only valid for simple products."})
        if self.variant_id and self.variant.product.product_type!=Product.ProductType.VARIABLE: raise ValidationError({"variant":"Variant stock is only valid for variable products."})
    def __str__(self): return self.product.sku if self.product_id else self.variant.sku

class ProductStock(TimeStampedModel):
    stock_item=models.ForeignKey(StockItem,on_delete=models.CASCADE,related_name="stocks")
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT,related_name="stocks")
    available_stock=models.PositiveIntegerField(default=0)
    reserved_stock=models.PositiveIntegerField(default=0)
    damaged_stock=models.PositiveIntegerField(default=0)
    incoming_stock=models.PositiveIntegerField(default=0)
    reorder_level=models.PositiveIntegerField(default=0)
    low_stock_threshold=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["stock_item","warehouse"],name="unique_stock_item_warehouse")]
        indexes=[models.Index(fields=["warehouse","available_stock"]),models.Index(fields=["stock_item","available_stock"])]

class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        PURCHASE="purchase","Purchase"; SALE="sale","Sale"; RETURN="return","Return"; CANCELLATION="cancellation","Cancellation"
        ADJUSTMENT="adjustment","Adjustment"; DAMAGE="damage","Damage"; TRANSFER="transfer","Transfer"; RESTOCK="restock","Restock"
        RESERVATION="reservation","Reservation"; RELEASE="release","Release"
    stock_item=models.ForeignKey(StockItem,on_delete=models.PROTECT,related_name="movements")
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT,related_name="stock_movements")
    movement_type=models.CharField(max_length=20,choices=Type.choices,db_index=True)
    quantity=models.IntegerField()
    before_quantity=models.PositiveIntegerField()
    after_quantity=models.PositiveIntegerField()
    reference_type=models.CharField(max_length=60,blank=True,db_index=True)
    reference_id=models.CharField(max_length=80,blank=True,db_index=True)
    note=models.TextField(blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="stock_movements")
    class Meta:
        indexes=[models.Index(fields=["stock_item","created_at"]),models.Index(fields=["reference_type","reference_id"])]

class StockReservation(TimeStampedModel):
    stock_item=models.ForeignKey(StockItem,on_delete=models.PROTECT,related_name="reservations")
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT,related_name="reservations")
    quantity=models.PositiveIntegerField()
    reference_type=models.CharField(max_length=60,db_index=True)
    reference_id=models.CharField(max_length=80,db_index=True)
    consumed=models.BooleanField(default=False)
    released=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["stock_item","warehouse","reference_type","reference_id"],name="unique_stock_reservation_ref")]

class Supplier(TimeStampedModel):
    name=models.CharField(max_length=180); contact_person=models.CharField(max_length=140,blank=True); phone=models.CharField(max_length=30,blank=True)
    email=models.EmailField(blank=True); address=models.TextField(blank=True); payment_terms=models.CharField(max_length=200,blank=True); notes=models.TextField(blank=True); is_active=models.BooleanField(default=True,db_index=True)
    def __str__(self): return self.name

class Purchase(TimeStampedModel):
    class Status(models.TextChoices): DRAFT="draft","Draft"; APPROVED="approved","Approved"; PARTIAL="partial","Partially Received"; RECEIVED="received","Received"; CANCELLED="cancelled","Cancelled"
    purchase_number=models.CharField(max_length=40,unique=True,db_index=True); supplier=models.ForeignKey(Supplier,on_delete=models.PROTECT,related_name="purchases"); warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT,related_name="purchases")
    supplier_invoice=models.CharField(max_length=100,blank=True); purchase_date=models.DateField(); expected_date=models.DateField(null=True,blank=True)
    subtotal=models.DecimalField(max_digits=14,decimal_places=2,default=0); discount=models.DecimalField(max_digits=14,decimal_places=2,default=0); tax=models.DecimalField(max_digits=14,decimal_places=2,default=0); total=models.DecimalField(max_digits=14,decimal_places=2,default=0)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT,db_index=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="purchases_created"); approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="purchases_approved"); received_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="purchases_received")
    received_at=models.DateTimeField(null=True,blank=True)

class PurchaseItem(TimeStampedModel):
    purchase=models.ForeignKey(Purchase,on_delete=models.CASCADE,related_name="items")
    product=models.ForeignKey(Product,null=True,blank=True,on_delete=models.PROTECT,related_name="purchase_items")
    product_variant=models.ForeignKey(ProductVariant,null=True,blank=True,on_delete=models.PROTECT,related_name="purchase_items")
    quantity=models.PositiveIntegerField(); received_quantity=models.PositiveIntegerField(default=0)
    unit_cost=models.DecimalField(max_digits=12,decimal_places=2); discount=models.DecimalField(max_digits=12,decimal_places=2,default=0); tax=models.DecimalField(max_digits=12,decimal_places=2,default=0); total=models.DecimalField(max_digits=14,decimal_places=2,default=0)
    class Meta:
        constraints=[
            models.CheckConstraint(condition=(Q(product__isnull=False,product_variant__isnull=True)|Q(product__isnull=True,product_variant__isnull=False)),name="purchase_item_exactly_one_target"),
            models.CheckConstraint(condition=Q(quantity__gt=0),name="purchase_item_quantity_gt_zero"),
            models.CheckConstraint(condition=Q(received_quantity__lte=F("quantity")),name="purchase_received_lte_ordered"),
        ]
    def clean(self):
        if self.product_id and self.product.product_type!=Product.ProductType.SIMPLE: raise ValidationError({"product":"Use product_variant for variable products."})
        if self.product_variant_id and self.product_variant.product.product_type!=Product.ProductType.VARIABLE: raise ValidationError({"product_variant":"Invalid variable product target."})
