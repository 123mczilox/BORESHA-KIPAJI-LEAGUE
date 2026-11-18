from django.urls import path

from . import views


app_name = 'statistics'

urlpatterns = [
	path('players/', views.player_statistics, name='player_statistics'),
]
