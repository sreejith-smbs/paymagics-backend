from django.db import models
from Paymagics_Admin.models import UserProfile
import uuid
from Paymagics_PayorStaff.models import *

class Category(models.Model):
    category = models.CharField(max_length=55, unique=True)
    count = models.IntegerField(default=0)

    def __str__(self):
        return self.category


class Payee(models.Model):
    PAYEE_TYPE_CHOICES = (
    ('DOMESTIC', 'Domestic'),
    ('INTERNATIONAL', 'International'),
    )
    ben_code = models.CharField(max_length=100,blank=True,null=True)
    ben_name = models.CharField(max_length=100,blank=True,null=True)
    add1 = models.CharField(max_length=100,blank=True,null=True)
    add2 = models.CharField(max_length=100,blank=True,null=True)
    city = models.CharField(max_length=100,blank=True,null=True)
    state = models.CharField(max_length=100,blank=True,null=True)
    zipcode = models.CharField(max_length=20,blank=True,null=True)
    contact = models.CharField(max_length=100,blank=True,null=True)
    email = models.CharField(max_length=100,blank=True,null=True)
    payee_type = models.CharField(
        max_length=20,
        choices=PAYEE_TYPE_CHOICES,
        default='DOMESTIC')

    acc_no = models.CharField(max_length=100,blank=True,null=True)
    ifsc = models.CharField(max_length=100,blank=True,null=True)

    iban= models.CharField(max_length=100, blank=True, null=True)
    swift_code = models.CharField(max_length=100, blank=True, null=True)
    sort_code = models.CharField(max_length=100, blank=True, null=True)

    bank_name = models.CharField(max_length=100,blank=True,null=True)
    branch = models.CharField(max_length=100,blank=True,null=True)
    bank_account_type = models.CharField(max_length=100,blank=True,null=True)
    referralcode = models.CharField(max_length=6,blank=True,null=True)
    payor = models.ForeignKey(UserProfile,on_delete=models.CASCADE,blank=True,null=True)
    is_confirmed = models.BooleanField(default=False,blank=True,null=True)
    categories = models.ManyToManyField(Category, related_name='payees', blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.ben_name} - {'Active' if self.is_active else 'Deleted'}"


class ReferralInvite(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('clicked', 'Clicked'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]

    payor = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='sent_invites')
    payee_email = models.EmailField()
    referral_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invite from {self.payor.username} to {self.payee_email} [{self.status}]"
      

