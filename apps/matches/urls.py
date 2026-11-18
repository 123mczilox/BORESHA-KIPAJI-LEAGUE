from django.urls import path

from . import views


app_name = 'matches'

urlpatterns = [
    path('', views.match_list_create, name='match_list_create'),
    path('<int:match_id>/', views.match_detail, name='match_detail'),
    path(
        '<int:match_id>/lifecycle/',
        views.match_lifecycle,
        name='match_lifecycle',
    ),
    path(
        '<int:match_id>/officials/',
        views.match_officials,
        name='match_officials',
    ),
    path(
        'officials/<int:assignment_id>/',
        views.match_official_remove,
        name='match_official_remove',
    ),
    path(
        '<int:match_id>/events/',
        views.match_events,
        name='match_events',
    ),
    path(
        'events/<int:event_id>/',
        views.match_event_detail,
        name='match_event_detail',
    ),
]
