import time

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


class InactivityLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = getattr(request, 'session', None)
        if session is not None:
            timeout_seconds = getattr(settings, 'SESSION_INACTIVITY_TIMEOUT', 3600)
            now = int(time.time())
            has_custom_user = 'user_id' in session and 'username' in session
            has_django_user = '_auth_user_id' in session
            has_authenticated_user = has_custom_user or has_django_user

            if has_authenticated_user:
                last_activity = session.get('last_activity')
                if last_activity is not None:
                    if now - int(last_activity) > timeout_seconds:
                        is_ajax = request.path == '/heartbeat/' or request.headers.get('x-requested-with') == 'XMLHttpRequest'
                        if has_django_user:
                            login_url = '/admin/login/'
                        elif session.get('role') == 'admin':
                            login_url = '/open_admin_signin'
                        else:
                            login_url = '/open_signin'
                        session.flush()
                        messages.warning(request, 'Your session has expired. Please login again.')
                        if is_ajax:
                            return JsonResponse({'logged_out': True, 'redirect_url': login_url}, status=401)
                        return redirect(login_url)

                session['last_activity'] = now
                session.modified = True

        return self.get_response(request)
