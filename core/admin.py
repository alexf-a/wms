from django.contrib import admin

from .models import Item, Location, LocationSharedAccess, Unit, UnitSharedAccess


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin interface for Item model."""

    list_display = ("name", "user", "unit", "quantity", "quantity_unit", "formatted_quantity", "created_on")
    list_filter = ("user", "unit", "created_on")
    search_fields = ("name", "description")
    readonly_fields = ("created_on", "formatted_quantity")


# Register your models here.
admin.site.register(Location)
admin.site.register(LocationSharedAccess)
admin.site.register(Unit)
admin.site.register(UnitSharedAccess)
