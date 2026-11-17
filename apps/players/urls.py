from django.urls import path

from . import views


app_name = 'players'

urlpatterns = [
    path('', views.player_list, name='player_list'),
    path('create/', views.player_create, name='player_create'),
    path('registrations/create/', views.registration_create,
         name='registration_create'),
    path(
        'registrations/<int:registration_id>/transfer/',
        views.registration_transfer,
        name='registration_transfer',
    ),
    path('<int:pk>/', views.player_detail, name='player_detail'),
    path(
        '<int:pk>/edit/',
        views.player_update,
        name='player_update',
    ),
    path(
        '<int:pk>/registrations/',
        views.registration_history,
        name='registration_history',
    ),
]
