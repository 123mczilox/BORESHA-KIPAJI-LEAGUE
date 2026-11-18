from django.urls import path

from . import views


app_name = 'standings'

urlpatterns = [
    path('', views.league_table, name='league_table'),
]