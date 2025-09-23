from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import ServiceTCO, Calculation, CalculationService

# Register your models here.
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_moderator', 'is_staff')
    list_filter = ('is_moderator', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительные поля', {'fields': ('is_moderator',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительные поля', {'fields': ('is_moderator',)}),
    )

# Регистрируем модели
admin.site.register(ServiceTCO)
admin.site.register(Calculation)
admin.site.register(CalculationService)

# Перерегистрируем User с кастомной админкой
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)