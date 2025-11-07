from rest_framework import serializers
from .models import *

class PayeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payee
        fields = '__all__'

class UpdatePayeeSerializer(serializers.ModelSerializer):
    ben_code = serializers.CharField(read_only=True)
    referralcode = serializers.CharField(read_only=True)
    payor = serializers.PrimaryKeyRelatedField(read_only=True)
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Payee
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class CreatePayeeSerializer(serializers.Serializer):
    acc_no = serializers.CharField(required=False)
    ifsc = serializers.CharField(required=False)

    iban = serializers.CharField(required=False)
    swift_code = serializers.CharField(required=False)
    sort_code = serializers.CharField(required=False)

    ben_code = serializers.CharField(max_length=100)
    ben_name = serializers.CharField(max_length=100)
    add1 = serializers.CharField(max_length=100)
    add2 = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zipcode = serializers.CharField(max_length=20)
    contact = serializers.CharField(max_length=100)
    payee_type = serializers.CharField()
    email = serializers.EmailField()
    bank_name = serializers.CharField(max_length=100, required=False)
    branch = serializers.CharField(max_length=100, required=False)
    bank_account_type = serializers.CharField(max_length=100, required=False)
    category = serializers.IntegerField(required=False)

    def validate(self, data):
        payee_type = data.get('payee_type')

        if payee_type == 'INTERNATIONAL':
            required_fields = ['iban', 'swift_code']
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                raise serializers.ValidationError(
                    f"Missing fields for International payee: {', '.join(missing)}"
                )

        elif payee_type == 'DOMESTIC':
            required_fields = ['acc_no', 'ifsc']
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                raise serializers.ValidationError(
                    f"Missing fields for Domestic payee: {', '.join(missing)}"
                )
        else:
            raise serializers.ValidationError(
                "Invalid payee_type. Must be 'DOMESTIC' or 'INTERNATIONAL'."
            )

        return data


