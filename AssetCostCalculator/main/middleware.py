from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


class DisableCSRFForAPI(MiddlewareMixin):
    """Отключает CSRF для всех API эндпоинтов"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Проверяем, является ли это API запросом
        if request.path.startswith('/api/'):
            # Применяем csrf_exempt к view
            return csrf_exempt(view_func)(request, *view_args, **view_kwargs)
        return None
    
    def process_request(self, request):
        # Дополнительно отключаем CSRF проверку для API
        if request.path.startswith('/api/'):
            request.csrf_processing_done = True
            return None


class SimpleCorsMiddleware(MiddlewareMixin):
    """Простой CORS middleware для React разработки"""
    
    def process_response(self, request, response):
        # Разрешаем запросы с React приложения
        if request.path.startswith('/api/') or request.path.startswith('/swagger'):
            # Получаем origin из запроса
            origin = request.META.get('HTTP_ORIGIN', '')
            # Разрешенные источники
            allowed_origins = [
                'http://localhost:3000',
                'http://127.0.0.1:3000',
                'https://localhost:5173',
                'http://localhost:5173',
                'http://127.0.0.1:5173',
            ]
            
            # Если origin в списке разрешенных, используем его, иначе используем первый
            if origin in allowed_origins:
                response['Access-Control-Allow-Origin'] = origin
            else:
                response['Access-Control-Allow-Origin'] = allowed_origins[0]
            
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
        
        # Обрабатываем preflight запросы
        if request.method == 'OPTIONS':
            response.status_code = 200
        
        return response


