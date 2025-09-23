from django.urls import path
from . import views

urlpatterns = [
    # GET контроллеры
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:service_id>/', views.service_detail, name='service_detail'),
    path('calculation/<int:calculation_id>/', views.calculation, name='calculation'),
    
    # POST контроллеры
    path('add-service/', views.add_service_to_calculation, name='add_service_to_calculation'),
    path('delete-calculation/', views.delete_calculation, name='delete_calculation'),
]
