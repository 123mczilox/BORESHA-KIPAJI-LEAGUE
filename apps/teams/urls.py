from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    # Public pages
    path('', views.team_list, name='team_list'),
    path('<int:pk>/', views.team_detail, name='team_detail'),

    # Team management
    path('create/', views.team_create, name='team_create'),
    path('<int:pk>/edit/', views.team_update, name='team_update'),
    path(
        '<int:pk>/toggle-status/',
        views.team_toggle_status,
        name='team_toggle_status',
    ),
]