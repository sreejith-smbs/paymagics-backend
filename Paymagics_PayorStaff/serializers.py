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
    ordered_fields = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentTemplate
        fields = ["id", "name", "template_type", "dynamic_fields", "static_fields", "options", "field_order", "ordered_fields", "created_at", "created_by"]
        read_only_fields = ("created_by",)

    def get_ordered_fields(self, obj):
        """Return fields in user-defined order"""
        return obj.get_ordered_fields()

    def update(self, instance, validated_data):
        # Auto-update field_order before saving
        validated_data = self._auto_update_field_order(instance, validated_data)
        return super().update(instance, validated_data)

    def _auto_update_field_order(self, instance, validated_data):
        """Automatically update field_order when fields are added/removed"""
        # Only proceed if any of the fields are being updated
        if not any(key in validated_data for key in ['dynamic_fields', 'static_fields', 'options']):
            return validated_data
        
        existing_field_order = instance.field_order or []
        
        # Get current fields from instance
        current_fields = set()
        if instance.dynamic_fields:
            current_fields.update(instance.dynamic_fields.keys())
        if instance.static_fields:
            current_fields.update(instance.static_fields.keys())
        if instance.options:
            current_fields.update(instance.options.keys())
        
        # Get updated fields from validated_data and existing instance
        updated_fields = set()
        
        # Dynamic fields
        dynamic_fields = validated_data.get('dynamic_fields', instance.dynamic_fields)
        if dynamic_fields:
            updated_fields.update(dynamic_fields.keys())
        
        # Static fields
        static_fields = validated_data.get('static_fields', instance.static_fields)
        if static_fields:
            updated_fields.update(static_fields.keys())
        
        # Options
        options = validated_data.get('options', instance.options)
        if options:
            updated_fields.update(options.keys())
        
        # Find changes
        added_fields = updated_fields - current_fields
        removed_fields = current_fields - updated_fields
        
        # Update field_order
        updated_order = existing_field_order.copy()
        
        # Remove deleted fields
        if removed_fields:
            updated_order = [field for field in updated_order if field not in removed_fields]
        
        # Add new fields at the end
        if added_fields:
            updated_order.extend(list(added_fields))
        
        # Only update if there are changes and field_order wasn't explicitly provided
        if ('field_order' not in validated_data and 
            (set(updated_order) != set(existing_field_order) or len(updated_order) != len(existing_field_order))):
            validated_data['field_order'] = updated_order
        
        return validated_data

    def validate(self, data):
        template_type = data.get("template_type")
        options = data.get("options")
        field_order = data.get("field_order", [])

        # Existing validation
        if template_type == "payee" and options:
            raise serializers.ValidationError("Options are not allowed for Payee templates.")

        # New validation for field_order
        if field_order:
            self._validate_field_order(field_order, data)

        return data

    def _validate_field_order(self, field_order, data):
        """Validate that field_order only contains existing field keys"""
        if not isinstance(field_order, list):
            raise serializers.ValidationError({
                "field_order": "Field order must be a list of field names."
            })

        # Get all available field keys from dynamic_fields, static_fields, and options
        available_fields = set()
        
        # Add dynamic fields keys
        dynamic_fields = data.get("dynamic_fields", {})
        if dynamic_fields and isinstance(dynamic_fields, dict):
            available_fields.update(dynamic_fields.keys())
        
        # Add static fields keys  
        static_fields = data.get("static_fields", {})
        if static_fields and isinstance(static_fields, dict):
            available_fields.update(static_fields.keys())
        
        # Add options keys
        options = data.get("options", {})
        if options and isinstance(options, dict):
            available_fields.update(options.keys())

        # Check if all field_order items exist in available fields
        invalid_fields = []
        for field_name in field_order:
            if field_name not in available_fields:
                invalid_fields.append(field_name)

        if invalid_fields:
            raise serializers.ValidationError({
                "field_order": f"The following fields in field_order do not exist in dynamic_fields, static_fields, or options: {', '.join(invalid_fields)}"
            })



class PaymentTempSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTemp
        fields = "__all__"


