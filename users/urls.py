from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='list'),
    path('create/', views.user_create, name='create'),
    path('<int:user_id>/edit/', views.user_edit, name='edit'),
    path('<int:user_id>/delete/', views.user_delete, name='delete'),
    path('api/communes/<int:wilaya_id>/', views.api_communes_by_wilaya, name='api_communes_by_wilaya'),
]