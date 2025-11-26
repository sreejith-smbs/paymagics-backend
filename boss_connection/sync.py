# Boss_Conn/sync.py

from django.contrib.auth import get_user_model

def sync_user_from_boss(user_data, company_id):
    """
    Create or update a module-side User based on boss_magics JWT claims.
    """
    User = get_user_model()
    user, _ = User.objects.update_or_create(
        username=user_data["username"],
        defaults={
            "email":          user_data["email"],
            "company_id":     company_id,
            "is_module_user": True
        }
    )
    user.set_unusable_password()
    user.save()
    return user
