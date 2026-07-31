import json
import time
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from .models import Restaurant, User, Item, Cart, Order, OrderItem


class AuthFlowTests(TestCase):
    @override_settings(SESSION_COOKIE_AGE=3600, SESSION_SAVE_EVERY_REQUEST=True, SESSION_EXPIRE_AT_BROWSER_CLOSE=False)
    def test_session_settings_use_one_hour_sliding_expiration(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 3600)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_signup_rejects_username_and_password_that_match(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'admin',
                'password': 'admin',
                'confirm_password': 'admin',
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'address': 'Main Street',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'message-box')
        self.assertNotContains(response, 'Username and password cannot be the same.')
        self.assertFalse(User.objects.filter(username='admin').exists())

    def test_signup_requires_matching_password_confirmation(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newuser',
                'password': 'StrongPass1',
                'confirm_password': 'DifferentPass2',
                'email': 'user@example.com',
                'mobile': '9876543210',
                'address': 'Another Street',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'message-box')
        self.assertNotContains(response, 'Passwords do not match.')
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_signin_with_invalid_password_does_not_render_notification(self):
        User.objects.create(username='alice', password='Secret123', email='a@example.com', mobile='1111111111', address='X')

        response = self.client.post(reverse('signin'), {'username': 'alice', 'password': 'wrongpass'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'message-box')
        self.assertNotContains(response, 'Please check your username or password correctly.')

    def test_signin_with_valid_credentials_returns_customer_home(self):
        User.objects.create(username='alice', password='Secret123', email='a@example.com', mobile='1111111111', address='X')

        response = self.client.post(reverse('signin'), {'username': 'alice', 'password': 'Secret123'}, follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')

    def test_signin_accepts_legacy_account_without_role(self):
        User.objects.create(username='legacyuser', password='Legacy123', email='legacy@example.com', mobile='1111111111', address='X', role='')

        response = self.client.post(reverse('signin'), {'username': 'legacyuser', 'password': 'Legacy123', 'role': 'customer'}, follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')

    def test_inactive_customer_session_redirects_to_customer_login(self):
        user = User.objects.create(username='inactiveuser', password='Secret123', email='inactive@example.com', mobile='1111111111', address='X', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = 'customer'
        session['last_activity'] = int(time.time()) - 3700
        session.save()

        response = self.client.get(reverse('customer_home'), follow=True)

        self.assertRedirects(response, reverse('open_signin'))
        self.assertContains(response, 'Your session has expired. Please login again.')

    def test_inactive_admin_session_redirects_to_admin_login(self):
        user = User.objects.create(username='inactiveadmin', password='Secret123', email='inactive-admin@example.com', mobile='1111111111', address='X', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = 'admin'
        session['last_activity'] = int(time.time()) - 3700
        session.save()

        response = self.client.get(reverse('admin_home'), follow=True)

        self.assertRedirects(response, reverse('open_admin_signin'))
        self.assertContains(response, 'Your session has expired. Please login again.')

    def test_inactive_django_admin_session_redirects_to_admin_login(self):
        session = self.client.session
        session['_auth_user_id'] = '1'
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session['_auth_user_hash'] = 'expired'
        session['last_activity'] = int(time.time()) - 3700
        session.save()

        response = self.client.get('/admin/', follow=True)

        self.assertRedirects(response, '/admin/login/')
        self.assertContains(response, 'Your session has expired. Please login again.')

    def test_admin_revenue_includes_only_successfully_paid_orders(self):
        admin = User.objects.create(username='revenueadmin', password='Admin123', email='revenue-admin@example.com', mobile='1111111111', address='X', role='admin')
        customer = User.objects.create(username='revenuecustomer', password='Secret123', email='revenue-customer@example.com', mobile='2222222222', address='Y', role='customer')
        Order.objects.create(customer=customer, total_amount=125.50, payment_status='Paid')
        Order.objects.create(customer=customer, total_amount=80.00, payment_status='Pending')

        session = self.client.session
        session['user_id'] = admin.id
        session['username'] = admin.username
        session['role'] = 'admin'
        session.save()

        response = self.client.get(reverse('admin_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '125.50')
        self.assertNotContains(response, '205.50')

    def test_admin_orders_show_success_for_paid_and_pending_for_unpaid(self):
        admin = User.objects.create(username='ordersadmin', password='Admin123', email='orders-admin@example.com', mobile='1111111111', address='X', role='admin')
        paid_customer = User.objects.create(username='paidcustomer', password='Secret123', email='paid@example.com', mobile='2222222222', address='Y', role='customer')
        pending_customer = User.objects.create(username='pendingcustomer', password='Secret123', email='pending@example.com', mobile='3333333333', address='Z', role='customer')
        Order.objects.create(customer=paid_customer, total_amount=125.50, payment_status='Paid')
        restaurant = Restaurant.objects.create(name='Pending Kitchen', cuisine='Indian', rating=4.5)
        item = Item.objects.create(restaurant=restaurant, name='Pending Item', description='Pending order item', price=80.00, vegeterian=False)
        pending_cart = Cart.objects.create(customer=pending_customer)
        pending_cart.items.add(item)

        session = self.client.session
        session['user_id'] = admin.id
        session['username'] = admin.username
        session['role'] = 'admin'
        session.save()

        response = self.client.get(reverse('open_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Success')
        self.assertContains(response, 'Pending')
        self.assertContains(response, '125.50')
        self.assertContains(response, '80.00')

    def test_signin_allows_matching_credentials_without_role_error(self):
        User.objects.create(username='matchuser', password='Match123', email='match@example.com', mobile='2223334445', address='Match Street', role='customer')

        response = self.client.post(reverse('signin'), {'username': 'matchuser', 'password': 'Match123', 'role': 'customer'}, follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')
        self.assertNotContains(response, 'Please use the correct sign-in page for this account.')

    def test_payment_verification_persists_customer_order(self):
        customer = User.objects.create(username='payuser', password='Secret123', email='pay@example.com', mobile='1111111111', address='X', role='customer')
        session = self.client.session
        session['user_id'] = customer.id
        session['username'] = customer.username
        session['role'] = 'customer'
        session.save()

        restaurant = Restaurant.objects.create(name='Tasty Bites', cuisine='Indian', rating=4.8)
        item = Item.objects.create(restaurant=restaurant, name='Biriyani', description='Spicy rice', price=180.0, vegeterian=False, picture='https://example.com/biriyani.jpg')
        cart = Cart.objects.create(customer=customer)
        cart.items.add(item)

        with patch('delivery.views.razorpay.Client') as mocked_client:
            mocked_client.return_value.utility.verify_payment_signature.return_value = None
            mocked_client.return_value.order.create.return_value = {'id': 'order_123'}

            response = self.client.post(
                reverse('verify_payment', args=[customer.username]),
                {
                    'razorpay_order_id': 'order_123',
                    'razorpay_payment_id': 'pay_123',
                    'razorpay_signature': 'signature',
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Order.objects.filter(customer=customer).exists())
        order = Order.objects.get(customer=customer)
        self.assertEqual(order.total_amount, 180.0)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().item.name, 'Biriyani')

        order_page = self.client.get(reverse('orders', args=[customer.username]))
        self.assertEqual(order_page.status_code, 200)
        self.assertContains(order_page, 'Biriyani')
        self.assertContains(order_page, 'Tasty Bites')

    def test_payment_verification_accepts_demo_payload_without_sdk(self):
        customer = User.objects.create(username='demouser', password='Secret123', email='demo@example.com', mobile='1111111111', address='X', role='customer')
        session = self.client.session
        session['user_id'] = customer.id
        session['username'] = customer.username
        session['role'] = 'customer'
        session.save()

        restaurant = Restaurant.objects.create(name='Demo Kitchen', cuisine='Indian', rating=4.7)
        item = Item.objects.create(restaurant=restaurant, name='Veg Roll', description='Roll', price=95.0, vegeterian=True, picture='https://example.com/roll.jpg')
        cart = Cart.objects.create(customer=customer)
        cart.items.add(item)

        response = self.client.post(
            reverse('verify_payment', args=[customer.username]),
            json.dumps({'demo_payment': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Order.objects.filter(customer=customer).exists())
        self.assertEqual(Order.objects.get(customer=customer).total_amount, 95.0)

    def test_delete_restaurant_redirects_without_notification(self):
        user = User.objects.create(username='adminonly', password='Admin123', email='admin@example.com', mobile='1234567890', address='Main Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Pizza Place', cuisine='Italian', rating=4.5)

        response = self.client.get(reverse('delete_restaurant', args=[restaurant.id]), follow=True)

        self.assertRedirects(response, reverse('open_show_restaurant'))
        self.assertNotContains(response, 'Restaurant deleted successfully!')
        self.assertFalse(Restaurant.objects.filter(id=restaurant.id).exists())

    def test_delete_menu_item_removes_item(self):
        user = User.objects.create(username='adminmenu', password='Admin123', email='admin2@example.com', mobile='1234567891', address='Main Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Burger House', cuisine='Fast Food', rating=4.6)
        item = Item.objects.create(
            restaurant=restaurant,
            name='Classic Burger',
            description='Juicy burger',
            price=120.0,
            vegeterian=False,
            picture='https://example.com/burger.jpg',
        )

        response = self.client.post(reverse('delete_menu_item', args=[item.id]), follow=True)

        self.assertRedirects(response, reverse('open_update_menu', args=[restaurant.id]))
        self.assertFalse(Item.objects.filter(id=item.id).exists())

    def test_update_menu_page_contains_add_item_popup_controls(self):
        user = User.objects.create(username='adminadd', password='Admin123', email='admin3@example.com', mobile='1234567892', address='Main Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Pizza Corner', cuisine='Italian', rating=4.8)

        response = self.client.get(reverse('open_update_menu', args=[restaurant.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'open-add-item-btn')
        self.assertContains(response, 'id="addItemForm"')

    def test_update_menu_item_uploads_image_and_preserves_it_without_replacement(self):
        user = User.objects.create(username='adminimage', password='Admin123', email='admin4@example.com', mobile='1234567893', address='Main Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Image Kitchen', cuisine='Italian', rating=4.8)
        item = Item.objects.create(restaurant=restaurant, name='Image Pasta', description='Fresh pasta', price=150.0)
        image_data = (
            b'\x89PNG\r\n\x1a\n'
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('update_menu_item', args=[item.id]),
                    {
                        'name': item.name,
                        'description': item.description,
                        'price': item.price,
                        'picture': '',
                        'image': SimpleUploadedFile('pasta.png', image_data, content_type='image/png'),
                    },
                )
                self.assertRedirects(response, reverse('open_update_menu', args=[restaurant.id]))
                item.refresh_from_db()
                saved_image_name = item.image.name
                self.assertTrue(saved_image_name.startswith('menu_items/'))

                self.client.post(
                    reverse('update_menu_item', args=[item.id]),
                    {
                        'name': 'Updated Pasta',
                        'description': item.description,
                        'price': item.price,
                        'picture': '',
                    },
                )
                item.refresh_from_db()
                self.assertEqual(item.image.name, saved_image_name)

                page = self.client.get(reverse('open_update_menu', args=[restaurant.id]))
                self.assertContains(page, item.image.url)

    def test_signup_as_admin_redirects_to_admin_home(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'adminuser',
                'password': 'Admin123',
                'confirm_password': 'Admin123',
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'address': 'Admin Street',
                'role': 'admin',
            },
            follow=True,
        )

        self.assertTrue(User.objects.filter(username='adminuser', role='admin').exists())
        self.assertRedirects(response, reverse('open_admin_signin'))
        self.assertNotIn('user_id', self.client.session)

    def test_signin_with_unknown_user_does_not_show_signup_message(self):
        response = self.client.post(reverse('signin'), {'username': 'ghost', 'password': 'WrongPass123'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'message-box')
        self.assertNotContains(response, 'Please signup and create your account.')

    def test_customer_opening_admin_signin_redirects_to_customer_home(self):
        user = User.objects.create(username='customeruser', password='Customer123', email='customer@example.com', mobile='5555555555', address='Customer Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('open_admin_signin'), follow=True)

        self.assertRedirects(response, reverse('customer_home'))

    def test_signup_logs_user_in_and_redirects_to_customer_home(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'signedupuser',
                'password': 'StrongPass1',
                'confirm_password': 'StrongPass1',
                'email': 'signedup@example.com',
                'mobile': '1112223334',
                'address': 'New Home',
                'role': 'customer',
            },
            follow=True,
        )

        self.assertTrue(User.objects.filter(username='signedupuser').exists())
        self.assertNotIn('user_id', self.client.session)
        self.assertRedirects(response, reverse('open_signin'))

    def test_logout_clears_user_session(self):
        user = User.objects.create(username='logoutuser', password='Logout123', email='logout@example.com', mobile='9998887776', address='X')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.post(reverse('logout'), follow=True)

        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('username', self.client.session)

    def test_home_page_header_shows_auth_buttons_for_guests(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="signupBtn"')
        self.assertContains(response, 'id="signinBtn"')
        self.assertContains(response, 'Sign Up')
        self.assertContains(response, 'Sign In')

    def test_signed_in_customer_is_redirected_from_home_to_dashboard(self):
        user = User.objects.create(username='homeredirect', password='Profile123', email='homeredirect@example.com', mobile='6667778888', address='Profile Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('home'), follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')

    def test_home_page_header_shows_profile_dropdown_for_signed_in_customer(self):
        user = User.objects.create(username='homeprofile', password='Profile123', email='homeprofile@example.com', mobile='6667778888', address='Profile Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('home'), follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')

    def test_customer_header_logo_links_to_customer_home(self):
        user = User.objects.create(username='profileuser', password='Profile123', email='profile@example.com', mobile='6667778888', address='Profile Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('customer_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("customer_home")}"')

    def test_customer_home_response_is_not_cached(self):
        user = User.objects.create(username='cacheuser', password='Cache123', email='cache@example.com', mobile='6667778888', address='Cache Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('customer_home'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', '').lower())

    def test_customer_header_renders_profile_dropdown_options(self):
        user = User.objects.create(username='profileuser', password='Profile123', email='profile@example.com', mobile='6667778888', address='Profile Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('customer_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="profile-dropdown-menu"')
        self.assertContains(response, 'View Profile')
        self.assertContains(response, 'Orders')
        self.assertContains(response, 'Cart')

    def test_cart_page_response_is_not_cached(self):
        user = User.objects.create(username='cartcache', password='Cart123', email='cartcache@example.com', mobile='6667778888', address='Cart Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('show_cart', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', '').lower())

    def test_orders_page_response_is_not_cached(self):
        user = User.objects.create(username='orderscache', password='Orders123', email='orderscache@example.com', mobile='6667778888', address='Orders Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('orders', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', '').lower())

    def test_customer_profile_dropdown_uses_modal_trigger_for_view_profile(self):
        user = User.objects.create(username='profilemodaluser', password='Profile123', email='profilemodal@example.com', mobile='6667778889', address='Profile Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('customer_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-action="view"')
        self.assertContains(response, 'href="/orders/profilemodaluser/"')

    def test_admin_header_logo_links_to_admin_home(self):
        user = User.objects.create(username='adminprofile', password='Admin123', email='adminprofile@example.com', mobile='6667778889', address='Admin Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('admin_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("admin_home")}"')

    def test_admin_home_response_is_not_cached(self):
        user = User.objects.create(username='admincache', password='Admin123', email='admincache@example.com', mobile='6667778889', address='Admin Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('admin_home'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', '').lower())

    def test_admin_header_renders_profile_dropdown_options(self):
        user = User.objects.create(username='adminprofile', password='Admin123', email='adminprofile@example.com', mobile='6667778889', address='Admin Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('admin_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="profile-dropdown-menu"')
        self.assertContains(response, 'View Profile')
        self.assertContains(response, 'Logout')

    def test_customer_menu_page_has_explore_restaurant_link(self):
        user = User.objects.create(username='menuuser', password='Menu123', email='menu@example.com', mobile='6667778888', address='Menu Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Street Bites', cuisine='Fast Food', rating=4.4)
        Item.objects.create(
            restaurant=restaurant,
            name='Wrap',
            description='Fresh wrap',
            price=90.0,
            vegeterian=True,
            picture='https://example.com/wrap.jpg',
        )

        response = self.client.get(reverse('view_menu', args=[restaurant.id, user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '← Explore Restaurant')
        self.assertContains(response, reverse('customer_home'))

    def test_customer_menu_page_renders_quantity_controls_shell(self):
        user = User.objects.create(username='qtyuser', password='Qty123', email='qty@example.com', mobile='3334445555', address='Qty Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Tandoor Point', cuisine='Indian', rating=4.7)
        Item.objects.create(
            restaurant=restaurant,
            name='Paneer Tikka',
            description='Chargrilled paneer',
            price=130.0,
            vegeterian=True,
            picture='https://example.com/tikka.jpg',
        )

        response = self.client.get(reverse('view_menu', args=[restaurant.id, user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="quantity-shell"')
        self.assertContains(response, 'Add')

    def test_add_to_cart_ajax_returns_server_cart_count(self):
        user = User.objects.create(username='ajaxcart', password='Ajax123', email='ajax@example.com', mobile='7778889990', address='Ajax Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Snack Bar', cuisine='Snacks', rating=4.2)
        item = Item.objects.create(
            restaurant=restaurant,
            name='Fries',
            description='Crispy fries',
            price=70.0,
            vegeterian=True,
            picture='https://example.com/fries.jpg',
        )

        response = self.client.get(reverse('add_to_cart_ajax', args=[item.id, user.username]), {'delta': 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cart_count'], 1)
        self.assertEqual(response.json()['item_quantities'][str(item.id)], 1)
        self.assertEqual(self.client.session.get('cart_state', {}).get(user.username, {}).get(str(item.id)), 1)

    def test_cart_count_tracks_quantity_across_plus_and_minus_clicks(self):
        user = User.objects.create(username='qtycounter', password='Qty1234', email='qtycounter@example.com', mobile='2223334444', address='Qty Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Quick Bite', cuisine='Fast Food', rating=4.3)
        item = Item.objects.create(
            restaurant=restaurant,
            name='Pizza Slice',
            description='Cheesy slice',
            price=80.0,
            vegeterian=True,
            picture='https://example.com/pizza.jpg',
        )

        first_add = self.client.get(reverse('add_to_cart_ajax', args=[item.id, user.username]))
        second_add = self.client.get(reverse('add_to_cart_ajax', args=[item.id, user.username]))
        first_remove = self.client.get(reverse('remove_from_cart_ajax', args=[item.id, user.username]))
        count_check = self.client.get(reverse('cart_count', args=[user.username]))

        self.assertEqual(first_add.json()['cart_count'], 1)
        self.assertEqual(second_add.json()['cart_count'], 2)
        self.assertEqual(first_remove.json()['cart_count'], 1)
        self.assertEqual(count_check.json()['cart_count'], 1)

    def test_cart_page_has_no_remove_button_for_each_item(self):
        user = User.objects.create(username='cartuser', password='Cart123', email='cart@example.com', mobile='4445556666', address='Cart Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Biryani House', cuisine='Indian', rating=4.9)
        item = Item.objects.create(
            restaurant=restaurant,
            name='Chicken Biryani',
            description='Spiced rice bowl',
            price=160.0,
            vegeterian=False,
            picture='https://example.com/biryani.jpg',
        )

        cart = Cart.objects.create(customer=user)
        cart.items.add(item)

        response = self.client.get(reverse('show_cart', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'cart-remove-btn')
        self.assertNotContains(response, 'aria-label="Remove item from cart"')

    def test_cart_page_has_explore_more_food_link_for_restaurant(self):
        user = User.objects.create(username='cartuser', password='Cart123', email='cart@example.com', mobile='4445556666', address='Cart Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Biryani House', cuisine='Indian', rating=4.9)
        item = Item.objects.create(
            restaurant=restaurant,
            name='Chicken Biryani',
            description='Spiced rice bowl',
            price=160.0,
            vegeterian=False,
            picture='https://example.com/biryani.jpg',
        )

        cart = Cart.objects.create(customer=user)
        cart.items.add(item)

        response = self.client.get(reverse('show_cart', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '← Explore more food')
        self.assertContains(response, reverse('view_menu', args=[restaurant.id, user.username]))

    def test_orders_page_shows_no_orders_message_when_no_completed_order_exists(self):
        user = User.objects.create(username='ordersuser', password='Orders123', email='orders@example.com', mobile='1112223334', address='Orders Street', role='customer')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        response = self.client.get(reverse('orders', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No orders yet')
        self.assertContains(response, 'View Restaurants')
        self.assertContains(response, reverse('customer_home'))
