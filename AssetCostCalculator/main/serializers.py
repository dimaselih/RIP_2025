from rest_framework import serializers
from .models import ServiceTCO, CalculationTCO, CalculationService, User


class ServiceTCOSerializer(serializers.ModelSerializer):
    """Сериализатор для услуг TCO"""
    
    class Meta:
        model = ServiceTCO
        fields = [
            'id', 'name', 'description', 'fullDescription', 
            'price', 'price_type', 'image_url', 'is_deleted'
        ]
        read_only_fields = ['id']


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


class CalculationTCOSerializer(serializers.ModelSerializer):
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


class CalculationTCOListSerializer(serializers.ModelSerializer):
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




class UpdateCartItemSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления элемента корзины"""
    
    class Meta:
        model = CalculationService
        fields = ['quantity']


class FormCalculationTCOSerializer(serializers.Serializer):
    """Сериализатор для формирования заявки"""
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class CompleteCalculationTCOSerializer(serializers.Serializer):
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
