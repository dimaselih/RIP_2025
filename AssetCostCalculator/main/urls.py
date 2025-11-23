from django.urls import path, include
from rest_framework import permissions, routers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from . import views

# Настройки безопасности для Swagger
security_definitions = {
    "SessionAuthentication": {
        "type": "apiKey",
        "in": "cookie",
        "name": "sessionid",
        "description": "Session ID для аутентификации через куки"
    }
}

# Создаем router для ViewSet согласно методичке
router = routers.DefaultRouter()
router.register(r'user', views.UserViewSet, basename='user')

schema_view = get_schema_view(
    openapi.Info(
        title="Asset Cost Calculator API",
        default_version='v1',
        description="API для системы расчета стоимости активов TCO",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Старые Django views (HTML)
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:service_id>/', views.service_detail, name='service_detail'),
    path('calculation/<int:calculation_id>/', views.calculation, name='calculation'),
    path('add-service/', views.add_service_to_calculation, name='add_service_to_calculation'),
    path('delete-calculation/', views.delete_calculation, name='delete_calculation'),
    
    # ==================== API URLS ====================
    # Домен "Услуга" (7 эндпоинтов)
    path('api/service_tco/', views.ServiceListAPIView.as_view(), name='api-servicetco-list'),
    path('api/service_tco/<int:pk>/', views.ServiceDetailAPIView.as_view(), name='api-servicetco-detail'),
    path('api/service_tco/create/', views.ServiceCreateAPIView.as_view(), name='api-servicetco-create'),
    path('api/service_tco/<int:pk>/update/', views.ServiceUpdateAPIView.as_view(), name='api-servicetco-update'),
    path('api/service_tco/<int:pk>/delete/', views.ServiceDeleteAPIView.as_view(), name='api-servicetco-delete'),
    path('api/service_tco/<int:pk>/add-to-cart/', views.ServiceAddToCartAPIView.as_view(), name='api-servicetco-add-to-cart'),
    path('api/service_tco/<int:pk>/image/', views.ServiceImageUploadAPIView.as_view(), name='api-servicetco-image'),
    
    # Домен "Заявка" (7 эндпоинтов)
    path('api/cart_tco/', views.CartIconAPIView.as_view(), name='api-cart-icon'),
    path('api/calculation_tco/', views.CalculationTCOListAPIView.as_view(), name='api-calculation-list'),
    path('api/calculation_tco/<int:pk>/', views.CalculationTCODetailAPIView.as_view(), name='api-calculation-detail'),
    path('api/calculation_tco/<int:pk>/update/', views.CalculationTCOUpdateAPIView.as_view(), name='api-calculation-update'),
    path('api/calculation_tco/<int:pk>/form/', views.CalculationTCOFormAPIView.as_view(), name='api-calculation-form'),
    path('api/calculation_tco/<int:pk>/complete/', views.CalculationTCOCompleteAPIView.as_view(), name='api-calculation-complete'),
    path('api/calculation_tco/<int:pk>/delete/', views.CalculationTCODeleteAPIView.as_view(), name='api-calculation-delete'),
    
    # Домен "М-М" (корзина) - 2 эндпоинта
    path('api/calculation-service/', views.CalculationTCOServiceDeleteAPIView.as_view(), name='api-calculation-service-delete'),
    path('api/calculation-service/update/', views.CalculationTCOServiceUpdateAPIView.as_view(), name='api-calculation-service-update'),
    
    # Дополнительные эндпоинты для пользователя (должны быть ПЕРЕД router.urls)
    path('api/user/profile/', views.UserProfileAPIView.as_view(), name='user-profile'),
    path('api/user/profile/update/', views.UserProfileUpdateAPIView.as_view(), name='user-profile-update'),
    
    # Router для ViewSet и функции авторизации согласно методичке
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/login', views.login_view, name='login'),
    path('api/logout', views.logout_view, name='logout'),
    
    # Swagger документация
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-yaml'),
]
