from django.urls import path
from . import views

urlpatterns = [
    # Старые Django views (HTML)
    path('catalog_tco/', views.catalog, name='catalog_tco'),
    path('catalog_tco/<int:service_id>/', views.service_detail, name='service_detail'),
    path('calculation_tco/<int:calculation_id>/', views.calculation, name='calculation_tco'),
    path('add-service/', views.add_service_to_calculation, name='add_service_to_calculation'),
    path('delete-calculation/', views.delete_calculation, name='delete_calculation'),
    
    # ==================== API URLS ====================
    # Домен "Услуга" (7 эндпоинтов)
    path('api/service_tco/', views.ServiceListAPIView.as_view(), name='api-service_tco-list'),
    path('api/service_tco/<int:pk>/', views.ServiceDetailAPIView.as_view(), name='api-service_tco-detail'),
    path('api/service_tco/create/', views.ServiceCreateAPIView.as_view(), name='api-service_tco-create'),
    path('api/service_tco/<int:pk>/update/', views.ServiceUpdateAPIView.as_view(), name='api-service_tco-update'),
    path('api/service_tco/<int:pk>/delete/', views.ServiceDeleteAPIView.as_view(), name='api-service_tco-delete'),
    path('api/service_tco/<int:pk>/add-to-cart/', views.ServiceAddToCartAPIView.as_view(), name='api-service_tco-add-to-cart'),
    path('api/service_tco/<int:pk>/image/', views.ServiceImageUploadAPIView.as_view(), name='api-service_tco-image'),
    
    # Домен "Заявка" (7 эндпоинтов)
    path('api/cart_tco/', views.CartIconAPIView.as_view(), name='api-cart_tco-icon'),
    path('api/calculation_tco/', views.CalculationTCOListAPIView.as_view(), name='api-calculation_tco-list'),
    path('api/calculation_tco/<int:pk>/', views.CalculationTCODetailAPIView.as_view(), name='api-calculation_tco-detail'),
    path('api/calculation_tco/<int:pk>/update/', views.CalculationTCOUpdateAPIView.as_view(), name='api-calculation_tco-update'),
    path('api/calculation_tco/<int:pk>/form/', views.CalculationTCOFormAPIView.as_view(), name='api-calculation_tco-form'),
    path('api/calculation_tco/<int:pk>/complete/', views.CalculationTCOCompleteAPIView.as_view(), name='api-calculation_tco-complete'),
    path('api/calculation_tco/<int:pk>/delete/', views.CalculationTCODeleteAPIView.as_view(), name='api-calculation_tco-delete'),
    
    # Домен "М-М" (корзина) - 2 эндпоинта
    path('api/calculation_tco-service/', views.CalculationServiceDeleteAPIView.as_view(), name='api-calculation_tco-service-delete'),
    path('api/calculation_tco-service/update/', views.CalculationServiceUpdateAPIView.as_view(), name='api-calculation_tco-service-update'),
    
    # Домен "Пользователь" - 5 эндпоинтов
    path('api/user/register/', views.UserRegistrationAPIView.as_view(), name='api-user-register'),
    path('api/user/profile/', views.UserProfileAPIView.as_view(), name='api-user-profile'),
    path('api/user/profile/update/', views.UserProfileUpdateAPIView.as_view(), name='api-user-profile-update'),
    path('api/user/login/', views.UserLoginAPIView.as_view(), name='api-user-login'),
    path('api/user/logout/', views.UserLogoutAPIView.as_view(), name='api-user-logout'),
]
