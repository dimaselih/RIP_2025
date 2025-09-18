from django.urls import path
from . import views

urlpatterns = [
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:service_id>/', views.service_detail, name='service_detail'),
    path('calculation/<int:cart_id>/', views.calculation, name='calculation'),
]
