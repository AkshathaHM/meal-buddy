import time

from django.conf import settings
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
            has_session_user = 'user_id' in session and 'username' in session

            if has_session_user:
                last_activity = session.get('last_activity')
                if last_activity is not None:
                    if now - int(last_activity) > timeout_seconds:
                        session.flush()
                        if request.path == '/heartbeat/' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                            return JsonResponse({'logged_out': True, 'redirect_url': '/'}, status=401)
                        return redirect('home')

                session['last_activity'] = now
                session.modified = True

        return self.get_response(request)
