from django.db import models
from django.contrib.auth.models import User
from admin_panel.models import UserProfile


class PaymentTemplate(models.Model):
    TEMPLATE_TYPES = (
        ("payee", "Payee Template"),
        ("payment", "Payment Template"),
    )

    name = models.CharField(max_length=100, unique=True) 
    template_type = models.CharField(
        max_length=20, choices=TEMPLATE_TYPES, default="payment"   
    )
    dynamic_fields = models.JSONField(blank=True, null=True)
    static_fields = models.JSONField(blank=True, null=True)
    options = models.JSONField(blank=True, null=True)
    field_order = models.JSONField(blank=True, null=True, default=list)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="templates")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def get_ordered_fields(self):
        """Get all fields in user-defined order across categories"""
        if not self.field_order:
            return self._get_default_ordered_fields()
        
        ordered_result = {}
        
        # Add fields in the specified order
        for field_name in self.field_order:
            # Check dynamic fields
            if self.dynamic_fields and field_name in self.dynamic_fields:
                ordered_result[field_name] = {
                    'value': self.dynamic_fields[field_name],
                    'type': 'dynamic',
                    'key': field_name
                }
            # Check static fields
            elif self.static_fields and field_name in self.static_fields:
                ordered_result[field_name] = {
                    'value': self.static_fields[field_name],
                    'type': 'static', 
                    'key': field_name
                }
            # Check options
            elif self.options and field_name in self.options:
                ordered_result[field_name] = {
                    'value': self.options[field_name],
                    'type': 'option',
                    'key': field_name
                }
        
        # Add any remaining fields that weren't in the order list
        ordered_result.update(self._get_remaining_fields(ordered_result))
        
        return ordered_result

    def _get_default_ordered_fields(self):
        """Get fields in default order when no custom order is defined"""
        result = {}
        
        # Dynamic fields first
        if self.dynamic_fields:
            for key, value in self.dynamic_fields.items():
                result[key] = {'value': value, 'type': 'dynamic', 'key': key}
        
        # Static fields next
        if self.static_fields:
            for key, value in self.static_fields.items():
                result[key] = {'value': value, 'type': 'static', 'key': key}
        
        # Options last
        if self.options:
            for key, value in self.options.items():
                result[key] = {'value': value, 'type': 'option', 'key': key}
        
        return result

    def _get_remaining_fields(self, existing_ordered):
        """Get fields that weren't included in the custom order"""
        existing_keys = set(existing_ordered.keys())
        remaining = {}
        
        # Check dynamic fields
        if self.dynamic_fields:
            for key, value in self.dynamic_fields.items():
                if key not in existing_keys:
                    remaining[key] = {'value': value, 'type': 'dynamic', 'key': key}
        
        # Check static fields
        if self.static_fields:
            for key, value in self.static_fields.items():
                if key not in existing_keys:
                    remaining[key] = {'value': value, 'type': 'static', 'key': key}
        
        # Check options
        if self.options:
            for key, value in self.options.items():
                if key not in existing_keys:
                    remaining[key] = {'value': value, 'type': 'option', 'key': key}
        
        return remaining



class TemplatePayee(models.Model):
    template = models.ForeignKey(PaymentTemplate, on_delete=models.CASCADE, related_name="payees")
    payee = models.ForeignKey('payors.Payee', on_delete=models.CASCADE)

    batch_name = models.CharField(max_length=150, blank=True, null=True)

    dynamic_data = models.JSONField(blank=True, null=True)
    static_data = models.JSONField(blank=True, null=True)
    options_data = models.JSONField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payee.ben_name} ({self.batch_name or 'default'}) in {self.template.name}"
