from django.test import TestCase
from django.urls import reverse
from .models import Restaurant, User


class AuthFlowTests(TestCase):
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
        self.assertContains(response, 'Username and password cannot be the same.')
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
        self.assertContains(response, 'Passwords do not match.')
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_signin_with_invalid_password_shows_error(self):
        User.objects.create(username='alice', password='Secret123', email='a@example.com', mobile='1111111111', address='X')

        response = self.client.post(reverse('signin'), {'username': 'alice', 'password': 'wrongpass'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please check your username or password correctly.')

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

    def test_signin_allows_matching_credentials_without_role_error(self):
        User.objects.create(username='matchuser', password='Match123', email='match@example.com', mobile='2223334445', address='Match Street', role='customer')

        response = self.client.post(reverse('signin'), {'username': 'matchuser', 'password': 'Match123', 'role': 'customer'}, follow=True)

        self.assertRedirects(response, reverse('customer_home'))
        self.assertTemplateUsed(response, 'customer_home.html')
        self.assertNotContains(response, 'Please use the correct sign-in page for this account.')

    def test_delete_restaurant_shows_success_notification(self):
        user = User.objects.create(username='adminonly', password='Admin123', email='admin@example.com', mobile='1234567890', address='Main Street', role='admin')
        session = self.client.session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session.save()

        restaurant = Restaurant.objects.create(name='Pizza Place', cuisine='Italian', rating=4.5)

        response = self.client.get(reverse('delete_restaurant', args=[restaurant.id]), follow=True)

        self.assertRedirects(response, reverse('open_show_restaurant'))
        self.assertContains(response, 'Restaurant deleted successfully!')
        self.assertFalse(Restaurant.objects.filter(id=restaurant.id).exists())

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

    def test_signin_with_unknown_user_shows_signup_message(self):
        response = self.client.post(reverse('signin'), {'username': 'ghost', 'password': 'WrongPass123'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please signup and create your account.')

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

        self.assertRedirects(response, reverse('open_signin'))
        self.assertNotIn('username', self.client.session)
