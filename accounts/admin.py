from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserRole

class UserRoleInline(admin.StackedInline):
    model = UserRole
    can_delete = False
    verbose_name_plural = 'Role & Scope'

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserRoleInline,)
    list_display = ('email', 'full_name', 'is_staff', 'get_role', 'created_at')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role_profile__role')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('email',)
    
    # Override fieldsets to match our CustomUser model exactly
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'phone', 'language_pref')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    
    # Add fields for the "Add User" form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'language_pref'),
        }),
    )
    
    # Make some fields readonly on change (not on create)
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing user
            return ('email', 'created_at', 'last_login')
        return ()

    def get_role(self, obj):
        try:
            return obj.role_profile.get_role_display()
        except UserRole.DoesNotExist:
            return "— No Role —"
    get_role.short_description = 'Role'

admin.site.register(CustomUser, CustomUserAdmin)