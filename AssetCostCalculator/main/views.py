from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction, connection
from django.db.models import Q
from .models import ServiceTCO, Calculation, CalculationService


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
    
    search_query = request.GET.get('search', '').strip()
    
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

# 2. GET - Детали расчета
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

# Дополнительная функция для деталей услуги
def service_detail(request, service_id):
    """GET: Детали услуги"""
    service = get_object_or_404(ServiceTCO, id=service_id, is_deleted=False)
    return render(request, 'main/service_detail.html', {"service": service})
