from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ServiceTCO, CalculationTCO, CalculationService, CustomUser

# Register your models here.
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )

# Регистрируем модели
admin.site.register(ServiceTCO)
admin.site.register(CalculationTCO)
admin.site.register(CalculationService)

# Регистрируем кастомную модель пользователя
admin.site.register(CustomUser, CustomUserAdmin)