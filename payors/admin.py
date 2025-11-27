from django.contrib import admin
from payors.models import Category, Payee, CategoryReferralCode

admin.site.register(Category)
admin.site.register(Payee)
admin.site.register(CategoryReferralCode)

