from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction, connection
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import ServiceTCO, Calculation, CalculationService

# DRF imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from .serializers import (
    ServiceTCOSerializer, ServiceTCOListSerializer, 
    AddToCartSerializer, ServiceImageUploadSerializer,
    CalculationSerializer, CalculationListSerializer,
    CartIconSerializer, FormCalculationSerializer,
    CompleteCalculationSerializer, CalculationServiceSerializer,
    UserRegistrationSerializer, UserProfileSerializer
)
from .minio_utils import get_minio_client
import uuid


def get_constant_creator():
    """Получаем константного пользователя-создателя (singleton)"""
    try:
        creator = User.objects.get(username='creator')
    except User.DoesNotExist:
        creator = User.objects.create_user(
            username='creator',
            first_name='Создатель',
            last_name='Заявок',
            email='creator@example.com'
        )
    return creator


def get_constant_moderator():
    """Получаем константного пользователя-модератора (singleton)"""
    try:
        moderator = User.objects.get(username='moderator')
    except User.DoesNotExist:
        moderator = User.objects.create_user(
            username='moderator',
            first_name='Модератор',
            last_name='Системы',
            email='moderator@example.com'
        )
        moderator.is_moderator = True
        moderator.save()
    return moderator


# 1. GET - Список услуг с поиском
def catalog(request):
    """GET: Получение и поиск услуг через ORM"""
    # Автоматический вход пользователя для демонстрации
    if not request.user.is_authenticated:
        try:
            user = User.objects.get(username='user1')
            login(request, user)
        except User.DoesNotExist:
            pass  # Если пользователь не найден, продолжаем без входа
    
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
            current_calculation = Calculation.objects.get(
                creator=request.user, 
                status='draft'
            )
        except Calculation.DoesNotExist:
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
        Calculation, 
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
        calculation, created = Calculation.objects.get_or_create(
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
        calculation = Calculation.objects.get(
            id=calculation_id, 
            creator=request.user
        )
    except Calculation.DoesNotExist:
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
    
    def get(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        serializer = ServiceTCOSerializer(service)
        return Response(serializer.data)


class ServiceCreateAPIView(APIView):
    """POST добавление услуги (без изображения)"""
    
    def post(self, request):
        serializer = ServiceTCOSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceUpdateAPIView(APIView):
    """PUT изменение услуги"""
    
    def put(self, request, pk):
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        serializer = ServiceTCOSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeleteAPIView(APIView):
    """DELETE удаление услуги (логическое удаление + удаление изображения)"""
    
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


class ServiceAddToCartAPIView(APIView):
    """POST добавление услуги в заявку-черновик"""
    
    def post(self, request, pk):
        # Получаем услугу
        service = get_object_or_404(ServiceTCO, pk=pk, is_deleted=False)
        
        # Валидируем данные
        serializer = AddToCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        quantity = serializer.validated_data['quantity']
        
        with transaction.atomic():
            # Получаем константного создателя
            creator = get_constant_creator()
            
            calculation, created = Calculation.objects.get_or_create(
                creator=creator,
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

class CartIconAPIView(APIView):
    """GET иконки корзины (id заявки-черновика + количество услуг)"""
    
    def get(self, request):
        try:
            # Получаем черновик заявки константного создателя
            creator = get_constant_creator()
            calculation = Calculation.objects.get(creator=creator, status='draft')
            services_count = calculation.calculation_services.count()
            
            serializer = CartIconSerializer({
                'calculation_id': calculation.id,
                'services_count': services_count
            })
            return Response(serializer.data)
            
        except Calculation.DoesNotExist:
            # Если черновика нет, возвращаем пустую корзину
            serializer = CartIconSerializer({
                'calculation_id': None,
                'services_count': 0
            })
            return Response(serializer.data)
    


class CalculationListAPIView(APIView):
    """GET список заявок (кроме удаленных и черновика) с фильтрацией"""
    
    def get(self, request):
        # Получаем параметры фильтрации
        status_filter = request.query_params.get('status', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        
        # Базовый queryset (исключаем удаленные и черновики)
        calculations = Calculation.objects.exclude(
            status__in=['deleted', 'draft']
        )
        
        # Применяем фильтры
        if status_filter:
            calculations = calculations.filter(status=status_filter)
        
        if date_from:
            calculations = calculations.filter(formed_at__date__gte=date_from)
        
        if date_to:
            calculations = calculations.filter(formed_at__date__lte=date_to)
        
        # Сериализуем
        serializer = CalculationListSerializer(calculations, many=True)
        return Response(serializer.data)


class CalculationDetailAPIView(APIView):
    """GET одна заявка с услугами и картинками"""
    
    def get(self, request, pk):
        calculation = get_object_or_404(
            Calculation, 
            pk=pk,
            status__in=['draft', 'formed', 'completed', 'rejected']
        )
        serializer = CalculationSerializer(calculation)
        return Response(serializer.data)


class CalculationUpdateAPIView(APIView):
    """PUT изменения полей заявки"""
    
    def put(self, request, pk):
        calculation = get_object_or_404(Calculation, pk=pk, status='draft')
        
        # Разрешаем изменять только определенные поля
        allowed_fields = ['start_date', 'end_date']
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = CalculationSerializer(calculation, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CalculationFormAPIView(APIView):
    """PUT сформировать заявку (проверка обязательных полей)"""
    
    def put(self, request, pk):
        calculation = get_object_or_404(Calculation, pk=pk, status='draft')
        
        # Валидируем данные
        serializer = FormCalculationSerializer(data=request.data)
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


class CalculationCompleteAPIView(APIView):
    """PUT завершить/отклонить заявку (вычисление стоимости)"""
    
    def put(self, request, pk):
        calculation = get_object_or_404(Calculation, pk=pk, status='formed')
        
        # Валидируем данные
        serializer = CompleteCalculationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        moderator_comment = serializer.validated_data.get('moderator_comment', '')
        
        # Получаем константного модератора
        moderator = get_constant_moderator()
        
        if action == 'complete':
            # Вычисляем стоимость и срок эксплуатации
            total_cost, duration_months = self._calculate_cost_and_duration(calculation)
            
            calculation.status = 'completed'
            calculation.total_cost = total_cost
            calculation.duration_months = duration_months
        else:  # reject
            calculation.status = 'rejected'
        
        calculation.moderator = moderator
        calculation.completed_at = timezone.now()
        calculation.save()
        
        response_serializer = CalculationSerializer(calculation)
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
    
    def delete(self, request, pk):
        calculation = get_object_or_404(Calculation, pk=pk, status='draft')
        
        # Логическое удаление
        calculation.status = 'deleted'
        calculation.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== ДОМЕН "М-М" (КОРЗИНА) ====================

class CalculationServiceDeleteAPIView(APIView):
    """DELETE удаление услуги из заявки-черновика"""
    
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
            calculation = Calculation.objects.get(
                id=calculation_id,
                creator=get_constant_creator(),
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
            
        except Calculation.DoesNotExist:
            return Response({
                'error': 'Заявка-черновик не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Ошибка удаления: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CalculationServiceUpdateAPIView(APIView):
    """PUT изменение количества/порядка/значения в заявке-черновике"""
    
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
            calculation = Calculation.objects.get(
                id=calculation_id,
                creator=get_constant_creator(),
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
            
        except Calculation.DoesNotExist:
            return Response({
                'error': 'Заявка-черновик не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Ошибка обновления: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ДОМЕН "ПОЛЬЗОВАТЕЛЬ" ====================

class UserRegistrationAPIView(APIView):
    """POST регистрация нового пользователя"""
    
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
    
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({
                'error': 'Пользователь не аутентифицирован'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class UserProfileUpdateAPIView(APIView):
    """PUT изменение профиля пользователя"""
    
    def put(self, request):
        if not request.user.is_authenticated:
            return Response({
                'error': 'Пользователь не аутентифицирован'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginAPIView(APIView):
    """POST аутентификация пользователя"""
    
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

