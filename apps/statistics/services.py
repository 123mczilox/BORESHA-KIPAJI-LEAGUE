from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.permissions import can_manage_match, is_league_admin
from apps.matches.models import Match, MatchEvent, Season
from apps.players.models import Player, PlayerRegistration

from .models import PlayerMatchPerformance, PlayerSeasonStatistics


PERFORMANCE_INPUT_FIELDS = {
    'assists',
    'appeared',
    'clean_sheet',
    'minutes_played',
    'penalties_saved',
    'player_of_the_match',
}
DERIVED_PERFORMANCE_FIELDS = (
    'goals_scored',
    'yellow_cards',
    'red_cards',
    'own_goals',
)
SEASON_STAT_FIELDS = (
    'appearances',
    'goals_scored',
    'assists',
    'clean_sheets',
    'penalties_saved',
    'player_of_the_match',
    'yellow_cards',
    'red_cards',
    'own_goals',
    'minutes_played',
)


def _require_league_admin(user):
    if not is_league_admin(user):
        raise PermissionDenied(
            'Only League Admins can recalculate verified statistics.'
        )


def _event_stat_totals(match):
    totals = defaultdict(lambda: defaultdict(int))
    participants = set()
    home_score = 0
    away_score = 0
    event_fields = {
        MatchEvent.EventType.GOAL: 'goals_scored',
        MatchEvent.EventType.PENALTY_GOAL: 'goals_scored',
        MatchEvent.EventType.OWN_GOAL: 'own_goals',
        MatchEvent.EventType.YELLOW_CARD: 'yellow_cards',
        MatchEvent.EventType.RED_CARD: 'red_cards',
    }

    events = match.events.select_related(
        'player',
        'related_player',
    ).order_by('pk')
    for event in events:
        event.full_clean()
        participants.add(event.player_id)
        if event.related_player_id:
            participants.add(event.related_player_id)
        field = event_fields.get(event.event_type)
        if field:
            totals[event.player_id][field] += 1
        if event.event_type in (
            MatchEvent.EventType.GOAL,
            MatchEvent.EventType.PENALTY_GOAL,
            MatchEvent.EventType.OWN_GOAL,
        ):
            player_teams = event.team_for_player(event.player_id)
            if len(player_teams) != 1:
                raise ValidationError(
                    'Scoring events require a player registered to one '
                    'participating team.'
                )
            scoring_team_id = player_teams[0]
            if event.event_type == MatchEvent.EventType.OWN_GOAL:
                scoring_team_id = (
                    match.away_team_id
                    if scoring_team_id == match.home_team_id
                    else match.home_team_id
                )
            if scoring_team_id == match.home_team_id:
                home_score += 1
            else:
                away_score += 1

    if (home_score, away_score) != (match.home_score, match.away_score):
        raise ValidationError(
            'Completed match scores do not match the recorded scoring events.'
        )

    return totals, participants


def _lock_match_players(match):
    participant_ids = set(
        PlayerMatchPerformance.objects.filter(match=match)
        .values_list('player_id', flat=True)
    )
    for player_id, related_player_id in match.events.values_list(
        'player_id',
        'related_player_id',
    ):
        participant_ids.add(player_id)
        if related_player_id:
            participant_ids.add(related_player_id)

    list(
        PlayerRegistration.objects.select_for_update()
        .filter(
            player_id__in=participant_ids,
            season_id=match.season_id,
            team_id__in=(match.home_team_id, match.away_team_id),
        )
        .order_by('pk')
    )
    list(
        Player.objects.select_for_update()
        .filter(pk__in=participant_ids)
        .order_by('pk')
    )


def _sync_completed_match_performances(match):
    if match.status != Match.Status.COMPLETED:
        raise ValidationError(
            'Player statistics can only be verified for completed matches.'
        )
    if match.home_score is None or match.away_score is None:
        raise ValidationError(
            'A completed match must have a verified result.'
        )

    _lock_match_players(match)
    event_totals, participants = _event_stat_totals(match)
    for player_id in participants:
        PlayerMatchPerformance.objects.get_or_create(
            match=match,
            player_id=player_id,
        )

    performances = PlayerMatchPerformance.objects.select_for_update().filter(
        match=match,
    ).order_by('pk')
    for performance in performances:
        performance.full_clean()
        event_stats = event_totals[performance.player_id]
        for field in DERIVED_PERFORMANCE_FIELDS:
            setattr(performance, field, event_stats[field])
        performance.save(update_fields=(
            *DERIVED_PERFORMANCE_FIELDS,
            'updated_at',
        ))


def _season_totals(season):
    totals = defaultdict(lambda: defaultdict(int))
    performances = PlayerMatchPerformance.objects.filter(
        match__season=season,
        match__status=Match.Status.COMPLETED,
    ).order_by('match_id', 'player_id')

    for performance in performances:
        player_totals = totals[performance.player_id]
        player_totals['appearances'] += int(performance.appeared)
        player_totals['goals_scored'] += performance.goals_scored
        player_totals['assists'] += performance.assists
        player_totals['clean_sheets'] += int(performance.clean_sheet)
        player_totals['penalties_saved'] += performance.penalties_saved
        player_totals['player_of_the_match'] += int(
            performance.player_of_the_match
        )
        player_totals['yellow_cards'] += performance.yellow_cards
        player_totals['red_cards'] += performance.red_cards
        player_totals['own_goals'] += performance.own_goals
        player_totals['minutes_played'] += performance.minutes_played
    return totals


def _rebuild_season_statistics(season):
    totals = _season_totals(season)
    existing = {
        item.player_id: item
        for item in PlayerSeasonStatistics.objects.select_for_update()
        .filter(season=season)
        .order_by('player_id')
    }
    for player_id in set(existing) | set(totals):
        statistics = existing.get(player_id)
        if statistics is None:
            statistics = PlayerSeasonStatistics(
                player_id=player_id,
                season=season,
            )
        for field in SEASON_STAT_FIELDS:
            setattr(statistics, field, totals[player_id][field])
        statistics.full_clean()
        statistics.save()


@transaction.atomic
def _rebuild_completed_match_statistics(match):
    if match.status != Match.Status.COMPLETED:
        raise ValidationError(
            'Player statistics can only be verified for completed matches.'
        )
    _lock_match_players(match)
    season = Season.objects.select_for_update().get(pk=match.season_id)
    _sync_completed_match_performances(match)
    _rebuild_season_statistics(season)
    return PlayerSeasonStatistics.objects.filter(season=season)


@transaction.atomic
def recalculate_completed_match_statistics(*, user, match_id):
    _require_league_admin(user)
    match = Match.objects.select_for_update().select_related(
        'season',
    ).get(pk=match_id)
    return _rebuild_completed_match_statistics(match)


@transaction.atomic
def recalculate_player_season_statistics(*, user, season_id):
    _require_league_admin(user)
    completed_matches = list(Match.objects.filter(
        season_id=season_id,
        status=Match.Status.COMPLETED,
    ).order_by('pk'))
    participant_ids = set()
    for match in completed_matches:
        participant_ids.update(
            PlayerMatchPerformance.objects.filter(match=match)
            .values_list('player_id', flat=True)
        )
        for player_id, related_player_id in match.events.values_list(
            'player_id',
            'related_player_id',
        ):
            participant_ids.add(player_id)
            if related_player_id:
                participant_ids.add(related_player_id)
    team_ids = {
        team_id
        for match in completed_matches
        for team_id in (match.home_team_id, match.away_team_id)
    }
    list(
        PlayerRegistration.objects.select_for_update()
        .filter(
            player_id__in=participant_ids,
            season_id=season_id,
            team_id__in=team_ids,
        )
        .order_by('pk')
    )
    list(
        Player.objects.select_for_update()
        .filter(pk__in=participant_ids)
        .order_by('pk')
    )
    season = Season.objects.select_for_update().get(pk=season_id)
    for match in completed_matches:
        _sync_completed_match_performances(match)
    _rebuild_season_statistics(season)
    return PlayerSeasonStatistics.objects.filter(season=season)


@transaction.atomic
def record_match_performance(*, user, match_id, player_id, values):
    match = Match.objects.select_for_update().get(pk=match_id)
    if not (
        is_league_admin(user)
        or can_manage_match(user, match)
    ):
        raise PermissionDenied(
            'Only an assigned Match Official or League Admin can record '
            'player performance.'
        )
    if match.status not in (Match.Status.LIVE, Match.Status.COMPLETED):
        raise ValidationError(
            'Player performance can only be recorded for a live or completed '
            'match.'
        )
    if (
        match.status == Match.Status.COMPLETED
        and not is_league_admin(user)
    ):
        raise PermissionDenied(
            'Only League Admins can correct completed match performance.'
        )
    list(
        PlayerRegistration.objects.select_for_update()
        .filter(
            player_id=player_id,
            season_id=match.season_id,
            team_id__in=(match.home_team_id, match.away_team_id),
        )
        .order_by('pk')
    )
    player = Player.objects.select_for_update().get(pk=player_id)
    unexpected = set(values) - PERFORMANCE_INPUT_FIELDS
    if unexpected:
        raise ValidationError(
            'Event-derived statistics cannot be entered directly.'
        )

    performance, _ = PlayerMatchPerformance.objects.get_or_create(
        match=match,
        player_id=player_id,
    )
    if {'appeared', 'minutes_played'} & set(values):
        appeared = values.get('appeared', performance.appeared)
        minutes_played = values.get(
            'minutes_played',
            performance.minutes_played,
        )
        if appeared != (minutes_played > 0):
            raise ValidationError(
                'An appearance requires positive minutes, and positive '
                'minutes require an appearance.'
            )
    if (
        values.get('clean_sheet', performance.clean_sheet)
        and not values.get('appeared', performance.appeared)
    ):
        raise ValidationError(
            'A clean sheet can only be recorded for a verified appearance.'
        )

    for field, value in values.items():
        setattr(performance, field, value)
    performance.full_clean()
    performance.save()

    if match.status == Match.Status.COMPLETED:
        recalculate_completed_match_statistics(
            user=user,
            match_id=match.pk,
        )
    return performance
