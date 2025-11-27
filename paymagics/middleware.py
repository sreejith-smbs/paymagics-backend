import json
from urllib import request as urlreq
from django.db import connections, close_old_connections
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.exceptions import TokenError
from decouple import config
print(config('DB_NAME'))
print("my sql name")

class TenantMiddleware:
    """
    Multi-tenant middleware with proper fallback handling (following TaskMagics pattern):
    1) Skip on /admin/ and /api/hr/login/ → use default MySQL database
    2) Decode JWT (no ORM) → get company_id
    3) If company_id exists, fetch DBConfig from BossMagics API
    4) If API fails, use hardcoded PostgreSQL fallback
    5) If company_id is missing, use default MySQL database
    6) Handle schema/database switching based on database type
    """

    def __init__(self, get_response):
        self.get_response = get_response
        from rest_framework_simplejwt.settings import api_settings
        self.token_backend = TokenBackend(
            api_settings.ALGORITHM,
            signing_key=settings.SIMPLE_JWT['SIGNING_KEY']
        )

    def __call__(self, request):
        # 1) Admin pages and login endpoint must use default MySQL database
        login_paths = ["/api/hr/login", "/api/hr/login/"]
        if request.path in login_paths or request.path.startswith("/admin"):
            print("🔐 HR Login/Admin → forcing MySQL default DB")
            self._switch_to_mysql_default()
            return self.get_response(request)

        # 2) Extract & decode raw JWT for API requests
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        company_id = None

        if auth.startswith("Bearer "):
            raw = auth.split()[1]
            try:
                payload = self.token_backend.decode(raw)
                company_id = payload.get("company_id")
                print(f"🔑 JWT decoded - company_id: {company_id}")
            except TokenError as e:
                print(f"⚠️ JWT decode error: {e}")
                company_id = None

        # 3) If no company_id, use default MySQL database (HireMagics standalone)
        if not company_id:
            print("📍 No company_id found - using MySQL default database")
            self._switch_to_mysql_default()
            return self.get_response(request)

        # 4) If we have a company_id, switch to tenant database/schema (BossMagics tenant)
        print(f"🏢 Company ID detected: {company_id} - switching to tenant database")

        module = request.META.get("HTTP_X_MODULE", settings.MODULE_NAME)
        cache_key = f"dbcfg:{company_id}"
        cfg = cache.get(cache_key)

        if not cfg:
            print(f"🔍 No cached config - fetching from BossMagics API...")
            # Try to fetch from BossMagics API
            cfg = self._fetch_database_config(company_id, auth)

            # CRITICAL: If API fails, use hardcoded PostgreSQL fallback
            if not cfg:
                print(f"⚠️ API fetch failed - using FALLBACK PostgreSQL config")
                self._switch_to_mysql_default()
                return self.get_response(request)
            else:
                print(f"✅ API config received successfully")

            # Cache the config (whether from API or fallback)
            if cfg:
                cache.set(cache_key, cfg, 300)  # Cache for 5 minutes
        else:
            print(f"✅ Using cached database config")

        # 5) Apply tenant database configuration and set schema
        if cfg:
            schema = f"company_{company_id}_{module}".lower()

            # CRITICAL: Complete database replacement, not update
            print(f"🔄 Switching to tenant database: {cfg['NAME']}")

            # Add ALL required Django database config keys
            cfg.update({
                'ATOMIC_REQUESTS': False,
                'AUTOCOMMIT': True,
                'CONN_MAX_AGE': 0,
                'CONN_HEALTH_CHECKS': False,
                'TIME_ZONE': None,
                'TEST': {},
            })

            # COMPLETE REPLACEMENT - not update
            connections.databases["default"] = cfg

            # Force close all connections
            close_old_connections()

            # Clear connection in thread-local storage
            if hasattr(connections._connections, 'default'):
                del connections._connections.default

            # Handle schema/database based on database type
            if cfg["ENGINE"] == "django.db.backends.postgresql":
                self._set_postgresql_schema(schema)
            elif cfg["ENGINE"] == "django.db.backends.mysql":
                print(f"✓ Using MySQL database: {cfg['NAME']}")
            else:
                print(f"✓ Using database engine: {cfg['ENGINE']}")
        else:
            # This should never happen due to fallback, but just in case
            print("❌ CRITICAL: No database config available - using MySQL default")
            self._switch_to_mysql_default()

        return self.get_response(request)

    def _switch_to_mysql_default(self):
        """
        Switch to original MySQL configuration for HireMagics standalone
        """
        original_default = {
            'ENGINE': config('DB_ENGINE'),
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'ATOMIC_REQUESTS': False,
            'AUTOCOMMIT': True,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
            'TIME_ZONE': None,
            'TEST': {},
        }
        # Complete replacement of database config
        connections.databases["default"] = original_default
        # Force close all connections
        close_old_connections()
        # Clear connection in thread-local storage
        if hasattr(connections._connections, 'default'):
            del connections._connections.default
        print(f"✓ Switched to MySQL default: {original_default['NAME']}")

    def _fetch_database_config(self, company_id, auth_header):
        """
        Fetch database configuration from BossMagics API
        Returns config dict or None if failed
        """
        try:
            url = f"https://api.bossmagics.com/api/db-configs/?company={company_id}"
            req = urlreq.Request(url, headers={"Authorization": auth_header})

            with urlreq.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

                if data and len(data) > 0:
                    db_config = data[0]
                    print(db_config['name'])
                    print(f"📦 API Response - DB: {db_config.get('name')}, Host: {db_config.get('host')}")

                    # Create PostgreSQL configuration
                    cfg = {
                        "ENGINE": "django.db.backends.postgresql",
                        "NAME": db_config["name"],
                        "USER": db_config["user"],
                        "PASSWORD": db_config["password"],
                        "HOST": db_config["host"],
                        "PORT": db_config["port"],
                        "OPTIONS": {
                            "connect_timeout": 10,
                        }
                    }
                    return cfg
                else:
                    print("⚠️ Empty response from BossMagics API")
                    return None

        except Exception as e:
            print(f"❌ BossMagics API call failed: {type(e).__name__}: {e}")
            return None



    def _set_postgresql_schema(self, schema):
        """
        Set PostgreSQL schema for the current connection
        """
        try:
            with connections["default"].cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
                cur.execute(f"SET search_path TO {schema}, public;")
                print(f"✓ PostgreSQL schema set: {schema}")
        except Exception as e:
            print(f"❌ Error setting PostgreSQL schema '{schema}': {e}")
            # Continue anyway - migrations will handle schema creation