from django.contrib import admin
from payor_staff.models import PaymentTemplate, TemplatePayee

admin.site.register(PaymentTemplate)
admin.site.register(TemplatePayee)
