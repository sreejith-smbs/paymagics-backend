from django.db import models

# Create your models here.
from django.db import models
from admin_panel.models import UserProfile 


class Bank(models.Model):
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    acc_type = models.CharField(max_length=100, blank=True, null=True)
    acc_no = models.CharField(max_length=100, blank=True, null=True)
    ifsc = models.CharField(max_length=100, blank=True, null=True)
    branch = models.CharField(max_length=100, blank=True, null=True)
    
    acc_holder = models.CharField(max_length=100, blank=True, null=True)  
    mobile = models.CharField(max_length=15, blank=True, null=True)      
    
    email = models.EmailField(max_length=100, blank=True, null=True)
    
    creator = models.ForeignKey(UserProfile, on_delete=models.CASCADE, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_name} - {self.acc_no}"