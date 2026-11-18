from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.matches.models import Season

from .models import PlayerSeasonStatistics


def index(request):
    return render(request, 'public/index.html')


def _requested_season(request):
    season_id = request.GET.get('season_id')
    if season_id:
        try:
            season_id = int(season_id)
        except ValueError as error:
            raise Http404 from error
        try:
            return Season.objects.get(pk=season_id)
        except Season.DoesNotExist as error:
            raise Http404 from error
    return (
        Season.objects.filter(is_active=True).first()
        or Season.objects.order_by('-year').first()
    )


@require_GET
def player_statistics(request):
    season = _requested_season(request)
    if season is None:
        return JsonResponse({'season': None, 'players': []})

    statistics = PlayerSeasonStatistics.objects.filter(
        season=season,
    ).select_related('player').order_by('-goals_scored', '-assists', 'player_id')
    return JsonResponse({
        'season': {'id': season.pk, 'name': season.name, 'year': season.year},
        'players': [
            {
                'player': {'id': row.player_id, 'name': str(row.player)},
                'appearances': row.appearances,
                'goals': row.goals_scored,
                'assists': row.assists,
                'clean_sheets': row.clean_sheets,
                'penalties_saved': row.penalties_saved,
                'yellow_cards': row.yellow_cards,
                'red_cards': row.red_cards,
                'own_goals': row.own_goals,
                'minutes_played': row.minutes_played,
                'player_of_the_match': row.player_of_the_match,
            }
            for row in statistics
        ],
    })
