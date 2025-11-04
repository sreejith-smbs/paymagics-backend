from django.urls import path
from . import views

urlpatterns = [
    path("templates/", views.templates, name="templates"),
    path("templates/<int:pk>/", views.payment_template_detail, name="payment_template_detail"),
    path('templates/<int:template_id>/add_payees/', views.add_payees_to_template, name='add_payees_to_template'),
    path('templates/batches/', views.list_batches, name='list_batches'),
    path("templates/batches/<str:batch_name>/view/", views.view_batch_excel, name="view_batch_excel"),
    path("templates/batches/<str:batch_name>/update/", views.update_batch_excel, name="update_batch_excel"),
    path('templates/<str:batch_name>/download_excel/', views.download_batch_excel, name='download_batch_excel'),
    path("templates/<int:template_id>/options/", views.payment_template_options, name="template_options"),
    path("delete_file/<str:batch_name>/", views.delete_files, name="delete_file") 
    
]
