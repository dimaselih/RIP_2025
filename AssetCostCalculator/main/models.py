from django.db import models
from django.contrib.auth.models import User

# Create your models here.

# Расширение системной таблицы User
# Добавляем поле is_moderator через миграцию
User.add_to_class('is_moderator', models.BooleanField(
    default=False,
    verbose_name='Модератор',
    help_text='Является ли пользователь модератором'
))

class ServiceTCO(models.Model):
    """Таблица услуг TCO"""
    
    PRICE_TYPE_CHOICES = [
        ('one_time', 'Единовременная'),
        ('monthly', 'Ежемесячная'),
        ('yearly', 'Ежегодная'),
    ]
    
    name = models.CharField(
        max_length=200, 
        verbose_name="Наименование",
        help_text="Название услуги"
    )
    description = models.TextField(
        verbose_name="Описание",
        help_text="Описание услуги"
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name="Статус удален",
        help_text="Помечена ли услуга как удаленная"
    )
    image_url = models.URLField(
        null=True, 
        blank=True,
        verbose_name="URL изображения",
        help_text="Ссылка на изображение услуги"
    )
    # Поля по предметной области
    fullDescription = models.TextField(
        verbose_name="Полное описание",
        help_text="Подробное описание услуги с включенными сервисами"
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Стоимость",
        help_text="Стоимость услуги в рублях"
    )
    price_type = models.CharField(
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default='one_time',
        verbose_name="Тип стоимости",
        help_text="Единовременная, ежемесячная или ежегодная оплата"
    )
    
    class Meta:
        verbose_name = "Услуга TCO"
        verbose_name_plural = "Услуги TCO"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CalculationTCO(models.Model):
    """Таблица расчетов TCO"""
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('deleted', 'Удалена'),
        ('formed', 'Сформирована'),
        ('completed', 'Завершена'),
        ('rejected', 'Отклонена'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Статус"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_requests',
        verbose_name="Создатель"
    )
    
    # Дополнительные поля
    formed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата формирования"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата завершения"
    )
    moderator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='moderated_requests',
        verbose_name="Модератор"
    )
    
    # Поля по предметной области
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Общая стоимость",
        help_text="Рассчитывается при завершении заявки"
    )
    duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Срок эксплуатации (месяцев)",
        help_text="Рассчитывается при завершении заявки"
    )
    
    # Поля для дат
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата начала эксплуатации",
        help_text="Дата начала эксплуатации актива"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата окончания эксплуатации",
        help_text="Дата окончания эксплуатации актива"
    )
    
    class Meta:
        verbose_name = "Расчет TCO"
        verbose_name_plural = "Расчеты TCO"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['creator', 'status'],
                condition=models.Q(status='draft'),
                name='unique_draft_per_user'
            )
        ]
    
    
    def __str__(self):
        return f"Расчет #{self.id} - {self.get_status_display()}"


class CalculationService(models.Model):
    """Таблица м-м расчеты-услуги (составной уникальный ключ)"""
    
    calculation = models.ForeignKey(
        CalculationTCO,
        on_delete=models.PROTECT,
        related_name='calculation_services',
        verbose_name="Расчет"
    )
    service = models.ForeignKey(
        ServiceTCO,
        on_delete=models.PROTECT,
        related_name='calculation_services',
        verbose_name="Услуга"
    )
    
    # Дополнительные поля
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Количество",
        help_text="Количество единиц услуги"
    )
    
    class Meta:
        verbose_name = "Услуга в расчете"
        verbose_name_plural = "Услуги в расчетах"
        ordering = ['service__name']
        # Составной уникальный ключ
        constraints = [
            models.UniqueConstraint(
                fields=['calculation', 'service'],
                name='unique_calculation_service'
            )
        ]
    
    def __str__(self):
        return f"{self.calculation} - {self.service} (x{self.quantity})"
