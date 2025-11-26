# Boss_Conn/migrate_view.py

from django.core.management import call_command
from django.db             import connections
from rest_framework        import views, permissions, response, status
from .serializers          import MigrateRequestSerializer

class MigrateView(views.APIView):
    # REMOVE JWT auth on this endpoint
    authentication_classes = []
    permission_classes     = [permissions.AllowAny]

    def post(self, request):
        """
        Body:
          {
            "company_id": 2,
            "db": { "NAME": "...", "USER": "...", ... }
          }
        """
        serializer = MigrateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company_id = serializer.validated_data["company_id"]
        dbcfg      = serializer.validated_data["db"]
        schema     = f"{company_id}_crm"

        # 1) Override default DB
        connections.databases["default"].update({
            "ENGINE":   "django.db.backends.postgresql",
            **dbcfg,
        })

        # 2) Create schema + set search_path
        quoted = connections["default"].ops.quote_name(schema)
        with connections["default"].cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted};")
            cur.execute(f"SET search_path TO {quoted}, public;")

        # 3) Run migrations for this app (label="crm")
        call_command(
            "migrate",
            "crm",
            database="default",
            interactive=False,
            verbosity=1,
        )

        return response.Response(
            {"detail": f"Schema {schema} & crm migrations applied."},
            status=status.HTTP_200_OK
        )
