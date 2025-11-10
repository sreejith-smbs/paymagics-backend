from django.db import models
from Paymagics_Admin.models import UserProfile
import uuid
from Paymagics_PayorStaff.models import *

class Category(models.Model):
    category = models.CharField(max_length=55, unique=True)
    description = models.CharField(max_length=500,blank=True,null=True)
    count = models.IntegerField(default=0)
    referral_code = models.CharField(max_length=6, blank=True, null=True)

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


import string, random
from django.db import models
from django.utils import timezone

class CategoryReferralCode(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='referral_codes')
    referrer = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_category_referrals'
    )
    code = models.CharField(max_length=10, unique=True)
    is_used = models.BooleanField(default=False)
    referred_payee = models.OneToOneField(
        'Payee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_category_referral'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def mark_used(self, payee):
        self.is_used = True
        self.referred_payee = payee
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.category.category} | {self.code} ({'USED' if self.is_used else 'ACTIVE'})"
