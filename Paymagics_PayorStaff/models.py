from django.db import models
from django.contrib.auth.models import User
from Paymagics_Admin.models import UserProfile

class PaymentTemp(models.Model): 
	user = models.ForeignKey(User,on_delete=models.CASCADE) 
	ben_code = models.CharField(max_length=100) 
	ben_name = models.CharField(max_length=100) 
	add1 = models.CharField(max_length=100) 
	add2 = models.CharField(max_length=100) 
	city = models.CharField(max_length=100) 
	state = models.CharField(max_length=100) 
	zipcode = models.CharField(max_length=6) 
	contact = models.CharField(max_length=100) 
	email = models.CharField(max_length=100) 
	acc_no = models.CharField(max_length=100,blank=True,null=True) 
	ifsc = models.CharField(max_length=100,blank=True,null=True) 
	bank_name = models.CharField(max_length=100,blank=True,null=True) 
	branch = models.CharField(max_length=100,blank=True,null=True) 
	referralcode = models.CharField(max_length=6,blank=True,null=True) 
	payor = models.ForeignKey(UserProfile,on_delete=models.CASCADE,blank=True,null=True) 
	is_confirmed = models.BooleanField(default=False,blank=True,null=True)


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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="templates")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class TemplatePayee(models.Model):
    template = models.ForeignKey(PaymentTemplate, on_delete=models.CASCADE, related_name="payees")
    payee = models.ForeignKey('Paymagics_Payor.Payee', on_delete=models.CASCADE)

    batch_name = models.CharField(max_length=150, blank=True, null=True)

    dynamic_data = models.JSONField(blank=True, null=True)
    static_data = models.JSONField(blank=True, null=True)
    options_data = models.JSONField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payee.ben_name} ({self.batch_name or 'default'}) in {self.template.name}"
