from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Customer


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Customer
        fields = ["username", "password", "email"]
        extra_kwargs = {"email": {"required": False}}

    def create(self, validated_data: dict) -> Customer:
        return Customer.objects.create_user(**validated_data)
