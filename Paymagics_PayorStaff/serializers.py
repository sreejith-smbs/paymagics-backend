# Paymagics_PayorStaff/serializers.py
from rest_framework import serializers
from .models import PaymentTemplate, TemplatePayee, PaymentTemp  # <- already imported

class TemplatePayeeSerializer(serializers.ModelSerializer):
    payee_details = serializers.SerializerMethodField()

    class Meta:
        model = TemplatePayee
        fields = "__all__"

    def get_payee_details(self, obj):
        return {
            "id": obj.payee.id,
            "ben_code": obj.payee.ben_code,
            "ben_name": obj.payee.ben_name,
        }


class PaymentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTemplate
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, data):
        template_type = data.get("template_type")
        options = data.get("options")

        if template_type == "payee" and options:
            raise serializers.ValidationError("Options are not allowed for Payee templates.")

        return data


class PaymentTempSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTemp
        fields = "__all__"
