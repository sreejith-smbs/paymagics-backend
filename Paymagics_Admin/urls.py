from django.urls import path
from . import views

urlpatterns = [

    # login of admin/payor/payorstaff
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    
    # Authentication & Signup
    path("signup/", views.signup, name="signup"),
    
    path("search/payors/", views.search_payors, name="search_payors"),
    path("search/payor-staff/", views.search_payor_staff, name="search_payor_staff"),
    
    # Password reset
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),

    # Admin actions
    path("payors/unapproved/", views.list_unapproved_payors, name="list_unapproved_payors"),
    path("payors/<int:pk>/approve/", views.approve_payor, name="approve_payor"),

    # Payor and Payor Staff Management
    path("payors/create/", views.create_payor, name="create-payors"),
    path("payors/view/", views.list_payors, name="list_payors"),
    path("payors/<int:pk>/update/", views.update_payor, name="update_payor"),
    path("payors/<int:pk>/delete/", views.delete_payor, name="delete_payor"),
    
    path("payor-staff/create/", views.create_payor_staff, name="create-payor-staff"),
    path("payor-staff/view/", views.list_payor_staff, name="list-payor-staff"),
    path("payor-staff/<int:pk>/update/", views.edit_payor_staff, name="edit-payor-staff"),
    path("payor-staff/<int:pk>/delete/", views.delete_payor_staff, name="delete-payor-staff"),
    
    # Dashboard
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    
    # search
    path("search/categories/", views.search_categories, name="search_categories"),
    path("search/payees/", views.search_payees, name="search_payees"),
    path("search/payors/", views.search_payors, name="search_payors"),
    path("search/payor-staff/", views.search_payor_staff, name="search_payor_staff"),
    
]
