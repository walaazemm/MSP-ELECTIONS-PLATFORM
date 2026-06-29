from django.contrib import admin
from .models import Wilaya, Commune, CommuneSettings

class CommuneSettingsInline(admin.StackedInline):
    model = CommuneSettings
    can_delete = False

@admin.register(Wilaya)
class WilayaAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_fr', 'name_ar')
    search_fields = ('name_fr', 'name_ar', 'code')
    ordering = ('code',)

@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_fr', 'name_ar', 'wilaya')
    list_filter = ('wilaya',)
    search_fields = ('name_fr', 'name_ar', 'code')
    inlines = (CommuneSettingsInline,) # Shows settings directly inside the Commune page