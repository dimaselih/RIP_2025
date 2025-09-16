from django.urls import path
from . import views

urlpatterns = [
    path('services/', views.services, name='services'),
    path('services/<int:service_id>/', views.service_detail, name='service_detail'),
    path('cart/', views.cart, name='cart'),
    path('minio/<str:bucket_name>/<path:object_name>', views.minio_proxy, name='minio_proxy')
]
