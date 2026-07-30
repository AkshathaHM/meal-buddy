from .views import _get_logged_in_user


def auth_user(request):
    user = _get_logged_in_user(request)
    if user is None:
        for key in ('user_id', 'username', 'role'):
            if key in request.session:
                del request.session[key]
    return {'logged_in_user': user}
