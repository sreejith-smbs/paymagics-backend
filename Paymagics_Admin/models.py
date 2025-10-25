from django.db import models
from django.contrib.auth.models import User


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    PAYOR = "payor", "Payor"
    PAYOR_STAFF = "payor_staff", "Payor Staff"
    PAYEE = "payee", "Payee"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    username = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)

    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PAYEE)

    is_confirmed = models.BooleanField(default=False)
    is_otp_verified = models.BooleanField(default=False)
    referral_code = models.CharField(max_length=6, blank=True, null=True)
    created_by = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="staff_members"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username or self.user.username} ({self.role})"

    @property
    def is_superuser(self):
        return self.user.is_superuser

    @property
    def is_staff(self):
        return self.user.is_staff
    
    @property
    def role_label(self):
        return self.get_role_display()
