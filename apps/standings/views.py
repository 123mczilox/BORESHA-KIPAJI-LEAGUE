from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from apps.matches.models import Season, SeasonTeam

from .models import TeamStandings


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
def league_table(request):
	season = _requested_season(request)
	if season is None:
		return JsonResponse({'season': None, 'standings': []})

	memberships = SeasonTeam.objects.filter(
		season=season,
	).select_related('team').order_by('team_id')
	totals = {
		row.team_id: row
		for row in TeamStandings.objects.filter(session=season)
	}
	zero_totals = {
		'played': 0,
		'won': 0,
		'drawn': 0,
		'lost': 0,
		'goals_for': 0,
		'goals_against': 0,
		'goal_difference': 0,
		'points': 0,
	}
	standings = []
	for membership in memberships:
		row = totals.get(membership.team_id)
		values = {
			field: getattr(row, field) if row else value
			for field, value in zero_totals.items()
		}
		standings.append({
			'team': {
				'id': membership.team_id,
				'name': membership.team.name,
			},
			**values,
		})
	standings.sort(key=lambda row: row['points'], reverse=True)

	return JsonResponse({
		'season': {'id': season.pk, 'name': season.name, 'year': season.year},
		'standings': standings,
	})
