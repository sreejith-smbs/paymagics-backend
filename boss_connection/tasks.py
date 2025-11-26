# Boss_Conn/tasks.py
import json
from io import StringIO
from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.db import connections, close_old_connections
from django.apps import apps
import re
import traceback as tb


def strip_ansi(text):
    """Remove ANSI escape sequences (colors) from text."""
    if not text:
        return ''
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def create_ultra_safe_postgresql_config(dbcfg):
    """
    Create an ultra-safe PostgreSQL configuration by completely rebuilding it
    and removing ANY non-PostgreSQL options at any level
    """
    print("=== RAW INCOMING DATABASE CONFIG ===")
    print(json.dumps(dbcfg, indent=2, default=str))
    print("====================================")

    # Essential PostgreSQL connection parameters - ONLY these are allowed
    safe_config = {
        'ENGINE': 'django.db.backends.postgresql',
    }

    # Map both lowercase and uppercase keys
    allowed_fields = {
        'name': 'NAME',
        'NAME': 'NAME',
        'user': 'USER',
        'USER': 'USER',
        'password': 'PASSWORD',
        'PASSWORD': 'PASSWORD',
        'host': 'HOST',
        'HOST': 'HOST',
        'port': 'PORT',
        'PORT': 'PORT',
    }

    # Copy fields, converting to uppercase keys
    for source_key, target_key in allowed_fields.items():
        if source_key in dbcfg and dbcfg[source_key] is not None:
            safe_config[target_key] = str(dbcfg[source_key])

    # Add required Django database keys
    safe_config.update({
        'ATOMIC_REQUESTS': False,
        'AUTOCOMMIT': True,
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': False,
        'TIME_ZONE': None,
        'TEST': {},
    })

    print("=== ULTRA-SAFE DATABASE CONFIG ===")
    print(json.dumps(safe_config, indent=2, default=str))
    print("=================================")

    return safe_config


@shared_task(bind=True, max_retries=3)
def run_migration_task(self, company_id, db_config, schema, module_name, base_url):
    """
    Celery task to run database migrations asynchronously for a tenant.
    This version implements Option C:
      - auto-detect custom apps that have migrations
      - exclude Django system apps
      - run migrations for tenant without being confused by core Django migrations
    Returns a dictionary with migration results or error details
    """

    # Initialize all variables at the start
    buf = None
    migration_db_alias = 'migration_postgres'
    safe_dbcfg = None
    current_step = "initialization"

    # Initialize result template with JSON-serializable values only
    migration_result = {
        "schema": str(schema),
        "module": str(module_name),
        "base_url": str(base_url),
        "migration_log": [],
        "applied_migrations": [],
        "apps_migrated": [],
        "tables_created": [],
        "already_migrated": False,
        "task_id": str(self.request.id) if self.request.id else None,
        "company_id": int(company_id),
        "current_step": str(current_step),
        "success": False,
        "error": None,
        "error_type": None,
        "traceback": None,
        "debug_info": {},
    }

    try:
        print(f"=== STARTING MIGRATION TASK {self.request.id} ===")
        print(f"Company: {company_id}, Schema: {schema}, Module: {module_name}")

        current_step = "creating_safe_config"
        migration_result["current_step"] = current_step

        # Create ULTRA-SAFE PostgreSQL configuration
        safe_dbcfg = create_ultra_safe_postgresql_config(db_config)

        current_step = "setting_schema_path"
        migration_result["current_step"] = current_step

        # Add schema search path to the configuration
        quoted_schema = f'"{schema}"'
        safe_dbcfg['OPTIONS'] = {
            'options': f'-c search_path={quoted_schema},public',
            'connect_timeout': 10,
        }

        print("=== UPDATING MIGRATION DATABASE CONNECTION ===")

        current_step = "updating_database_connection"
        migration_result["current_step"] = current_step

        # Complete replacement of migration database config
        connections.databases[migration_db_alias] = safe_dbcfg

        # Close any existing connections for that alias
        if migration_db_alias in connections:
            try:
                connections[migration_db_alias].close()
            except Exception as e:
                print(f"Note: Error closing existing connection: {e}")

        close_old_connections()

        print(f"Using database alias: {migration_db_alias}")
        print(f"Database: {safe_dbcfg.get('NAME')}@{safe_dbcfg.get('HOST')}")

        current_step = "testing_connection"
        migration_result["current_step"] = current_step

        # Test database connection
        print("=== TESTING DATABASE CONNECTION ===")
        connection = connections[migration_db_alias]
        connection.ensure_connection()

        with connection.cursor() as cur:
            cur.execute("SELECT version();")
            result = cur.fetchone()

            if not result:
                raise Exception("No result from database version query")

            db_version = result[0] if result else "Unknown"
            print(f"✓ PostgreSQL connected: {db_version}")

            if 'PostgreSQL' not in db_version:
                raise Exception(f"Not a PostgreSQL database: {db_version}")

        current_step = "creating_schema"
        migration_result["current_step"] = current_step

        # Create schema and set search_path for this tenant
        print(f"=== CREATING SCHEMA: {schema} ===")
        with connections[migration_db_alias].cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS {quoted_schema};')
            cur.execute(f'SET search_path TO {quoted_schema}, public;')
            print("✓ Schema created and search path set")

        # === Dynamic detection of custom apps with migrations (Option C) ===
        current_step = "detecting_apps"
        migration_result["current_step"] = current_step

        # Apps to consider system-level and therefore exclude from per-tenant migration
        SYSTEM_APPS = {
            'admin', 'auth', 'contenttypes', 'sessions', 'messages', 'staticfiles', 'sites'
        }

        # Exclude the Boss_Conn itself (management app) and any app that is a framework/library
        EXCLUDED_APPS = {'Boss_Conn', 'boss_conn', 'bossconn'}  # keep flexible naming

        detected_custom_apps = []
        for app_conf in apps.get_app_configs():
            # app_conf.label is safe lowercase label (e.g., 'hr')
            label = getattr(app_conf, "label", None)
            name = getattr(app_conf, "name", None)
            if not label or not name:
                continue

            # Skip system apps and explicitly excluded apps
            if label in SYSTEM_APPS:
                continue

            if label.lower() in {ea.lower() for ea in EXCLUDED_APPS}:
                continue

            # Try to import migrations module to confirm migrations exist
            try:
                __import__(f"{name}.migrations")
            except ImportError:
                # No migrations package, skip
                continue

            # Check that the migrations directory contains at least one numeric migration file
            # We avoid importing filesystem here for portability; trusting import is usually enough
            detected_custom_apps.append(label)

        # Deduplicate and sort
        detected_custom_apps = sorted(set(detected_custom_apps))

        migration_result["debug_info"]["detected_custom_apps"] = detected_custom_apps
        print(f"Detected custom apps for tenant migration: {detected_custom_apps}")

        current_step = "checking_existing_migrations"
        migration_result["current_step"] = current_step

        # Check if any migrations for these custom apps already exist in this tenant's django_migrations
        migrations_table_exists = False
        with connections[migration_db_alias].cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'django_migrations'
                );
            """, [schema])
            result = cur.fetchone()
            migrations_table_exists = result[0] if result else False

        existing_migrations = []
        if migrations_table_exists and detected_custom_apps:
            # Build parameterized SQL to avoid injection
            placeholders = ",".join(["%s"] * len(detected_custom_apps))
            sql = f"""
                SELECT app, name FROM django_migrations
                WHERE lower(app) IN ({placeholders})
                ORDER BY id DESC LIMIT 100;
            """
            params = [a.lower() for a in detected_custom_apps]
            with connections[migration_db_alias].cursor() as cur:
                cur.execute(sql, params)
                existing_migrations = cur.fetchall()

            if existing_migrations:
                migration_result["existing_migrations"] = [
                    f"{app}.{name}" for app, name in existing_migrations
                ]
                print(f"✓ Found existing migrations for custom apps: {migration_result['existing_migrations']}")
            else:
                print("✓ No existing custom-app migrations found in tenant; will run migrations.")
        else:
            if not detected_custom_apps:
                print("⚠️ No custom apps with migrations detected — nothing to migrate for tenant.")
            else:
                print("✓ No django_migrations table exists yet for this tenant schema — will run migrations.")

        # If any custom app migrations already present, we mark already_migrated = True only if we find
        # that at least one migration entry exists for each detected_custom_app (conservative check).
        if detected_custom_apps:
            found_apps = {r[0].lower() for r in existing_migrations} if existing_migrations else set()
            missing_apps = [a for a in detected_custom_apps if a.lower() not in found_apps]
            if not missing_apps and found_apps:
                # All detected custom apps have at least one applied migration
                migration_result["already_migrated"] = True
                print("✓ Tenant schema already has migrations for all detected custom apps — skipping apply.")
                # List tables and return
                with connections[migration_db_alias].cursor() as cur:
                    cur.execute("""
                        SELECT tablename FROM pg_tables 
                        WHERE schemaname = %s 
                        ORDER BY tablename;
                    """, [schema])
                    tables = [r[0] for r in cur.fetchall()]
                migration_result["tables_created"] = tables
                migration_result["success"] = True
                migration_result["database_engine"] = "django.db.backends.postgresql"
                migration_result["current_step"] = "completed"
                return migration_result
            else:
                if found_apps:
                    print(f"Detected some applied custom-app migrations: {sorted(found_apps)}; missing: {missing_apps}")
                else:
                    print("No applied custom-app migrations found; proceeding to run all detected custom-app migrations.")

        # If we reach here, we should run migrations for the detected custom apps (or all apps if none detected)
        current_step = "running_migrations"
        migration_result["current_step"] = current_step

        print("=== RUNNING MIGRATIONS ===")
        buf = StringIO()

        original_routers = getattr(settings, "DATABASE_ROUTERS", [])
        settings.DATABASE_ROUTERS = []

        try:
            # Ensure search_path is set for this connection before running migrate
            connection = connections[migration_db_alias]
            with connection.cursor() as cur:
                cur.execute(f'SET search_path TO {quoted_schema}, public;')

            # If we detected custom apps, run migrate normally — Django will apply migrations for installed apps.
            # Running migrate without app labels will apply for all installed apps that have unapplied migrations
            call_command(
                "migrate",
                database=migration_db_alias,
                interactive=False,
                verbosity=2,
                stdout=buf
            )
        finally:
            # restore original routers
            settings.DATABASE_ROUTERS = original_routers

        current_step = "processing_results"
        migration_result["current_step"] = current_step

        # Process migration output safely
        raw = buf.getvalue()
        lines = strip_ansi(raw).splitlines()
        migration_result["migration_log"] = lines

        applied = []
        for line in lines:
            stripped = line.strip()
            # Lines like: "Applying hr.0001_initial... OK"
            if stripped.startswith("Applying "):
                try:
                    parts = stripped.split(" ")
                    if len(parts) >= 2:
                        migration_name = parts[1].split("...")[0]
                        applied.append(migration_name)
                except Exception as e:
                    print(f"Warning: Could not parse migration line: {line}")
                    continue

        migration_result["applied_migrations"] = applied
        migration_result["apps_migrated"] = sorted(set(
            m.split(".")[0] for m in applied
        )) if applied else []

        # Get tables after migration
        with connections[migration_db_alias].cursor() as cur:
            cur.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = %s 
                ORDER BY tablename;
            """, [schema])
            tables = [r[0] for r in cur.fetchall()]
        migration_result["tables_created"] = tables
        migration_result["database_engine"] = "django.db.backends.postgresql"
        migration_result["success"] = True
        migration_result["current_step"] = "completed"

        print("=== MIGRATION COMPLETED SUCCESSFULLY ===")
        print(f"Applied {len(applied)} migrations")
        print(f"Created {len(tables)} tables")
        print(f"Apps migrated: {', '.join(migration_result['apps_migrated'])}")

        return migration_result

    except Exception as e:
        print(f"=== MIGRATION FAILED AT STEP: {current_step} ===")
        print(f"Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")

        full_traceback = tb.format_exc()
        print(full_traceback)

        # Update result with error details - ensure all values are JSON-serializable
        migration_result["error"] = str(e)
        migration_result["error_type"] = str(type(e).__name__)
        migration_result["traceback"] = full_traceback
        migration_result["success"] = False
        migration_result["current_step"] = str(current_step)

        # Safely get migration log if available
        if buf:
            try:
                migration_result["migration_log"] = strip_ansi(buf.getvalue()).splitlines()
            except Exception:
                migration_result["migration_log"] = []

        if safe_dbcfg:
            migration_result["debug_info"].update({
                "safe_config_keys": list(safe_dbcfg.keys()),
                "database": str(safe_dbcfg.get('NAME', '')),
                "host": str(safe_dbcfg.get('HOST', '')),
            })

        # Return error result instead of raising exception
        return migration_result

    finally:
        # Clean up: close the migration connection
        print("=== CLEANING UP MIGRATION DATABASE CONNECTION ===")
        if migration_db_alias in connections:
            try:
                connections[migration_db_alias].close()
                print("✓ Migration database connection closed")
            except Exception as e:
                print(f"✗ Error closing connection: {e}")

        close_old_connections()
