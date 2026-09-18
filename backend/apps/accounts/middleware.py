from apps.core.context import owner_context


class OwnerContextMiddleware:
    """Binds the authenticated user as the current owner for the whole request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            with owner_context(user.pk):
                return self.get_response(request)
        return self.get_response(request)
