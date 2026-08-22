from decimal import Decimal
from datetime import date,timedelta
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image,ImageDraw
from apps.accounts.models import User,UserRole
from apps.catalog.models import Category,Brand,Product,ProductVariant,Attribute,AttributeValue,ProductImage,ProductBeautyProfile,SkinType,HairType,Concern,Ingredient,Claim,ProductClaim,VariantAttributeValue
from apps.inventory.models import Warehouse,Supplier,Purchase,PurchaseItem,StockMovement
from apps.inventory.services import resolve_stock_item,increase_stock,receive_purchase
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.shipping.models import ShippingMethod
from apps.orders.services import checkout,transition_order
from apps.orders.models import Order
from apps.payments.services import mark_payment_paid
from apps.promotions.models import Coupon,Promotion
from apps.reviews.models import Review
from apps.reviews.services import create_review
from apps.returns.services import create_return_request,approve_return,receive_return,create_refund,complete_refund
from apps.common.models import AnalyticsEvent

SIMPLE=[
("CeraVe Foaming Cleanser 236ml","cerave-foaming-cleanser-236ml","CER-FC-236",620,"Skincare","CeraVe"),
("COSRX Snail Essence","cosrx-snail-essence","COS-SNAIL-96",1550,"Skincare","COSRX"),
("Beauty of Joseon Sunscreen","beauty-of-joseon-sunscreen","BOJ-SPF-50",1450,"Skincare","Beauty of Joseon"),
("The Ordinary Niacinamide","the-ordinary-niacinamide","TO-NIA-30",1180,"Skincare","The Ordinary"),
("Laneige Water Sleeping Mask","laneige-water-sleeping-mask","LAN-WSM-70",2250,"Skincare","Laneige"),
("Cetaphil Gentle Skin Cleanser","cetaphil-gentle-skin-cleanser","CET-GSC-250",1320,"Skincare","Cetaphil"),
("Some By Mi AHA BHA PHA Toner","some-by-mi-toner","SBM-TONER-150",1690,"Skincare","Some By Mi"),
("Bioderma Sensibio H2O","bioderma-sensibio-h2o","BIO-H2O-250",1850,"Skincare","Bioderma"),
("Nivea Soft Moisturizing Cream","nivea-soft-moisturizing-cream","NIV-SOFT-100",520,"Body","Nivea"),
("Mise en Scene Perfect Serum","mise-en-scene-perfect-serum","MES-PS-80",1280,"Hair","Mise en Scene"),
]
VARIABLE=[
("Radiant Skin Foundation","radiant-skin-foundation","Makeup","Demo Beauty","shade",["Porcelain","Natural Beige","Warm Sand"]),
("Velvet Matte Lipstick","velvet-matte-lipstick","Makeup","Demo Beauty","color",["Rosewood","Berry","Coral"]),
("d'Aamour Signature Perfume","damour-signature-perfume","Fragrance","d'Aamour","volume",["30ml","50ml","100ml"]),
("Repair Shampoo","repair-shampoo","Hair","Demo Hair","size",["250ml","500ml"]),
("Smooth Conditioner","smooth-conditioner","Hair","Demo Hair","size",["250ml","500ml"]),
("Brightening Concealer","brightening-concealer","Makeup","Demo Beauty","shade",["Light","Medium","Tan"]),
("Soft Flush Blush","soft-flush-blush","Makeup","Demo Beauty","shade",["Peach","Pink","Mauve"]),
("Deep Repair Hair Mask","deep-repair-hair-mask","Hair","Demo Hair","size",["200ml","400ml"]),
("Ceramide Body Lotion","ceramide-body-lotion","Body","Demo Beauty","size",["200ml","400ml"]),
("Daily Glow BB Cream","daily-glow-bb-cream","Makeup","Demo Beauty","shade",["21 Light","23 Natural","25 Warm"]),
]

def placeholder(name,seed=1,size=(900,900)):
    im=Image.new("RGB",size,(235-(seed*7)%40,238-(seed*5)%35,242-(seed*3)%30)); d=ImageDraw.Draw(im); d.rectangle((80,80,size[0]-80,size[1]-80),outline=(90,90,90),width=4); d.text((110,size[1]//2),name[:34],fill=(30,30,30)); b=BytesIO(); im.save(b,format="JPEG",quality=85); return ContentFile(b.getvalue(),name=f"demo-{seed}.jpg")

class Command(BaseCommand):
    help="Seed a full, clearly labelled Beauty E-commerce demo dataset. Safe to run repeatedly."
    def handle(self,*args,**opts):
        if Product.objects.filter(slug="cerave-foaming-cleanser-236ml").exists():
            self.stdout.write(self.style.WARNING("Demo data already exists; no duplicate import performed.")); return
        # Taxonomy
        roots={}
        for name in ["Skincare","Makeup","Hair","Body","Fragrance","Mom & Baby","Men"]:
            roots[name]=Category.objects.create(name=name,slug=name.lower().replace(" & ","-").replace(" ","-"))
        for parent,children in {"Skincare":["Cleanser","Toner","Serum","Moisturizer","Sunscreen","Mask"],"Makeup":["Face","Eyes","Lips","Nails"]}.items():
            for c in children: Category.objects.create(name=c,slug=f"{parent.lower()}-{c.lower()}".replace(" ","-"),parent=roots[parent])
        brands={}
        for name in sorted({x[5] for x in SIMPLE}|{x[3] for x in VARIABLE}): brands[name]=Brand.objects.create(name=name,slug=name.lower().replace("'","").replace(" ","-"),country="Demo / sample",active=True,featured=name in {"COSRX","Beauty of Joseon","Demo Beauty"})
        skin=[SkinType.objects.create(name=x,slug=x.lower().replace(" ","-")) for x in ["Dry","Oily","Combination","Sensitive","Normal"]]
        HairType.objects.bulk_create([HairType(name="Straight",slug="straight"),HairType(name="Wavy",slug="wavy"),HairType(name="Curly",slug="curly")])
        concerns=[Concern.objects.create(name=x,slug=x.lower().replace(" ","-"),concern_type="skin") for x in ["Acne","Dryness","Dullness","Dark Spots","Sun Protection"]]
        ing=[Ingredient.objects.create(name=x,slug=x.lower().replace(" ","-")) for x in ["Niacinamide","Hyaluronic Acid","Ceramide","Snail Mucin","Centella"]]
        claims=[Claim.objects.create(name=x,slug=x.lower().replace(" ","-")) for x in ["Cruelty Free","Vegan","Dermatologist Tested","Pregnancy Safe","Fragrance Free","Alcohol Free"]]
        attrs={}
        for n in ["shade","color","volume","size","finish"]: attrs[n]=Attribute.objects.create(name=n.title(),slug=n)
        products=[]; seed=1
        for name,slug,sku,price,cat,brand in SIMPLE:
            p=Product.objects.create(name=name,slug=slug,product_type=Product.ProductType.SIMPLE,sku=sku,brand=brands[brand],category=roots[cat],base_price=Decimal(price),compare_at_price=Decimal(price)*Decimal("1.15"),cost_price=Decimal(price)*Decimal("0.55"),status=Product.Status.ACTIVE,short_description=f"Demo beauty product: {name}",description="Clearly labelled demo catalogue content.",featured=seed%3==0,new_arrival=seed%4==0,bestseller=seed%5==0,published_at=timezone.now())
            prof=ProductBeautyProfile.objects.create(product=p,benefits="Demo benefit copy for hydration, comfort and everyday care.",ingredients_text="Demo ingredient list.",how_to_use="Use as directed on the product label.",precautions="Patch test before use.",country_of_origin="Demo",shelf_life="36 months",pao="12M"); prof.skin_types.set(skin[:3]); prof.concerns.set(concerns[:2]); prof.ingredients.set(ing[:3])
            ProductClaim.objects.create(product=p,claim=claims[2],is_verified=True,evidence="Demo evidence only",reviewed_at=timezone.now())
            for j in range(2): ProductImage.objects.create(product=p,image=placeholder(name,seed*10+j),order=j,is_primary=j==0,alt_text=name)
            products.append(p); seed+=1
        variants=[]
        for name,slug,cat,brand,attr_name,values in VARIABLE:
            p=Product.objects.create(name=name,slug=slug,product_type=Product.ProductType.VARIABLE,brand=brands[brand],category=roots[cat],base_price=Decimal(1200+seed*45),status=Product.Status.ACTIVE,short_description=f"Demo variable product: {name}",description="Variable demo product with real variants.",cost_price=Decimal(700),published_at=timezone.now())
            ProductBeautyProfile.objects.create(product=p,benefits="Configurable demo beauty profile.",how_to_use="Use according to selected variant.")
            ProductImage.objects.create(product=p,image=placeholder(name,seed*10),order=0,is_primary=True,alt_text=name)
            for j,value in enumerate(values):
                av,_=AttributeValue.objects.get_or_create(attribute=attrs[attr_name],slug=value.lower().replace(" ","-"),defaults={"value":value})
                v=ProductVariant.objects.create(product=p,sku=f"VAR-{seed:02}-{j+1:02}",price_override=p.base_price+Decimal(j*150),cost_price=Decimal(650+j*60),is_active=True)
                VariantAttributeValue.objects.create(variant=v,attribute_value=av); ProductImage.objects.create(product=p,variant=v,image=placeholder(f"{name} {value}",seed*100+j),order=0,is_primary=True,alt_text=f"{name} {value}"); variants.append(v)
            products.append(p); seed+=1
        # Inventory & purchasing
        main=Warehouse.objects.create(name="Demo Main Warehouse",code="DEMO-MAIN",address="Dhaka")
        hub=Warehouse.objects.create(name="Demo Hub Warehouse",code="DEMO-HUB",address="Dhaka Hub")
        admin=User.objects.create_superuser(phone="01900000000",password="Admin123!",full_name="Demo Super Admin")
        for p in products:
            if p.product_type==Product.ProductType.SIMPLE:
                si=resolve_stock_item(product=p); increase_stock(stock_item=si,warehouse=main,quantity=30,movement_type=StockMovement.Type.RESTOCK,reference_type="demo",reference_id=p.id,created_by=admin)
            else:
                for v in p.variants.all():
                    si=resolve_stock_item(variant=v); increase_stock(stock_item=si,warehouse=main,quantity=15,movement_type=StockMovement.Type.RESTOCK,reference_type="demo",reference_id=v.id,created_by=admin); increase_stock(stock_item=si,warehouse=hub,quantity=5,movement_type=StockMovement.Type.RESTOCK,reference_type="demo",reference_id=v.id,created_by=admin)
        supplier=Supplier.objects.create(name="Demo Beauty Supplier Ltd.",contact_person="Demo Supplier",phone="01800000000",email="supplier@example.test",payment_terms="30 days")
        purchase=Purchase.objects.create(purchase_number="DEMO-PO-0001",supplier=supplier,warehouse=main,purchase_date=date.today(),expected_date=date.today()+timedelta(days=3),subtotal=Decimal("12400"),total=Decimal("12400"),status=Purchase.Status.APPROVED,created_by=admin,approved_by=admin)
        pi1=PurchaseItem.objects.create(purchase=purchase,product=products[0],quantity=10,unit_cost=Decimal("400"),total=Decimal("4000")); pi2=PurchaseItem.objects.create(purchase=purchase,product_variant=variants[0],quantity=8,unit_cost=Decimal("1050"),total=Decimal("8400")); receive_purchase(purchase=purchase,receipts=[{"item_id":pi1.id,"quantity":10},{"item_id":pi2.id,"quantity":4}],user=admin)
        # Shipping + promotions
        ship=ShippingMethod.objects.create(name="Inside Dhaka",code="inside-dhaka",base_charge=Decimal("70"),estimated_days="1-2 days",free_threshold=Decimal("5000"))
        Coupon.objects.create(code="DEMO10",coupon_type=Coupon.Type.PERCENTAGE,value=Decimal("10"),minimum_spend=Decimal("1000"),usage_limit=100,active=True)
        Promotion.objects.create(name="Demo Skincare 5%",promotion_type=Promotion.Type.CATEGORY,active=True,priority=50,combinable=True,config={"percent":5})
        promo=Promotion.objects.get(name="Demo Skincare 5%"); promo.categories.add(roots["Skincare"])
        # Customers + delivered orders using real cart/checkout/stock services
        delivered=[]
        for idx in range(4):
            user=User.objects.create_user(phone=f"0179000000{idx}",password="Customer123!",full_name=f"Demo Customer {idx+1}")
            cart=Cart.objects.create(user=user); target=products[idx]; add_cart_item(cart=cart,product=target,quantity=2 if idx==0 else 1)
            if idx%2==0: add_cart_item(cart=cart,product_variant=variants[idx],quantity=1)
            result=checkout(cart=cart,customer_data={"name":user.full_name,"phone":user.phone,"district":"Dhaka","thana":"Dhanmondi","address":f"Demo House {idx+1}, Road 5","label":"Home"},shipping_method=ship,payment_method="cod",coupon_code="DEMO10" if idx==0 else "",request_user=user)
            order=result["order"]
            for status in [Order.Status.CONFIRMED,Order.Status.PROCESSING,Order.Status.PACKED,Order.Status.READY_TO_SHIP,Order.Status.SHIPPED,Order.Status.OUT_FOR_DELIVERY,Order.Status.DELIVERED]: order=transition_order(order=order,new_status=status,actor=admin)
            payment=order.payments.first(); mark_payment_paid(payment=payment,transaction_id=f"DEMO-TXN-{idx+1}")
            delivered.append(order)
            oi=order.items.first(); rv=create_review(user=user,validated_data={"product":oi.product,"order_item":oi,"rating":5-idx%2,"title":"Demo verified review","comment":"Demo review generated by seed_full_demo."}); rv.status=Review.Status.APPROVED; rv.save(update_fields=["status"])
        # One return + partial refund demo
        order=delivered[0]; oi=order.items.first(); rr=create_return_request(order=order,user=order.user,items=[{"order_item":oi,"quantity":1,"reason":"Demo return","restock":True}],reason="Demo return request"); approve_return(return_request=rr,actor=admin); receive_return(return_request=rr,warehouse=main,actor=admin); payment=order.payments.first(); refund=create_refund(payment=payment,amount=min(oi.unit_price,payment.amount),reason="Demo partial refund",actor=admin); complete_refund(refund=refund,gateway_reference="DEMO-REFUND-1")
        # Analytics without anonymous user creation
        for i in range(60): AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.PRODUCT_VIEW,session_token=f"demo-session-{i%10}",product_id_ref=products[i%len(products)].id)
        for i in range(25): AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.ADD_TO_CART,cart_token=f"demo-cart-{i%8}",product_id_ref=products[i%len(products)].id)
        for i in range(8): AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.CHECKOUT_STARTED,session_token=f"demo-checkout-{i}")
        self.stdout.write(self.style.SUCCESS("Seeded 20 products (10 simple + 10 variable), variants, images, inventory, purchase, customers, orders, reviews, coupons, promotions, return/refund and analytics."))
