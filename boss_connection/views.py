# Boss_Conn/views.py

import json
from django.conf import settings
from rest_framework import views, response, status
from .serializers import MigrateRequestSerializer
from .permissions import ModuleAPIKeyPermission
from .tasks import run_migration_task

from django.conf import settings

class MigrateView(views.APIView):
    """
    Async migration endpoint using Celery (following TaskMagics pattern)
    """
    authentication_classes = []
    permission_classes = [ModuleAPIKeyPermission]

    def post(self, request):
        print("=== COMPLETE MIGRATION REQUEST ===")
        print(f"Method: {request.method}")
        print(f"Path: {request.path}")
        print(f"Full data: {request.data}")
        print("=================================")

        ser = MigrateRequestSerializer(data=request.data)
        if not ser.is_valid():
            print(f"Serializer errors: {ser.errors}")
            return response.Response(
                {"error": "Invalid request data", "details": ser.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        cid = ser.validated_data["company_id"]
        dbcfg = ser.validated_data["db"]
        schema = f"company_{cid}_{settings.MODULE_NAME}".lower()
        base_url = request.build_absolute_uri("/").rstrip("/")

        print(f"Starting migration for company {cid}, schema {schema}")

        # Start the Celery task asynchronously
        try:
            task = run_migration_task.delay(
                company_id=cid,
                db_config=dbcfg,
                schema=schema,
                module_name=settings.MODULE_NAME,
                base_url=base_url
            )

            return response.Response({
                "message": "Migration started",
                "task_id": task.id,
                "schema": schema,
                "company_id": cid,
                "status": "PENDING",
                "check_status_url": f"{base_url}/api/boss/migration-status/{task.id}/"
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            import traceback
            return response.Response({
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MigrationStatusView(views.APIView):
    """View to check the status of a migration task"""
    authentication_classes = []
    permission_classes = [ModuleAPIKeyPermission]

    def get(self, request, task_id):
        from celery.result import AsyncResult

        try:
            task_result = AsyncResult(task_id)

            response_data = {
                "task_id": task_id,
                "status": task_result.status,
                "state": task_result.state,
            }

            # Task is still pending or running
            if task_result.state in ['PENDING', 'STARTED', 'RETRY']:
                response_data["info"] = "Task is still running"
                response_data["success"] = None
                return response.Response(response_data)

            # Task completed (either successfully or with failure)
            if task_result.ready():
                if task_result.successful():
                    try:
                        result = task_result.result

                        # Check if result indicates an error
                        if isinstance(result, dict):
                            if result.get('error') or result.get('success') == False:
                                # Task ran but migration failed
                                response_data["status"] = "FAILED"
                                response_data["success"] = False
                                response_data["error"] = result.get('error', 'Unknown error')
                                response_data["error_type"] = result.get('error_type')
                                response_data["current_step"] = result.get('current_step')
                                response_data["message"] = result.get('message', 'Migration failed')

                                # Include limited error details
                                if result.get('traceback'):
                                    response_data["traceback"] = result.get('traceback')[-500:]
                                if result.get('migration_log'):
                                    response_data["migration_log"] = result.get('migration_log', [])
                                if result.get('debug_info'):
                                    response_data["debug_info"] = result.get('debug_info', {})
                            else:
                                # Task succeeded
                                response_data["status"] = "SUCCESS"
                                response_data["success"] = True
                                response_data["result"] = result
                                response_data["message"] = result.get('message', 'Migration completed successfully')
                        else:
                            response_data["status"] = "SUCCESS"
                            response_data["success"] = True
                            response_data["result"] = result

                    except Exception as e:
                        response_data["status"] = "FAILED"
                        response_data["success"] = False
                        response_data["error"] = f"Error retrieving task result: {str(e)}"
                        response_data["error_type"] = type(e).__name__

                else:
                    # Task failed with exception
                    response_data["status"] = "FAILURE"
                    response_data["success"] = False

                    try:
                        error = task_result.result

                        if isinstance(error, Exception):
                            response_data["error"] = str(error)
                            response_data["error_type"] = type(error).__name__
                        else:
                            response_data["error"] = str(error)

                        # Try to get traceback
                        if hasattr(task_result, 'traceback') and task_result.traceback:
                            response_data["traceback"] = str(task_result.traceback)[-500:]

                        # Try to get additional info
                        if hasattr(task_result, 'info'):
                            info = task_result.info
                            if isinstance(info, dict):
                                response_data["info"] = info
                            else:
                                response_data["info"] = str(info)
                    except Exception as e:
                        response_data["error"] = f"Error processing task failure: {str(e)}"
            else:
                response_data["info"] = "Task state unknown"
                response_data["success"] = None

            return response.Response(response_data)

        except Exception as e:
            import traceback
            return response.Response({
                "error": f"Error retrieving task status: {str(e)}",
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()[-500:],
                "task_id": task_id,
                "success": False,
                "status": "ERROR"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DebugMigrationView(views.APIView):
    """Debug view to test migration without Celery (synchronous)"""
    authentication_classes = []
    permission_classes = [ModuleAPIKeyPermission]

    def post(self, request):
        ser = MigrateRequestSerializer(data=request.data)
        if not ser.is_valid():
            return response.Response({"errors": ser.errors}, status=400)

        cid = ser.validated_data["company_id"]
        dbcfg = ser.validated_data["db"]
        schema = f"company_{cid}_{settings.MODULE_NAME}".lower()
        base_url = request.build_absolute_uri("/").rstrip("/")

        # Run synchronously (not as Celery task) - for debugging
        try:
            result = run_migration_task(
                company_id=cid,
                db_config=dbcfg,
                schema=schema,
                module_name=settings.MODULE_NAME,
                base_url=base_url
            )
            return response.Response(result)
        except Exception as e:
            import traceback
            return response.Response({
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }, status=500)


class DebugConfigView(views.APIView):
    authentication_classes = []
    permission_classes = [ModuleAPIKeyPermission]

    def post(self, request):
        """Debug endpoint to see exactly what database config is being sent"""
        ser = MigrateRequestSerializer(data=request.data)
        if not ser.is_valid():
            return response.Response({"errors": ser.errors}, status=400)

        dbcfg = ser.validated_data["db"]
        debug_info = {
            "received_config_keys": list(dbcfg.keys()),
            "received_config_full": dbcfg,
            "has_options": 'OPTIONS' in dbcfg,
            "options_content": dbcfg.get('OPTIONS', {}),
            "engine": dbcfg.get('ENGINE'),
            "problematic_keys": []
        }

        mysql_options = ['init_command', 'charset', 'use_unicode', 'sql_mode']
        for opt in mysql_options:
            if opt in dbcfg:
                debug_info["problematic_keys"].append(f"root_level: {opt}")
            if 'OPTIONS' in dbcfg and opt in dbcfg['OPTIONS']:
                debug_info["problematic_keys"].append(f"options_level: {opt}")

        return response.Response(debug_info)


