from django.contrib import admin


class OwnedModelAdmin(admin.ModelAdmin):
    """Admin is deliberate global access: uses `all_users`, shows the owner column."""

    def get_queryset(self, request):
        qs = self.model.all_users.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_display(self, request):
        base = list(super().get_list_display(request))
        if "user" not in base and base != ["__str__"]:
            base.append("user")
        return base
