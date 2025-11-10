from django.urls import path
from .views import *

urlpatterns = [
    #payee CRUD operations
    path('payee-register/', create_payee, name='payee_register'),
    path('payee-edit/<int:pk>/', edit_payee, name='edit_payee'),
    path('delete_payee/<int:pk>/',delete_payee,name='delete_payee'),
    path('payee-list/', payee_list, name='payee_list'),
    path('payee/<int:pk>/', payee_detail, name='payee'),

    #list CRUD operations
    path('create_edit_list/', create_or_update_category, name='create_edit_list'),
    path('view_lists/', view_list, name='view_list'),
    path('delete_list/<int:pk>/', delete_categ, name='delete_list'),
    path('remove_from_list/', remove_payee_from_category, name='remove_from_list'),
    path("payees_in_list/<int:category>/", payees_in_list, name="payees_in_list"),
    
    #payee excel
    path('export-payees/<int:template_id>/', export_payees_excel, name='export_payees'),

    #referrel
    path('referral/', send_invite_email, name='add_payee'),
    # 1️⃣ Generate a one-time referral code (authenticated)
    path('categories/<int:category_id>/referral-code/', create_category_referral_code, name='create_category_referral_code'),

    # 2️⃣ Public endpoint — create a payee via referral code
    path('payees/referral/<str:referral_code>/', create_payee_via_referral, name='create_payee_via_referral'),


    #list dashboard counts
    path("list_counts/",list_counts, name='list-counts'),

    # payment template
    path("templates/<int:template_id>/options/", payment_template_options, name="template_options"),
    path("delete_file/<str:batch_name>/", delete_files, name="delete_file") ,



]