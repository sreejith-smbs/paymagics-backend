# Boss_Conn/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .sync import sync_user_from_boss
from django.contrib.auth import get_user_model


class CustomJWTAuthentication(JWTAuthentication):
    """
    After TenantMiddleware has switched us to the correct database,
    get_user() can safely use ORM to sync/fetch user.
    If no company_id, assume user is from default MySQL database.
    """
    def get_user(self, validated_token):
        p = validated_token.payload
        user_id = p.get("user_id")
        company_id = p.get("company_id")
        username = p.get("username")
        email = p.get("email")

        if not user_id:
            raise InvalidToken("Token missing user_id")

        # If company_id is missing, fetch user from default database
        if not company_id:
            User = get_user_model()
            try:
                user = User.objects.using('default').get(id=user_id)
                return user
            except User.DoesNotExist:
                raise InvalidToken("User not found in default database")

        # If company_id exists, ensure username and email are present
        if not all([username, email]):
            raise InvalidToken("Token missing required fields")

        # Sync user from boss_magics for tenant database
        return sync_user_from_boss({"username": username, "email": email}, company_id)