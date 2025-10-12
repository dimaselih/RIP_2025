from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.db import transaction, connection
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import ServiceTCO, CalculationTCO, CalculationService, CustomUser

# DRF imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Permissions imports
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsModerator, IsAdmin, IsModeratorOrAdmin, IsOwnerOrModerator
from .serializers import (
    ServiceTCOSerializer, ServiceTCOListSerializer, 
    ServiceImageUploadSerializer,
    CalculationTCOSerializer, CalculationTCOListSerializer,
    CartIconSerializer, FormCalculationTCOSerializer,
    CompleteCalculationTCOSerializer, CalculationServiceSerializer,
    UserRegistrationSerializer, UserProfileSerializer, CustomUserSerializer,
    LoginSerializer
)
from .minio_utils import get_minio_client
import uuid


def get_constant_creator():
    """Получаем константного пользователя-создателя (singleton)"""
    try:
        creator = CustomUser.objects.get(email='creator@cto.com')
    except CustomUser.DoesNotExist:
        creator = CustomUser.objects.create_user(
            email='creator@cto.com',
            password='creator'
        )
    return creator


def get_constant_moderator():
    """Получаем константного пользователя-модератора (singleton)"""
    try:
        moderator = CustomUser.objects.get(email='moderator@cto.com')
    except CustomUser.DoesNotExist:
        moderator = CustomUser.objects.create_user(
            email='moderator@cto.com',
            password='moderator'
        )
        moderator.is_staff = True
        moderator.save()
    return moderator


# 1. GET - Список услуг с поиском
def catalog(request):
    """GET: Получение и поиск услуг через ORM"""
    search_query = request.GET.get('search_tcoservice', '').strip()
    
    # Получаем услуги из БД (только не удаленные)
    services = ServiceTCO.objects.filter(is_deleted=False)
    
    # Поиск по названию и описанию
    if search_query:
        services = services.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Получаем текущий расчет пользователя (черновик)
    current_calculation = None
    if request.user.is_authenticated:
        try:
            current_calculation = CalculationTCO.objects.get(
                creator=request.user, 
                status='draft'
            )
        except CalculationTCO.DoesNotExist:
            current_calculation = None
    
    return render(request, 'main/catalog.html', {
        "services": services,
        "current_calculation": current_calculation,
        "search_query": search_query,
    })

# 2. GET - Детали услуги
def service_detail(request, service_id):
    """GET: Детали услуги"""
    service = get_object_or_404(ServiceTCO, id=service_id, is_deleted=False)
    return render(request, 'main/service_detail.html', {"service": service})

# 3. GET - Детали расчета
def calculation(request, calculation_id):
    """GET: Просмотр расчета через ORM"""
    # Исключаем удаленные расчеты из поиска
    calculation = get_object_or_404(
        CalculationTCO, 
        id=calculation_id,
        status__in=['draft', 'formed', 'completed', 'rejected']  # Исключаем 'deleted'
    )
    
    # Получаем услуги в расчете
    calculation_services = calculation.calculation_services.all()
    
    return render(request, 'main/calculation.html', {
        "calculation": calculation,
        "calculation_services": calculation_services,
    })

# 4. POST - Добавление услуги в расчет
@login_required
def add_service_to_calculation(request):
    """POST: Добавление услуги в расчет через ORM"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    service_id = request.POST.get('service_id')
    quantity = int(request.POST.get('quantity', 1))
    
    try:
        service = ServiceTCO.objects.get(id=service_id, is_deleted=False)
    except ServiceTCO.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)
    
    with transaction.atomic():
        # Получаем или создаем черновик расчета
        calculation, created = CalculationTCO.objects.get_or_create(
            creator=request.user,
            status='draft',
            defaults={'status': 'draft'}
        )
        
        # Добавляем или обновляем услугу в расчете
        calculation_service, created = CalculationService.objects.get_or_create(
            calculation=calculation,
            service=service,
            defaults={'quantity': quantity}
        )
        
        if not created:
            calculation_service.quantity += quantity
            calculation_service.save()
    
    # Перенаправляем обратно на каталог с сообщением
    from django.contrib import messages
    messages.success(request, f'Услуга "{service.name}" добавлена в расчет')
    return redirect('catalog')

# 5. POST - Логическое удаление расчета через SQL
@login_required
def delete_calculation(request):
    """POST: Логическое удаление расчета через SQL UPDATE"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    calculation_id = request.POST.get('calculation_id')
    
    # Проверяем, что расчет принадлежит пользователю
    try:
        calculation = CalculationTCO.objects.get(
            id=calculation_id, 
            creator=request.user
        )
    except CalculationTCO.DoesNotExist:
        from django.contrib import messages
        messages.error(request, 'Расчет не найден')
        return redirect('catalog')
    
    # Логическое удаление через SQL UPDATE
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE main_calculation SET status = 'deleted' WHERE id = %s",
            [calculation_id]
        )
    
    # Перенаправляем на каталог с сообщением
    from django.contrib import messages
    messages.success(request, 'Расчёт удалён')
    return redirect('catalog')


# ==================== API VIEWS ====================

class ServiceListAPIView(APIView):
    """GET список услуг с фильтрацией"""
    permission_classes = [AllowAny]  # Публичный доступ
    
    @swagger_auto_schema(
        operation_description="Получение списка услуг с возможностью фильтрации и поиска",
        manual_parameters=[
            openapi.Parameter('search_tcoservice', openapi.IN_QUERY, description="Поиск по названию услуги", type=openapi.TYPE_STRING),
            openapi.Parameter('price_type', openapi.IN_QUERY, description="Фильтр по типу цены", type=openapi.TYPE_STRING, enum=['fixed', 'hourly']),
        ],
        responses={
            200: openapi.Response('Список услуг', examples={
                'application/json': [
                    {
                        'id': 1,
                        'name': 'Веб-разработка',
                        'description': 'Создание веб-сайтов',
                        'price': 50000.00,
                        'price_type': 'fixed',
                        'image_url': 'http://127.0.0.1:9000/technical/web.png'
                    }
                ]
            }),
        }
    )
    def get(self, request):
        # Получаем параметр поиска
        search = request.query_params.get('search', '')
        
        # Базовый queryset (только не удаленные)
        services = ServiceTCO.objects.filter(is_deleted=False)
        
        # Применяем фильтр поиска
        if search:
            services = services.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        # Сериализуем
        serializer = ServiceTCOListSerializer(services, many=True)
        return Response(serializer.data)


class ServiceDetailAPIView(APIView):
    """GET одна запись услуги"""
    permission_classes = [AllowAny]  # Публичный доступ для чтения
    
    def get(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        serializer = ServiceTCOSerializer(service)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class ServiceCreateAPIView(APIView):
    """POST добавление услуги (без изображения)"""
    permission_classes = [IsAuthenticated, IsModeratorOrAdmin]  # Только модераторы и админы
    
    @swagger_auto_schema(
        request_body=ServiceTCOSerializer,
        responses={
            201: openapi.Response('Услуга успешно создана', ServiceTCOSerializer),
            400: openapi.Response('Ошибка валидации'),
        }
    )
    def post(self, request):
        serializer = ServiceTCOSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceUpdateAPIView(APIView):
    """PUT изменение услуги"""
    permission_classes = [IsAuthenticated, IsModeratorOrAdmin]  # Только модераторы и админы
    
    @swagger_auto_schema(
        request_body=ServiceTCOSerializer,
        responses={
            200: openapi.Response('Услуга успешно обновлена', ServiceTCOSerializer),
            400: openapi.Response('Ошибка валидации'),
            404: openapi.Response('Услуга не найдена'),
        }
    )
    def put(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        serializer = ServiceTCOSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeleteAPIView(APIView):
    """DELETE удаление услуги (логическое удаление + удаление изображения)"""
    permission_classes = [IsAuthenticated, IsModeratorOrAdmin]  # Только модераторы и админы
    
    def delete(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        
        # Удаляем изображение из MinIO если есть
        if service.image_url:
            try:
                client = get_minio_client()
                # Извлекаем имя файла из URL
                image_name = service.image_url.split('/')[-1]
                client.remove_object('technical', image_name)
            except Exception as e:
                print(f"Ошибка удаления изображения: {e}")
        
        # Логическое удаление
        service.is_deleted = True
        service.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name='dispatch')
class ServiceAddToCartAPIView(APIView):
    """POST добавление услуги в заявку-черновик"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def post(self, request, pk):
        # Получаем услугу
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        
        # Валидируем данные
        serializer = AddToCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        quantity = serializer.validated_data['quantity']
        
        with transaction.atomic():
            # Автозаполнение пользователя из request.user
            calculation, created = CalculationTCO.objects.get_or_create(
                creator=request.user,
                status='draft',
                defaults={'status': 'draft'}
            )
            
            # Добавляем или обновляем услугу в заявке
            calculation_service, created = CalculationService.objects.get_or_create(
                calculation=calculation,
                service=service,
                defaults={'quantity': quantity}
            )
            
            if not created:
                calculation_service.quantity += quantity
                calculation_service.save()
        
        return Response({
            'message': f'Услуга "{service.name}" добавлена в корзину',
            'calculation_id': calculation.id,
            'quantity': calculation_service.quantity
        }, status=status.HTTP_201_CREATED)
    


class ServiceImageUploadAPIView(APIView):
    """POST добавление изображения услуги"""
    permission_classes = [IsAuthenticated, IsModeratorOrAdmin]  # Только модераторы и админы
    
    def post(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        
        # Валидируем данные
        serializer = ServiceImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = serializer.validated_data['image']
        
        try:
            # Удаляем старое изображение если есть
            if service.image_url:
                self._delete_old_image(service.image_url)
            
            # Генерируем имя файла на латинице
            image_name = f"{service.id}_{uuid.uuid4().hex[:8]}.{image_file.name.split('.')[-1]}"
            
            # Загружаем в MinIO
            client = get_minio_client()
            client.put_object(
                'cards',
                image_name,
                image_file,
                image_file.size,
                content_type=image_file.content_type
            )
            
            # Обновляем URL в базе
            service.image_url = f"http://localhost:9000/cards/{image_name}"
            service.save()
            
            return Response({
                'message': 'Изображение успешно загружено',
                'image_url': service.image_url
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Ошибка загрузки изображения: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _delete_old_image(self, old_url):
        """Удаляет старое изображение из MinIO"""
        try:
            client = get_minio_client()
            image_name = old_url.split('/')[-1]
            client.remove_object('cards', image_name)
        except Exception as e:
            print(f"Ошибка удаления старого изображения: {e}")


# ==================== ДОМЕН "ЗАЯВКА" ====================

@method_decorator(csrf_exempt, name='dispatch')
class CartIconAPIView(APIView):
    """GET иконки корзины (id заявки-черновика + количество услуг)"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def get(self, request):
        try:
            # Получаем черновик заявки текущего пользователя
            calculation = CalculationTCO.objects.get(creator=request.user, status='draft')
            services_count = calculation.calculation_services.count()
            
            serializer = CartIconSerializer({
                'calculation_id': calculation.id,
                'services_count': services_count
            })
            return Response(serializer.data)
            
        except CalculationTCO.DoesNotExist:
            # Если черновика нет, возвращаем пустую корзину
            serializer = CartIconSerializer({
                'calculation_id': None,
                'services_count': 0
            })
            return Response(serializer.data)
    


class CalculationListAPIView(APIView):
    """GET список заявок (кроме удаленных и черновика) с фильтрацией"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    @swagger_auto_schema(
        security=[{'SessionAuthentication': []}],
        responses={
            200: openapi.Response('Список заявок', examples={
                'application/json': [
                    {
                        'id': 1,
                        'status': 'active',
                        'creator': 'user@cto.com',
                        'moderator': 'moderator@cto.com'
                    }
                ]
            }),
            401: openapi.Response('Не авторизован'),
            403: openapi.Response('Доступ запрещен')
        }
    )
    def get(self, request):
        # Получаем параметры фильтрации
        status_filter = request.query_params.get('status', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        
        # Базовый queryset (исключаем удаленные и черновики)
        calculations = CalculationTCO.objects.exclude(
            status__in=['deleted', 'draft']
        )
        
        # Фильтрация по пользователю
        if request.user.is_staff or request.user.is_superuser:
            # Модератор или админ видит все заявки
            pass
        else:
            # Обычный пользователь видит только свои заявки
            calculations = calculations.filter(creator=request.user)
        
        # Применяем фильтры
        if status_filter:
            calculations = calculations.filter(status=status_filter)
        
        if date_from:
            calculations = calculations.filter(formed_at__date__gte=date_from)
        
        if date_to:
            calculations = calculations.filter(formed_at__date__lte=date_to)
        
        # Сериализуем
        serializer = CalculationTCOListSerializer(calculations, many=True)
        return Response(serializer.data)


class CalculationDetailAPIView(APIView):
    """GET одна заявка с услугами и картинками"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def get(self, request, pk):
        calculation = get_object_or_404(
            CalculationTCO, 
            pk=pk,
            status__in=['draft', 'formed', 'completed', 'rejected']
        )
        serializer = CalculationTCOSerializer(calculation)
        return Response(serializer.data)


class CalculationUpdateAPIView(APIView):
    """PUT изменения полей заявки"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    @swagger_auto_schema(
        request_body=FormCalculationTCOSerializer,
        responses={
            200: openapi.Response('Заявка успешно обновлена', CalculationTCOSerializer),
            400: openapi.Response('Ошибка валидации'),
            404: openapi.Response('Заявка не найдена'),
        }
    )
    def put(self, request, pk):
        calculation = get_object_or_404(CalculationTCO, pk=pk, status='draft')
        
        # Разрешаем изменять только определенные поля
        allowed_fields = ['start_date', 'end_date']
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = CalculationTCOSerializer(calculation, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CalculationFormAPIView(APIView):
    """PUT сформировать заявку (проверка обязательных полей)"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    @swagger_auto_schema(
        request_body=FormCalculationTCOSerializer,
        responses={
            200: openapi.Response('Заявка успешно сформирована', CalculationTCOSerializer),
            400: openapi.Response('Ошибка валидации'),
            404: openapi.Response('Заявка не найдена'),
        }
    )
    def put(self, request, pk):
        calculation = get_object_or_404(CalculationTCO, pk=pk, status='draft')
        
        # Валидируем данные
        serializer = FormCalculationTCOSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Проверяем обязательные поля
        if not calculation.calculation_services.exists():
            return Response({
                'error': 'Нельзя сформировать заявку без услуг'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Обновляем заявку
        calculation.start_date = serializer.validated_data['start_date']
        calculation.end_date = serializer.validated_data['end_date']
        calculation.status = 'formed'
        calculation.formed_at = timezone.now()
        calculation.save()
        
        response_serializer = CalculationSerializer(calculation)
        return Response(response_serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class CalculationTCOCompleteAPIView(APIView):
    """PUT завершить/отклонить заявку (вычисление стоимости)"""
    permission_classes = [IsModerator]  # Только модераторы
    
    @swagger_auto_schema(
        request_body=CompleteCalculationTCOSerializer,
        security=[{'SessionAuthentication': []}],
        responses={
            200: openapi.Response('Заявка успешно завершена', CalculationTCOSerializer),
            400: openapi.Response('Ошибка валидации'),
            403: openapi.Response('Доступ запрещен - требуется роль модератора'),
            404: openapi.Response('Заявка не найдена'),
        }
    )
    def put(self, request, pk):
        # Отладочная информация
        print(f"[COMPLETE] User: {request.user}")
        print(f"[COMPLETE] Is authenticated: {request.user.is_authenticated}")
        print(f"[COMPLETE] Is staff: {request.user.is_staff}")
        print(f"[COMPLETE] Is superuser: {request.user.is_superuser}")
        
        calculation = get_object_or_404(CalculationTCO, pk=pk, status='formed')
        
        # Валидируем данные
        serializer = CompleteCalculationTCOSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        moderator_comment = serializer.validated_data.get('moderator_comment', '')
        
        # Автозаполнение модератора из request.user (текущий авторизованный пользователь)
        if action == 'complete':
            # Вычисляем стоимость и срок эксплуатации
            total_cost, duration_months = self._calculate_cost_and_duration(calculation)
            
            calculation.status = 'completed'
            calculation.total_cost = total_cost
            calculation.duration_months = duration_months
        else:  # reject
            calculation.status = 'rejected'
        
        calculation.moderator = request.user
        calculation.completed_at = timezone.now()
        calculation.save()
        
        response_serializer = CalculationTCOSerializer(calculation)
        return Response(response_serializer.data)
    
    def _calculate_cost_and_duration(self, calculation):
        """Вычисляет стоимость и срок эксплуатации заявки"""
        total_cost = 0
        duration_months = 0
        
        for item in calculation.calculation_services.all():
            service = item.service
            quantity = item.quantity
            
            # Вычисляем стоимость в зависимости от типа цены
            if service.price_type == 'one_time':
                cost = service.price * quantity
            elif service.price_type == 'monthly':
                # Предполагаем срок эксплуатации 12 месяцев
                cost = service.price * quantity * 12
                duration_months = max(duration_months, 12)
            elif service.price_type == 'yearly':
                # Предполагаем срок эксплуатации 12 месяцев
                cost = service.price * quantity
                duration_months = max(duration_months, 12)
            else:
                cost = service.price * quantity
            
            total_cost += cost
        
        # Если не определили срок, устанавливаем 12 месяцев
        if duration_months == 0:
            duration_months = 12
        
        return total_cost, duration_months
    


class CalculationDeleteAPIView(APIView):
    """DELETE удаление заявки (логическое удаление)"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def delete(self, request, pk):
        calculation = get_object_or_404(CalculationTCO, pk=pk, status='draft')
        
        # Логическое удаление
        calculation.status = 'deleted'
        calculation.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== ДОМЕН "М-М" (КОРЗИНА) ====================

class CalculationServiceDeleteAPIView(APIView):
    """DELETE удаление услуги из заявки-черновика"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def delete(self, request):
        # Получаем параметры из query string
        calculation_id = request.query_params.get('calculation_id')
        service_id = request.query_params.get('service_id')
        
        if not calculation_id or not service_id:
            return Response({
                'error': 'Требуются параметры calculation_id и service_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Получаем заявку-черновик константного создателя
            calculation = CalculationTCO.objects.get(
                id=calculation_id,
                creator=request.user,
                status='draft'
            )
            
            # Получаем услугу
            service = get_object_or_404(ServiceTCO, id=service_id, is_deleted=False)
            
            # Удаляем связь
            calculation_service = get_object_or_404(
                CalculationService,
                calculation=calculation,
                service=service
            )
            
            calculation_service.delete()
            
            return Response({
                'message': f'Услуга "{service.name}" удалена из корзины'
            }, status=status.HTTP_200_OK)
            
        except CalculationTCO.DoesNotExist:
            return Response({
                'error': 'Заявка-черновик не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Ошибка удаления: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CalculationServiceUpdateAPIView(APIView):
    """PUT изменение количества/порядка/значения в заявке-черновике"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def put(self, request):
        # Получаем параметры из query string
        calculation_id = request.query_params.get('calculation_id')
        service_id = request.query_params.get('service_id')
        
        if not calculation_id or not service_id:
            return Response({
                'error': 'Требуются параметры calculation_id и service_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Получаем заявку-черновик константного создателя
            calculation = CalculationTCO.objects.get(
                id=calculation_id,
                creator=request.user,
                status='draft'
            )
            
            # Получаем услугу
            service = get_object_or_404(ServiceTCO, id=service_id, is_deleted=False)
            
            # Получаем связь
            calculation_service = get_object_or_404(
                CalculationService,
                calculation=calculation,
                service=service
            )
            
            # Валидируем данные (только quantity и order)
            quantity = request.data.get('quantity')
            order = request.data.get('order')
            
            if quantity is not None:
                try:
                    quantity = int(quantity)
                    if quantity < 1:
                        raise ValueError()
                    calculation_service.quantity = quantity
                except (ValueError, TypeError):
                    return Response({
                        'quantity': ['Количество должно быть положительным целым числом']
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            if order is not None:
                try:
                    order = int(order)
                    if order < 0:
                        raise ValueError()
                    calculation_service.order = order
                except (ValueError, TypeError):
                    return Response({
                        'order': ['Порядок должен быть неотрицательным целым числом']
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Пересчитываем value
            calculation_service.value = calculation_service.quantity * service.price
            calculation_service.save()
            
            # Возвращаем обновленную связь
            response_serializer = CalculationServiceSerializer(calculation_service)
            return Response(response_serializer.data)
            
        except CalculationTCO.DoesNotExist:
            return Response({
                'error': 'Заявка-черновик не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Ошибка обновления: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ДОМЕН "ПОЛЬЗОВАТЕЛЬ" ====================

@method_decorator(csrf_exempt, name='dispatch')
class UserViewSet(viewsets.ModelViewSet):
    """Класс, описывающий методы работы с пользователями
    Осуществляет связь с таблицей пользователей в базе данных
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    model_class = CustomUser
    
    def get_permissions(self):
        """
        Разные permissions для разных действий:
        - create (POST) - доступно всем (публичная регистрация)
        - list, retrieve, update, partial_update, destroy - только для администраторов
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated(), IsAdmin()]

    @swagger_auto_schema(
        request_body=CustomUserSerializer,
        security=[],
        responses={
            201: openapi.Response(
                'Успешная регистрация', 
                examples={
                    'application/json': {
                        'status': 'ok',
                        'user_id': 1
                    }
                }
            ),
            400: openapi.Response(
                'Ошибка регистрации', 
                examples={
                    'application/json': {
                        'status': 'error',
                        'error': 'validation failed'
                    }
                }
            )
        }
    )

    def create(self, request):
        """
        Функция регистрации новых пользователей
        Если пользователя c указанным в request email ещё нет, в БД будет добавлен новый пользователь.
        """
        # Отладочная информация
        print(f"Request data: {request.data}")
        
        serializer = self.serializer_class(data=request.data)
        print(f"Serializer is valid: {serializer.is_valid()}")
        if not serializer.is_valid():
            print(f"Serializer errors: {serializer.errors}")
            return Response({'status': 'Error', 'error': serializer.errors}, status=400)
        
        # Проверяем, существует ли пользователь
        email = serializer.validated_data['email']
        if self.model_class.objects.filter(email=email).exists():
            return Response({'status': 'Exist'}, status=400)
        
        # Создаем пользователя
        self.model_class.objects.create_user(
            email=email,
            password=serializer.validated_data['password'],
            is_superuser=serializer.validated_data.get('is_superuser', False),
            is_staff=serializer.validated_data.get('is_staff', False)
        )
        return Response({'status': 'Success'}, status=200)


class UserRegistrationAPIView(APIView):
    """POST регистрация нового пользователя"""
    permission_classes = [AllowAny]  # Публичный доступ
    
    @swagger_auto_schema(
        operation_description="Регистрация нового пользователя в системе",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'first_name', 'last_name', 'email', 'password', 'password_confirm'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
                'first_name': openapi.Schema(type=openapi.TYPE_STRING, description='Имя'),
                'last_name': openapi.Schema(type=openapi.TYPE_STRING, description='Фамилия'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description='Email'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль'),
                'password_confirm': openapi.Schema(type=openapi.TYPE_STRING, description='Подтверждение пароля'),
            }
        ),
        responses={
            201: openapi.Response('Пользователь успешно зарегистрирован', examples={
                'application/json': {
                    'message': 'Пользователь успешно зарегистрирован',
                    'user_id': 1,
                    'username': 'newuser'
                }
            }),
            400: openapi.Response('Ошибка валидации'),
        }
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Создаем пользователя
            user = User.objects.create_user(
                username=serializer.validated_data['username'],
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            
            return Response({
                'message': 'Пользователь успешно зарегистрирован',
                'user_id': user.id,
                'username': user.username
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPIView(APIView):
    """GET профиль пользователя после аутентификации"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({
                'error': 'Пользователь не аутентифицирован'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class UserProfileUpdateAPIView(APIView):
    """PUT изменение профиля пользователя"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    @swagger_auto_schema(
        request_body=CustomUserSerializer,
        responses={
            200: openapi.Response('Профиль успешно обновлен', CustomUserSerializer),
            400: openapi.Response('Ошибка валидации'),
            401: openapi.Response('Пользователь не аутентифицирован'),
        }
    )
    def put(self, request):
        if not request.user.is_authenticated:
            return Response({
                'error': 'Пользователь не аутентифицирован'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = CustomUserSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # Обновляем поля пользователя
            user = request.user
            if 'email' in serializer.validated_data:
                user.email = serializer.validated_data['email']
            if 'is_staff' in serializer.validated_data:
                user.is_staff = serializer.validated_data['is_staff']
            if 'is_superuser' in serializer.validated_data:
                user.is_superuser = serializer.validated_data['is_superuser']
            if 'password' in serializer.validated_data:
                user.set_password(serializer.validated_data['password'])
            
            user.save()
            return Response({
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginAPIView(APIView):
    """POST аутентификация пользователя"""
    permission_classes = [AllowAny]  # Публичный доступ
    
    @swagger_auto_schema(
        operation_description="Аутентификация пользователя в системе",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль'),
            }
        ),
        responses={
            200: openapi.Response('Успешная аутентификация', examples={
                'application/json': {
                    'message': 'Успешная аутентификация',
                    'user_id': 1,
                    'username': 'testuser',
                    'is_moderator': False
                }
            }),
            400: openapi.Response('Ошибка валидации'),
            401: openapi.Response('Неверные учетные данные'),
        }
    )
    def post(self, request):
        from django.contrib.auth import authenticate, login
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'error': 'Требуются username и password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return Response({
                    'message': 'Успешная аутентификация',
                    'user_id': user.id,
                    'username': user.username,
                    'is_moderator': user.is_moderator
                })
            else:
                return Response({
                    'error': 'Аккаунт деактивирован'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'error': 'Неверные учетные данные'
            }, status=status.HTTP_401_UNAUTHORIZED)


class UserLogoutAPIView(APIView):
    """POST деавторизация пользователя"""
    permission_classes = [IsAuthenticated]  # Требует аутентификации
    
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({
                'error': 'Пользователь не аутентифицирован'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from django.contrib.auth import logout
        logout(request)
        
        return Response({
            'message': 'Успешный выход из системы'
        })


# Функции авторизации согласно методичке
@swagger_auto_schema(
    method='post',
    request_body=LoginSerializer,
    security=[],
    responses={
        200: openapi.Response(
            'Успешная авторизация', 
            examples={
                'application/json': {
                    'status': 'ok'
                }
            }
        ),
        400: openapi.Response(
            'Ошибка авторизации', 
            examples={
                'application/json': {
                    'status': 'error',
                    'error': 'login failed'
                }
            }
        )
    },
    operation_description="Авторизация пользователя в системе",
    operation_summary="Вход в систему"
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@csrf_exempt
def login_view(request):
    """Функция авторизации пользователей согласно методичке"""
    # Отладочная информация
    print(f"Request data: {request.data}")
    print(f"Request POST: {request.POST}")
    print(f"Content-Type: {request.content_type}")
    
    email = request.POST.get("email") or request.data.get("email")
    password = request.POST.get("password") or request.data.get("password")
    
    print(f"Email: {email}")
    print(f"Password: {password}")
    
    if not email or not password:
        print("Missing email or password")
        return Response({'status': 'error', 'error': 'email and password required'}, status=400)
        
    user = authenticate(request, email=email, password=password)
    print(f"User: {user}")
    
    if user is not None:
        login(request, user)
        response = Response({'status': 'ok', 'message': 'Успешная авторизация'})
        # Явно устанавливаем куку sessionid для Swagger UI
        response.set_cookie(
            'sessionid',
            request.session.session_key,
            max_age=1209600,  # 2 недели
            httponly=True,
            samesite='Lax'
        )
        return response
    else:
        return Response({'status': 'error', 'error': 'login failed'}, status=400)


@api_view(['POST'])
@swagger_auto_schema(
    security=[{'SessionAuthentication': []}],
    responses={
        200: openapi.Response('Успешный выход', examples={
            'application/json': {
                'status': 'Success'
            }
        })
    }
)
@csrf_exempt
def logout_view(request):
    """Функция выхода из системы согласно методичке"""
    logout(request._request)
    return Response({'status': 'Success'})

