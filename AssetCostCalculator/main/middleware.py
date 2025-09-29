from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt


class DisableCSRFForAPI(MiddlewareMixin):
    """Отключает CSRF для всех API эндпоинтов"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Проверяем, является ли это API запросом
        if request.path.startswith('/api/'):
            # Применяем csrf_exempt к view
            return csrf_exempt(view_func)(request, *view_args, **view_kwargs)
        return None


