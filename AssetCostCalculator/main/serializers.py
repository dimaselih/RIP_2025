from rest_framework import serializers
from .models import ServiceTCO, CalculationTCO, CalculationService, User, CustomUser
from collections import OrderedDict


class ServiceTCOSerializer(serializers.ModelSerializer):
    """Сериализатор для услуг TCO"""
    
    class Meta:
        model = ServiceTCO
        fields = [
            'id', 'name', 'description', 'fullDescription', 
            'price', 'price_type', 'image_url', 'is_deleted'
        ]
        read_only_fields = ['id']
    
    def get_fields(self):
        """Метод для возможности передачи только части полей в запросах"""
        new_fields = OrderedDict()
        for name, field in super().get_fields().items():
            field.required = False
            new_fields[name] = field
        return new_fields


class ServiceTCOListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка услуг (без полного описания)"""
    
    class Meta:
        model = ServiceTCO
        fields = [
            'id', 'name', 'description', 'price', 
            'price_type', 'image_url'
        ]


class CalculationServiceSerializer(serializers.ModelSerializer):
    """Сериализатор для связи м-м (услуги в заявке)"""
    service = ServiceTCOListSerializer(read_only=True)
    service_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = CalculationService
        fields = ['id', 'service', 'service_id', 'quantity']
        read_only_fields = ['id']


class CalculationSerializer(serializers.ModelSerializer):
    """Сериализатор для заявок"""
    creator = serializers.StringRelatedField(read_only=True)
    moderator = serializers.StringRelatedField(read_only=True)
    calculation_services = CalculationServiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = CalculationTCO
        fields = [
            'id', 'status', 'created_at', 'formed_at', 'completed_at',
            'creator', 'moderator', 'total_cost', 'duration_months',
            'start_date', 'end_date', 'calculation_services'
        ]
        read_only_fields = [
            'id', 'created_at', 'formed_at', 'completed_at',
            'creator', 'moderator', 'total_cost', 'duration_months'
        ]
    
    def get_fields(self):
        """Метод для возможности передачи только части полей в запросах"""
        new_fields = OrderedDict()
        for name, field in super().get_fields().items():
            field.required = False
            new_fields[name] = field
        return new_fields


class CalculationListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка заявок (без деталей)"""
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    moderator_username = serializers.CharField(source='moderator.username', read_only=True)
    
    class Meta:
        model = CalculationTCO
        fields = [
            'id', 'status', 'created_at', 'formed_at', 'completed_at',
            'creator_username', 'moderator_username', 'total_cost'
        ]


class CartIconSerializer(serializers.Serializer):
    """Сериализатор для иконки корзины"""
    calculation_id = serializers.IntegerField()
    services_count = serializers.IntegerField()


class AddToCartSerializer(serializers.Serializer):
    """Сериализатор для добавления услуги в корзину"""
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления элемента корзины"""
    
    class Meta:
        model = CalculationService
        fields = ['quantity']


class FormCalculationSerializer(serializers.Serializer):
    """Сериализатор для формирования заявки"""
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class CompleteCalculationSerializer(serializers.Serializer):
    """Сериализатор для завершения заявки"""
    action = serializers.ChoiceField(choices=['complete', 'reject'])
    moderator_comment = serializers.CharField(required=False, allow_blank=True)


class ServiceImageUploadSerializer(serializers.Serializer):
    """Сериализатор для загрузки изображения услуги"""
    image = serializers.ImageField()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'password_confirm']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return data


class UserLoginSerializer(serializers.Serializer):
    """Сериализатор для входа пользователя"""
    username = serializers.CharField()
    password = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля пользователя"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_moderator']
        read_only_fields = ['id', 'username', 'is_moderator']


class LoginSerializer(serializers.Serializer):
    """Сериализатор для авторизации"""
    email = serializers.EmailField(
        required=True,
        help_text='Email пользователя',
        style={'placeholder': 'admin@cto.com'}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        help_text='Пароль пользователя',
        style={'input_type': 'password', 'placeholder': 'admin'}
    )

class CustomUserSerializer(serializers.Serializer):
    """Сериализатор для кастомного пользователя согласно методичке"""
    email = serializers.EmailField(
        required=True,
        help_text='Email пользователя',
        style={'placeholder': 'user@cto.com'}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        help_text='Пароль пользователя',
        style={'input_type': 'password', 'placeholder': 'admin'}
    )
    is_staff = serializers.BooleanField(
        default=False,
        required=False,
        help_text='Статус сотрудника'
    )
    is_superuser = serializers.BooleanField(
        default=False,
        required=False,
        help_text='Статус суперпользователя'
    )
