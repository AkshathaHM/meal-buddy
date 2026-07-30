#!/usr/bin/env python3
import os
import sys

# ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meal.settings')
import django
django.setup()

from delivery.models import Restaurant, User, Cart

rest_count = Restaurant.objects.count()
user_count = User.objects.count()
order_count = Cart.objects.count()

# compute revenue by summing each cart's items' prices
total_revenue = 0.0
for cart in Cart.objects.prefetch_related('items').all():
    total_revenue += sum(float(item.price) for item in cart.items.all())

print('TOTAL_RESTAURANTS:', rest_count)
print('TOTAL_ORDERS:', order_count)
print('TOTAL_USERS:', user_count)
print('TOTAL_REVENUE:', f"{total_revenue:.2f}")
