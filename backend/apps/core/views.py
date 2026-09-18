from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.views import View


def healthcheck(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


class SPAView(View):
    """Serves the built frontend's index.html for client-side routes (production)."""

    def get(self, request, *args, **kwargs):
        index = settings.FRONTEND_DIST / "index.html"
        if not index.exists():
            if settings.DEBUG:
                return JsonResponse(
                    {"detail": "Frontend not built. Run the Vite dev server on :5173."},
                    status=404,
                )
            raise Http404
        return FileResponse(open(index, "rb"), content_type="text/html")
