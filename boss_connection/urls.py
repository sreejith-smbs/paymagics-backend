from rest_framework.urls import urlpatterns
from django.urls import path
from .views import *


urlpatterns = [
    path('', MigrateView.as_view(), name='migrate'),
    path('migration-status/<str:task_id>/', MigrationStatusView.as_view(), name='migration-status'),
    path('debug-config/', DebugConfigView.as_view(), name='debug-config'),
    path('migrate/debug/', DebugMigrationView.as_view(), name='debug-migrate'),

]