from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.permissions import is_league_admin
from apps.matches.models import Match, Season, SeasonTeam

from .models import TeamStandings


WIN_POINTS = 3
DRAW_POINTS = 1
STANDING_FIELDS = (
    'played',
    'won',
    'drawn',
    'lost',
    'goals_for',
    'goals_against',
    'goal_difference',
    'points',
)


def _require_league_admin(user):
    if not is_league_admin(user):
        raise PermissionDenied(
            'Only League Admins can recalculate league standings.'
        )


def _calculate_season_standings(season):
    memberships = list(
        SeasonTeam.objects.filter(season=season)
        .select_related('team')
        .order_by('team_id')
    )
    team_ids = {membership.team_id for membership in memberships}
    totals = defaultdict(lambda: {
        'played': 0,
        'won': 0,
        'drawn': 0,
        'lost': 0,
        'goals_for': 0,
        'goals_against': 0,
        'goal_difference': 0,
        'points': 0,
    })

    matches = Match.objects.filter(
        season=season,
        status=Match.Status.COMPLETED,
    ).order_by('pk')
    for match in matches:
        if match.home_score is None or match.away_score is None:
            raise ValidationError(
                f'Completed match {match.pk} has no complete result.'
            )
        if (
            match.home_team_id not in team_ids
            or match.away_team_id not in team_ids
        ):
            raise ValidationError(
                f'Completed match {match.pk} contains a team not registered '
                'for its season.'
            )

        home = totals[match.home_team_id]
        away = totals[match.away_team_id]
        home['played'] += 1
        away['played'] += 1
        home['goals_for'] += match.home_score
        home['goals_against'] += match.away_score
        away['goals_for'] += match.away_score
        away['goals_against'] += match.home_score

        if match.home_score > match.away_score:
            home['won'] += 1
            home['points'] += WIN_POINTS
            away['lost'] += 1
        elif match.home_score < match.away_score:
            away['won'] += 1
            away['points'] += WIN_POINTS
            home['lost'] += 1
        else:
            home['drawn'] += 1
            away['drawn'] += 1
            home['points'] += DRAW_POINTS
            away['points'] += DRAW_POINTS

    for values in totals.values():
        values['goal_difference'] = (
            values['goals_for'] - values['goals_against']
        )

    existing = {
        standing.team_id: standing
        for standing in TeamStandings.objects.select_for_update()
        .filter(session=season)
        .order_by('team_id')
    }
    for team_id in team_ids | set(existing):
        standing = existing.get(team_id)
        if standing is None:
            if team_id not in team_ids:
                continue
            standing = TeamStandings(session=season, team_id=team_id)
        values = (
            totals[team_id]
            if team_id in team_ids
            else dict.fromkeys(STANDING_FIELDS, 0)
        )
        for field, value in values.items():
            setattr(standing, field, value)
        standing.full_clean()
        standing.save()


@transaction.atomic
def recalculate_season_standings(*, user, season_id):
    _require_league_admin(user)
    season = Season.objects.select_for_update().get(pk=season_id)
    _calculate_season_standings(season)
    return TeamStandings.objects.filter(session=season).order_by('-points')


@transaction.atomic
def _rebuild_completed_match_standings(match):
    if match.status != Match.Status.COMPLETED:
        raise ValidationError(
            'Standings can only be recalculated from completed matches.'
        )
    season = Season.objects.select_for_update().get(pk=match.season_id)
    _calculate_season_standings(season)
    return TeamStandings.objects.filter(session=season).order_by('-points')


@transaction.atomic
def recalculate_completed_match_standings(*, user, match_id):
    _require_league_admin(user)
    match = Match.objects.select_for_update().get(pk=match_id)
    return _rebuild_completed_match_standings(match)
