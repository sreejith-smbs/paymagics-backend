from django.urls import path
from .views import *

urlpatterns = [
    path('', view_banks, name='view_banks'),
    path('add/', add_bank, name='add_bank'),
    path('<int:pk>/', get_bank, name='get_bank'),
    path('<int:pk>/update/', update_bank, name='update_bank'),
    path('<int:pk>/delete/', delete_bank, name='delete_bank'),
    path('type/', filter_banks_by_type, name='filter_by_type'),
    path('search/', search_banks, name='search')    
]