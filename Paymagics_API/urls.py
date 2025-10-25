from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/admin/', include('Paymagics_Admin.urls')),
    path('api/payor/', include('Paymagics_Payor.urls')),
    path('api/payorstaff/', include('Paymagics_PayorStaff.urls')),
    
    path('api/bank/', include('Bank.urls')),
    
]
