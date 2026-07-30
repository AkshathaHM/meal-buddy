import json
import time

import razorpay
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import User, Restaurant, Item, Cart, Order, OrderItem


def _normalize_role(role):
    return str(role or '').strip().lower() or 'customer'


def _set_user_session(request, user):
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    request.session['role'] = _normalize_role(getattr(user, 'role', ''))
    request.session['last_activity'] = int(time.time())


def _clear_user_session(request):
    request.session.flush()


def _get_logged_in_user(request):
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    if not user_id or not username:
        return None
    try:
        user = User.objects.get(id=user_id, username=username)
    except User.DoesNotExist:
        return None

    if not getattr(user, 'role', None):
        user.role = 'customer'
    return user


# Create your views here.
def index(request):
    user = _get_logged_in_user(request)
    if user:
        if _normalize_role(user.role) == 'admin':
            return redirect('admin_home')
        return redirect('customer_home')
    return render(request, 'home.html')

def admin_home(request):
    response = None
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_admin_signin')
    if _normalize_role(user.role) != 'admin':
        return redirect('customer_home')
    # compute admin dashboard totals
    rest_count = Restaurant.objects.count()
    user_count = User.objects.count()
    order_count = Cart.objects.count()

    # compute revenue by summing prices of items in all carts (completed carts are represented as Cart records)
    total_revenue = 0.0
    for cart in Cart.objects.prefetch_related('items').all():
        total_revenue += sum(float(item.price) for item in cart.items.all())

    # format revenue for display (no currency symbol)
    total_revenue_display = f"{total_revenue:,.2f}"

    context = {
        'username': user.username,
        'rest_count': rest_count,
        'user_count': user_count,
        'order_count': order_count,
        'total_revenue': total_revenue_display,
    }
    response = render(request, 'admin_home.html', context)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def customer_home(request):
    response = None
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    if _normalize_role(user.role) == 'admin':
        return redirect('admin_home')
    restaurantList = Restaurant.objects.all()
    response = render(request, 'customer_home.html', {'restaurantList': restaurantList, 'username': user.username})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def open_signin(request):
    user = _get_logged_in_user(request)
    if user:
        if _normalize_role(user.role) == 'admin':
            return redirect('admin_home')
        return redirect('customer_home')
    return render(request, 'home.html', {'open_modal': 'signin', 'role': 'customer', 'form_data': {}})


def open_admin_signin(request):
    user = _get_logged_in_user(request)
    if user:
        if _normalize_role(user.role) == 'admin':
            return redirect('admin_home')
        return redirect('customer_home')
    return render(request, 'home.html', {'open_modal': 'signin', 'role': 'admin', 'form_data': {}})


def open_signup(request):
    return render(request, 'home.html', {'open_modal': 'signup', 'form_data': {}})

# def signin(request):
#     #DB's Data
#     user = "gamana"
#     pw = "123"
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         if user == username and pw == password:
#             # return HttpResponse(f"Username : {username} password : {password}")
#             return render(request, "success.html") 
#         else:
#             #return HttpResponse(f"Invalid response")
#             return render(request, "fail.html") 
    
#     else:
#         return HttpResponse("Invalid Request")

# def signin(request):
#     if request.method == 'POST':
#         # Fetching data from the form
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         try:
#             # Check if a user exists with the provided credentials
#             customer = User.objects.get(username=username, password=password)
#             return render(request, 'success.html')
#         except User.DoesNotExist:
#             # If credentials are invalid, show a failure page
#             return render(request, 'fail.html')
#     else:
#         return HttpResponse("Invalid Request")

def signin(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        selected_role = request.POST.get('role', 'customer').strip()

        if not username or not password:
            return render(request, 'home.html', {'open_modal': 'signin', 'role': selected_role, 'form_data': {'username': username}})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return render(request, 'home.html', {'open_modal': 'signin', 'role': selected_role, 'form_data': {'username': username}})

        if user.password != password:
            return render(request, 'home.html', {'open_modal': 'signin', 'role': selected_role, 'form_data': {'username': username}})

        stored_role = _normalize_role(getattr(user, 'role', ''))
        selected_role = selected_role.strip().lower() or 'customer'

        if stored_role not in ['customer', 'admin']:
            stored_role = 'customer'

        if selected_role not in ['customer', 'admin']:
            selected_role = 'customer'

        _set_user_session(request, user)
        if stored_role == 'admin' or username == 'admin':
            return redirect('admin_home')

        return redirect('customer_home')

    return render(request, 'home.html', {'open_modal': 'signin', 'role': 'customer'})


def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        address = request.POST.get('address', '').strip()
        role = request.POST.get('role', 'customer').strip()

        if role not in ['customer', 'admin']:
            role = 'customer'

        if not username or not password or not confirm_password or not email or not mobile or not address:
            return render(request, 'home.html', {'open_modal': 'signup', 'form_data': {'username': username, 'email': email, 'mobile': mobile, 'address': address}})

        if password != confirm_password:
            return render(request, 'home.html', {'open_modal': 'signup', 'form_data': {'username': username, 'email': email, 'mobile': mobile, 'address': address}})

        if username.lower() == password.lower():
            return render(request, 'home.html', {'open_modal': 'signup', 'form_data': {'username': username, 'email': email, 'mobile': mobile, 'address': address, 'role': role}})

        if User.objects.filter(username=username).exists():
            return render(request, 'home.html', {'open_modal': 'signup', 'form_data': {'username': username, 'email': email, 'mobile': mobile, 'address': address, 'role': role}})

        user = User(username=username, password=password, email=email, mobile=mobile, address=address, role=role)
        user.save()

        if role == 'admin':
            return redirect('open_admin_signin')
        return redirect('open_signin')

    return render(request, 'home.html', {'open_modal': 'signup'})

def logout(request):
    _clear_user_session(request)
    return redirect('home')


def heartbeat(request):
    session = getattr(request, 'session', None)
    if session is None:
        return JsonResponse({'logged_out': True, 'redirect_url': '/'}, status=401)

    if 'user_id' not in session or 'username' not in session:
        return JsonResponse({'logged_out': True, 'redirect_url': '/'}, status=401)

    session['last_activity'] = int(time.time())
    session.modified = True
    return JsonResponse({'status': 'ok'})


def forgot_password(request):
    username = request.GET.get('username') or request.POST.get('username')
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not username:
            return render(request, 'home.html', {'open_modal': 'forgot', 'form_data': {'username': username}})

        if new_password != confirm_password:
            return render(request, 'home.html', {'open_modal': 'forgot', 'form_data': {'username': username}})

        updated = User.objects.filter(username=username).update(password=new_password)
        if updated == 0:
            return render(request, 'home.html', {'open_modal': 'forgot', 'form_data': {'username': username}})

        user = User.objects.filter(username=username).first()
        if user and user.role == 'admin':
            return redirect('open_admin_signin')
        return redirect('open_signin')

    return render(request, 'home.html', {'open_modal': 'forgot'})
    
def open_add_restaurant(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    return render(request, 'add_restaurant.html', {'username': user.username})

def add_restaurant(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    if request.method == 'POST':
        name = request.POST.get('name')
        picture = request.POST.get('picture')
        cuisine = request.POST.get('cuisine')
        rating = request.POST.get('rating')

        try:
            Restaurant.objects.get(name=name)
            return redirect('open_add_restaurant')

        except Restaurant.DoesNotExist:
            Restaurant.objects.create(
                name=name,
                picture=picture,
                cuisine=cuisine,
                rating=rating,
            )
            return redirect('open_show_restaurant')

    return redirect('open_add_restaurant')

def open_show_restaurant(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurantList = Restaurant.objects.all()
    return render(request, 'show_restaurants.html',{"restaurantList" : restaurantList, 'username': user.username})

def open_orders(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    carts = Cart.objects.prefetch_related('items','customer').all()
    return render(request, 'admin_orders.html', {'username': user.username, 'carts': carts})


def open_users(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    users = User.objects.all().order_by('-role', 'username')
    return render(request, 'admin_users.html', {'username': user.username, 'users': users})


def open_view_user(request, user_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    target_user = get_object_or_404(User, id=user_id)
    return render(request, 'admin_view_user.html', {'username': user.username, 'target_user': target_user})


def open_update_user(request, user_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    target_user = get_object_or_404(User, id=user_id)
    return render(request, 'admin_update_user.html', {'username': user.username, 'target_user': target_user})


def update_user(request, user_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        address = request.POST.get('address', '').strip()
        role = request.POST.get('role', 'customer').strip()

        if not username or not email or not mobile or not address:
            return render(request, 'admin_update_user.html', {'username': user.username, 'target_user': target_user})

        if role not in ['customer', 'admin']:
            role = 'customer'

        if User.objects.filter(username=username).exclude(id=target_user.id).exists():
            return render(request, 'admin_update_user.html', {'username': user.username, 'target_user': target_user})

        target_user.username = username
        target_user.email = email
        target_user.mobile = mobile
        target_user.address = address
        target_user.role = role
        target_user.save()

        return redirect('open_users')

    return render(request, 'admin_update_user.html', {'username': user.username, 'target_user': target_user})


def delete_user(request, user_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == user.id:
        return redirect('open_users')
    target_user.delete()
    return redirect('open_users')


def open_update_restaurant(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    return render(request, 'update_restaurant.html', {"restaurant" : restaurant, 'username': user.username})

def update_restaurant(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id=restaurant_id)
    if request.method == "POST":
        restaurant.name = request.POST.get("name")
        restaurant.picture = request.POST.get("picture")
        restaurant.cuisine = request.POST.get("cuisine")
        restaurant.rating = request.POST.get("rating")
        restaurant.save()
        return redirect('open_show_restaurant')
    return render(request, 'update_restaurant.html', {'restaurant': restaurant, 'username': user.username})

def delete_restaurant(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    restaurant.delete()

    return redirect('open_show_restaurant')

def open_update_menu(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    itemList = restaurant.items.all()
    return render(request, 'update_menu.html',{"itemList" : itemList, "restaurant" : restaurant, 'username': user.username})

def update_menu(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        vegeterian = request.POST.get('vegeterian') == 'on'
        picture = request.POST.get('picture')
        
        try:
            Item.objects.get(name = name)
            return HttpResponse("Duplicate item!")
        except Item.DoesNotExist:
            Item.objects.create(
                restaurant = restaurant,
                name = name,
                description = description,
                price = price,
                vegeterian = vegeterian,
                picture = picture,
            )
        return redirect('open_update_menu', restaurant_id=restaurant.id)
    return render(request, 'update_menu.html', {"itemList": restaurant.items.all(), "restaurant": restaurant, 'username': user.username})


def update_menu_item(request, item_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        item.name = request.POST.get('name', item.name)
        item.description = request.POST.get('description', item.description)
        item.price = request.POST.get('price', item.price)
        item.vegeterian = request.POST.get('vegeterian') == 'on'
        item.picture = request.POST.get('picture', item.picture)
        item.save()
    return redirect('open_update_menu', restaurant_id=item.restaurant.id)


def delete_menu_item(request, item_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')

    item = get_object_or_404(Item, id=item_id)
    restaurant_id = item.restaurant.id

    if request.method not in {'POST', 'DELETE'}:
        return redirect('open_update_menu', restaurant_id=restaurant_id)

    item.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'message': 'Menu item deleted successfully!'})

    return redirect('open_update_menu', restaurant_id=restaurant_id)


def view_menu(request, restaurant_id, username):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'customer':
        return redirect('open_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    itemList = restaurant.items.all()
    return render(request, 'customer_menu.html',{"itemList" : itemList, "restaurant" : restaurant, "username": username})

def add_to_cart_ajax(request, item_id, username):
    user = _get_logged_in_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Please sign in first."}, status=401)
    item = Item.objects.get(id=item_id)
    customer = User.objects.get(username=username)

    cart, created = Cart.objects.get_or_create(customer=customer)
    cart.items.add(item)

    cart_state = dict(request.session.get('cart_state', {}))
    username_state = cart_state.get(username, {}) if isinstance(cart_state.get(username), dict) else {}
    username_state[str(item.id)] = int(username_state.get(str(item.id), 0)) + 1
    cart_state[username] = username_state
    request.session['cart_state'] = cart_state

    cart_count = sum(int(quantity) for quantity in username_state.values() if int(quantity) > 0)

    return JsonResponse({
        "status": "success",
        "message": f"'{item.name}' added to cart!",
        "cart_count": cart_count,
        "item_quantities": username_state,
    })


def remove_from_cart_ajax(request, item_id, username):
    user = _get_logged_in_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Please sign in first."}, status=401)

    item = Item.objects.get(id=item_id)
    customer = User.objects.get(username=username)
    cart = Cart.objects.filter(customer=customer).first()

    cart_state = dict(request.session.get('cart_state', {}))
    username_state = cart_state.get(username, {}) if isinstance(cart_state.get(username), dict) else {}
    if str(item.id) in username_state:
        new_quantity = max(0, int(username_state[str(item.id)]) - 1)
        if new_quantity == 0:
            username_state.pop(str(item.id), None)
            if cart and cart.items.filter(id=item.id).exists():
                cart.items.remove(item)
        else:
            username_state[str(item.id)] = new_quantity
    cart_state[username] = username_state
    request.session['cart_state'] = cart_state

    cart_count = sum(int(quantity) for quantity in username_state.values() if int(quantity) > 0)

    return JsonResponse({
        "status": "success",
        "message": f"'{item.name}' removed from cart!",
        "cart_count": cart_count,
        "item_quantities": username_state,
    })


def cart_count(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Please sign in first."}, status=401)

    customer = get_object_or_404(User, username=username)
    cart_state = dict(request.session.get('cart_state', {}))
    username_state = cart_state.get(username, {}) if isinstance(cart_state.get(username), dict) else {}
    cart_state[username] = username_state
    request.session['cart_state'] = cart_state

    cart_count = sum(int(quantity) for quantity in username_state.values() if int(quantity) > 0)

    return JsonResponse({"status": "success", "cart_count": cart_count, "item_quantities": username_state})


def show_cart(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    customer = User.objects.get(username = username)
    cart = Cart.objects.filter(customer=customer).first()
    items = cart.items.all() if cart else []
    total_price = cart.total_price() if cart else 0
    restaurant_id = None

    if items:
        first_item = items[0]
        if hasattr(first_item, 'restaurant_id') and first_item.restaurant_id:
            restaurant_id = first_item.restaurant_id

    response = render(request, 'cart.html', {
        "itemList": items,
        "total_price": total_price,
        "username": username,
        "restaurant_id": restaurant_id,
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def checkout(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    
    customer = get_object_or_404(User, username=username)  # Fixed: User not Customer
    cart = Cart.objects.filter(customer=customer).first()
    cart_items = cart.items.all() if cart else []
    total_price = cart.total_price() if cart else 0

    if total_price == 0:
        return render(request, 'checkout.html', {'error': 'Your cart is empty!'})

    amount_paisa = int(round(total_price * 100))

    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({
            'amount': amount_paisa,
            'currency': 'INR',
            'payment_capture': 1,
        })
    except Exception:
        return render(request, 'checkout.html', {'error': 'Unable to start payment. Please try again later.'})

    return render(request, 'checkout.html', {
        'username': username,
        'customer_email': customer.email,
        'customer_mobile': customer.mobile,
        'cart_items': cart_items,
        'total_price': total_price,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': order['id'],
        'amount_paisa': amount_paisa,
    })

@require_POST
def verify_payment(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return JsonResponse({'status': 'error', 'message': 'Please sign in first.'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid payment response.'}, status=400)

    if payload.get('demo_payment'):
        pass
    else:
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': payload.get('razorpay_order_id'),
                'razorpay_payment_id': payload.get('razorpay_payment_id'),
                'razorpay_signature': payload.get('razorpay_signature'),
            })
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'status': 'error', 'message': 'Payment verification failed.'}, status=400)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Payment verification failed.'}, status=400)

    customer = get_object_or_404(User, username=username)
    cart = Cart.objects.filter(customer=customer).first()
    cart_items = list(cart.items.all()) if cart else []
    restaurant_id = cart_items[0].restaurant_id if cart_items else None
    restaurant = Restaurant.objects.get(id=restaurant_id) if restaurant_id else None

    if cart and cart_items:
        order = Order.objects.create(
            customer=customer,
            restaurant=restaurant,
            total_amount=cart.total_price() if cart else 0,
            status='Pending',
            payment_status='Paid',
        )
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                item=item,
                name=item.name,
                price=item.price,
                quantity=1,
                picture=item.picture,
            )
        cart.items.clear()

    request.session['completed_order'] = {
        'restaurant_id': restaurant_id,
        'total_price': cart.total_price() if cart else 0,
    }

    return JsonResponse({
        'status': 'success',
        'redirect_url': reverse('orders', args=[username]),
    })

def orders(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    customer = get_object_or_404(User, username=username)
    if user.id != customer.id:
        return redirect('open_signin')
    completed_order = request.session.pop('completed_order', None)

    orders = Order.objects.filter(customer=customer).prefetch_related('items').order_by('-created_at')
    response = render(request, 'orders.html', {
        'username': username,
        'customer': customer,
        'orders': orders,
        'restaurant_id': completed_order.get('restaurant_id') if completed_order else None,
        'total_price': completed_order.get('total_price', 0) if completed_order else 0,
        'show_empty_state': not orders.exists(),
    })

    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response