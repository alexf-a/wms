from django.contrib import admin

from .models import Location, LocationSharedAccess, Unit, UnitSharedAccess

# Register your models here.
admin.site.register(Location)
admin.site.register(LocationSharedAccess)
admin.site.register(Unit)
admin.site.register(UnitSharedAccess)
