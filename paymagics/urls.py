from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/admin/', include('admin_panel.urls')),
    path('api/payor/', include('payors.urls')),
    path('api/payorstaff/', include('payor_staff.urls')),
    path('api/bank/', include('bank_partner.urls')),
    path('api/migrate/', include('boss_connection.urls')),
]
