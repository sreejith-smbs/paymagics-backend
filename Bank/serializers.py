from rest_framework import serializers
from .models import Bank


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = '__all__'

    def validate(self, data):
        if self.instance is None:
            required_fields = ['bank_name', 'acc_type', 'acc_no', 'ifsc', 'branch', 'acc_holder', 'mobile', 'email']
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                raise serializers.ValidationError({
                    field: "This field is required." for field in missing
                })

        return data