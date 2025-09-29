from django.urls import path
from . import views

urlpatterns = [
    # Старые Django views (HTML)
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:service_id>/', views.service_detail, name='service_detail'),
    path('calculation/<int:calculation_id>/', views.calculation, name='calculation'),
    path('add-service/', views.add_service_to_calculation, name='add_service_to_calculation'),
    path('delete-calculation/', views.delete_calculation, name='delete_calculation'),
    
    # ==================== API URLS ====================
    # Домен "Услуга" (7 эндпоинтов)
    path('api/servicetco/', views.ServiceListAPIView.as_view(), name='api-servicetco-list'),
    path('api/servicetco/<int:pk>/', views.ServiceDetailAPIView.as_view(), name='api-servicetco-detail'),
    path('api/servicetco/create/', views.ServiceCreateAPIView.as_view(), name='api-servicetco-create'),
    path('api/servicetco/<int:pk>/update/', views.ServiceUpdateAPIView.as_view(), name='api-servicetco-update'),
    path('api/servicetco/<int:pk>/delete/', views.ServiceDeleteAPIView.as_view(), name='api-servicetco-delete'),
    path('api/servicetco/<int:pk>/add-to-cart/', views.ServiceAddToCartAPIView.as_view(), name='api-servicetco-add-to-cart'),
    path('api/servicetco/<int:pk>/image/', views.ServiceImageUploadAPIView.as_view(), name='api-servicetco-image'),
    
    # Домен "Заявка" (7 эндпоинтов)
    path('api/cart/', views.CartIconAPIView.as_view(), name='api-cart-icon'),
    path('api/calculation/', views.CalculationListAPIView.as_view(), name='api-calculation-list'),
    path('api/calculation/<int:pk>/', views.CalculationDetailAPIView.as_view(), name='api-calculation-detail'),
    path('api/calculation/<int:pk>/update/', views.CalculationUpdateAPIView.as_view(), name='api-calculation-update'),
    path('api/calculation/<int:pk>/form/', views.CalculationFormAPIView.as_view(), name='api-calculation-form'),
    path('api/calculation/<int:pk>/complete/', views.CalculationCompleteAPIView.as_view(), name='api-calculation-complete'),
    path('api/calculation/<int:pk>/delete/', views.CalculationDeleteAPIView.as_view(), name='api-calculation-delete'),
    
    # Домен "М-М" (корзина) - 2 эндпоинта
    path('api/calculation-service/', views.CalculationServiceDeleteAPIView.as_view(), name='api-calculation-service-delete'),
    path('api/calculation-service/update/', views.CalculationServiceUpdateAPIView.as_view(), name='api-calculation-service-update'),
    
    # Домен "Пользователь" - 5 эндпоинтов
    path('api/user/register/', views.UserRegistrationAPIView.as_view(), name='api-user-register'),
    path('api/user/profile/', views.UserProfileAPIView.as_view(), name='api-user-profile'),
    path('api/user/profile/update/', views.UserProfileUpdateAPIView.as_view(), name='api-user-profile-update'),
    path('api/user/login/', views.UserLoginAPIView.as_view(), name='api-user-login'),
    path('api/user/logout/', views.UserLogoutAPIView.as_view(), name='api-user-logout'),
]
