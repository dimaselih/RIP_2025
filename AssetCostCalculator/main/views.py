from django.shortcuts import render
from django.http import HttpResponse
from .minio_utils import get_minio_client

services_data = [
    {
        "id": 1,
        "title": "Закупка оборудования",
        "image": "minio/cards/purchase.png",
        "shortDescription": "Первоначальная стоимость приобретения актива, включая доставку, установку и настройку",
        "fullDescription": (
            "• Поставка оборудования в полной комплектации\n"
            "• Доставка до места эксплуатации\n"
            "• Распаковка и проверка комплектности\n"
            "• Установка и первичная настройка\n"
            "• Тестирование работоспособности"
        ),
        "price": "500,000 ₽",
    },
    {
        "id": 2,
        "title": "Эксплуатационные расходы",
        "image": "minio/cards/operation.png",
        "shortDescription": "Ежегодные затраты на эксплуатацию актива: энергопотребление, расходные материалы, аренда помещений",
        "fullDescription": (
            "• Энергопотребление и коммунальные услуги\n"
            "• Расходные материалы и комплектующие\n"
            "• Аренда помещений и инфраструктуры\n"
            "• Техническое обслуживание систем\n"
            "• Мониторинг и контроль работы"
        ),
        "price": "12,500 ₽/мес",
    },
    {
        "id": 3,
        "title": "Техническое обслуживание",
        "image": "minio/cards/service.png",
        "shortDescription": "Плановое и внеплановое техническое обслуживание, ремонты, замена комплектующих",
        "fullDescription": (
            "• Плановое техническое обслуживание\n"
            "• Внеплановые ремонты и диагностика\n"
            "• Замена изношенных комплектующих\n"
            "• Профилактические работы\n"
            "• Консультации и техническая поддержка"
        ),
        "price": "6,700 ₽/мес",
    },
    {
        "id": 4,
        "title": "Модернизация и обновления",
        "image": "minio/cards/modernization.png",
        "shortDescription": "Затраты на обновление программного обеспечения, модернизацию оборудования",
        "fullDescription": (
            "• Обновление программного обеспечения\n"
            "• Апгрейд аппаратного обеспечения\n"
            "• Внедрение новых технологий\n"
            "• Улучшение функциональности\n"
            "• Обучение персонала новым возможностям"
        ),
        "price": "200,000 ₽",
    },
    {
        "id": 5,
        "title": "Утилизация и списание",
        "image": "minio/cards/disposal.png",
        "shortDescription": "Затраты на демонтаж, утилизацию, экологическую безопасность при списании актива",
        "fullDescription": (
            "• Демонтаж и разборка оборудования\n"
            "• Утилизация в соответствии с экологическими нормами\n"
            "• Уничтожение конфиденциальных данных\n"
            "• Оформление документов по списанию\n"
            "• Утилизация отходов и материалов"
        ),
        "price": "30,000 ₽",
    },
    {
        "id": 6,
        "title": "Страхование актива",
        "image": "minio/cards/insurance.png",
        "shortDescription": "Страховые взносы за весь период эксплуатации актива",
        "fullDescription": (
            "• Страхование от повреждений\n"
            "• Страхование от кражи и потери\n"
            "• Защита от форс-мажорных обстоятельств\n"
            "• Страхование ответственности\n"
            "• Техническая поддержка при страховых случаях"
        ),
        "price": "2,100 ₽/мес",
    },
]

cart_data = {
    1: {
        "name": "System 1",
        "components": [
            {"componentId": 1, "replicationCount": 4},
            {"componentId": 3, "replicationCount": 2},
            {"componentId": 6, "replicationCount": 3},
        ],
    }
}


def services(request):
    # Обработка поиска
    search_query = request.GET.get('search', '').strip()
    filtered_services = services_data
    
    if search_query:
        filtered_services = [
            service for service in services_data
            if search_query.lower() in service['title'].lower() or 
               search_query.lower() in service['shortDescription'].lower()
        ]
    
    return render(request, 'main/services.html', {
        "services": filtered_services,
        "cart_data": cart_data,
        "search_query": search_query,
    })

def cart(request):
    return render(request, 'main/cart.html', {
        "cart_data": cart_data,
        "services_data": services_data,
    })

def service_detail(request, service_id):
    service = next((s for s in services_data if s["id"] == service_id), None)
    return render(request, 'main/service_detail.html', {"service": service})

def minio_proxy(request, bucket_name, object_name):
    """
    Прокси для доступа к файлам MinIO
    """
    try:
        client = get_minio_client()
        response = client.get_object(bucket_name, object_name)
        data = response.read()
        response.close()
        response.release_conn()

        content_type = 'application/octet-stream'
        lower = object_name.lower()
        if lower.endswith('.png'):
            content_type = 'image/png'
        elif lower.endswith('.jpg') or lower.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif lower.endswith('.gif'):
            content_type = 'image/gif'

        return HttpResponse(data, content_type=content_type)
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=404)