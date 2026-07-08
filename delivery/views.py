import json

import razorpay
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import User, Restaurant, Item, Cart


def _normalize_role(role):
    return str(role or '').strip().lower() or 'customer'


def _set_user_session(request, user):
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    request.session['role'] = _normalize_role(getattr(user, 'role', ''))


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
    return render(request, 'index.html')

def admin_home(request):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_admin_signin')
    if _normalize_role(user.role) != 'admin':
        return redirect('customer_home')
    return render(request, 'admin_home.html', {'username': user.username})


def customer_home(request):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    if _normalize_role(user.role) == 'admin':
        return redirect('admin_home')
    restaurantList = Restaurant.objects.all()
    return render(request, 'customer_home.html', {'restaurantList': restaurantList, 'username': user.username})


def open_signin(request):
    user = _get_logged_in_user(request)
    if user:
        if _normalize_role(user.role) == 'admin':
            return redirect('admin_home')
        return redirect('customer_home')
    return render(request, 'signin.html', {'page_title': 'Customer Sign In', 'role': 'customer'})


def open_admin_signin(request):
    user = _get_logged_in_user(request)
    if user:
        if _normalize_role(user.role) == 'admin':
            return redirect('admin_home')
        return redirect('customer_home')
    return render(request, 'signin.html', {'page_title': 'Admin Sign In', 'role': 'admin'})


def open_signup(request):
    return render(request, 'signup.html')

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
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'signin.html', {'page_title': 'Sign In', 'role': selected_role})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Please signup and create your account.')
            return render(request, 'signin.html', {'page_title': 'Sign In', 'role': selected_role})

        if user.password != password:
            messages.error(request, 'Please check your username or password correctly.')
            return render(request, 'signin.html', {'page_title': 'Sign In', 'role': selected_role})

        stored_role = _normalize_role(getattr(user, 'role', ''))
        selected_role = selected_role.strip().lower() or 'customer'

        if stored_role not in ['customer', 'admin']:
            stored_role = 'customer'

        if selected_role not in ['customer', 'admin']:
            selected_role = 'customer'

        _set_user_session(request, user)
        messages.success(request, f'Welcome back, {username}!')
        if stored_role == 'admin' or username == 'admin':
            return redirect('admin_home')

        return redirect('customer_home')

    return render(request, 'signin.html', {'page_title': 'Customer Sign In', 'role': 'customer'})


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
            messages.error(request, 'Please fill in all the fields.')
            return render(request, 'signup.html')

        if username == password:
            messages.error(request, 'Username and password cannot be the same.')
            return render(request, 'signup.html')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'This username is already registered. Please choose another one.')
            return render(request, 'signup.html')

        user = User(username=username, password=password, email=email, mobile=mobile, address=address, role=role)
        user.save()

        messages.success(request, 'Account created successfully. Please sign in with your new account.')
        if role == 'admin':
            return redirect('open_admin_signin')
        return redirect('open_signin')

    return render(request, 'signup.html')

def logout(request):
    _clear_user_session(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('open_signin')


def forgot_password(request):
    username = request.GET.get('username') or request.POST.get('username')
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not username:
            return render(request, 'forgot_password.html', {'error': 'Username is missing. Please go back and enter your username.'})

        if new_password != confirm_password:
            return render(request, 'forgot_password.html', {'username': username, 'error': 'Passwords do not match.'})

        updated = User.objects.filter(username=username).update(password=new_password)
        if updated == 0:
            return render(request, 'forgot_password.html', {'username': username, 'error': 'User not found.'})

        messages.success(request, 'Password changed successfully. Please sign in.')
        user = User.objects.filter(username=username).first()
        if user and user.role == 'admin':
            return redirect('open_admin_signin')
        return redirect('open_signin')

    return render(request, 'forgot_password.html', {'username': username})
    
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
            messages.error(request, 'This restaurant already exists.')
            return redirect('open_add_restaurant')

        except Restaurant.DoesNotExist:
            Restaurant.objects.create(
                name=name,
                picture=picture,
                cuisine=cuisine,
                rating=rating,
            )
            messages.success(request, 'Restaurant added successfully!')
            return redirect('open_show_restaurant')

    return redirect('open_add_restaurant')

def open_show_restaurant(request):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurantList = Restaurant.objects.all()
    return render(request, 'show_restaurants.html',{"restaurantList" : restaurantList, 'username': user.username})

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
        messages.success(request, 'Restaurant updated successfully!')
        return redirect('open_show_restaurant')
    return render(request, 'update_restaurant.html', {'restaurant': restaurant, 'username': user.username})

def delete_restaurant(request, restaurant_id):
    user = _get_logged_in_user(request)
    if not user or _normalize_role(user.role) != 'admin':
        return redirect('open_admin_signin')
    restaurant = Restaurant.objects.get(id = restaurant_id)
    restaurant.delete()
    messages.success(request, 'Restaurant deleted successfully!')

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
        except:
            Item.objects.create(
                restaurant = restaurant,
                name = name,
                description = description,
                price = price,
                vegeterian = vegeterian,
                picture = picture,
            )
        messages.success(request, 'Menu item added successfully!')
        return redirect('open_update_menu', restaurant_id=restaurant.id)
    return render(request, 'update_menu.html', {"itemList": restaurant.items.all(), "restaurant": restaurant, 'username': user.username})

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

    return JsonResponse({"status": "success", "message": f"'{item.name}' added to cart!"})

def show_cart(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    customer = User.objects.get(username = username)
    cart = Cart.objects.filter(customer=customer).first()
    items = cart.items.all() if cart else []
    total_price = cart.total_price() if cart else 0

    return render(request, 'cart.html',{"itemList" : items, "total_price" : total_price, "username":username})

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
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature({
            'razorpay_order_id': payload.get('razorpay_order_id'),
            'razorpay_payment_id': payload.get('razorpay_payment_id'),
            'razorpay_signature': payload.get('razorpay_signature'),
        })
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid payment response.'}, status=400)
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'status': 'error', 'message': 'Payment verification failed.'}, status=400)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Payment verification failed.'}, status=400)

    customer = get_object_or_404(User, username=username)
    cart = Cart.objects.filter(customer=customer).first()
    cart_items = list(cart.items.all()) if cart else []
    restaurant_id = cart_items[0].restaurant_id if cart_items else None

    request.session['completed_order'] = {
        'restaurant_id': restaurant_id,
        'total_price': cart.total_price() if cart else 0,
    }

    if cart:
        cart.items.clear()

    return JsonResponse({
        'status': 'success',
        'redirect_url': reverse('orders', args=[username]),
    })

def orders(request, username):
    user = _get_logged_in_user(request)
    if not user:
        return redirect('open_signin')
    customer = get_object_or_404(User, username=username)
    completed_order = request.session.pop('completed_order', None)

    if not completed_order:
        return redirect('show_cart', username=username)

    restaurant_id = completed_order.get('restaurant_id')

    return render(request, 'orders.html', {
        'username': username,
        'customer': customer,
        'restaurant_id': restaurant_id,
        'total_price': completed_order.get('total_price', 0),
    })