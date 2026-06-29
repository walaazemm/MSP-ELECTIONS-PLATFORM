from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    # Bureau creation (scoped by role)
    path('add/', views.create_bureau, name='create_bureau'),
    
    # Bureau list (scoped by role + election filter)
    path('bureaux/', views.bureau_list, name='bureau_list'),
    
    # Data entry for a specific bureau
    path('data/<int:bureau_id>/', views.enter_results, name='enter_results'),
    path('edit/<int:bureau_id>/', views.edit_bureau, name='edit_bureau'),
    path('delete/<int:bureau_id>/', views.delete_bureau, name='delete_bureau'),
    path('api/communes/<int:wilaya_id>/', views.api_communes_by_wilaya, name='api_communes_by_wilaya'),
    path('api/add-list/', views.add_list_ajax, name='add_list_ajax'),
    path('api/wilaya/<int:wilaya_id>/seats/', views.update_wilaya_seats, name='update_wilaya_seats'),
    path('bulk-delete/', views.bulk_delete_bureaux, name='bulk_delete_bureaux'),
    path('audit-log/', views.audit_log, name='audit_log'),
    path('audit/<int:log_id>/details/', views.get_audit_details, name='audit_details'),
]