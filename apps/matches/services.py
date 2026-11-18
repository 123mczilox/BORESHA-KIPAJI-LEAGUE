from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import (
    can_manage_match,
    is_league_admin,
)
from apps.players.models import Player
from apps.teams.models import Team

from .models import Match, MatchEvent, MatchOfficial, Season, SeasonTeam


EVENT_FIELDS = (
    'event_type',
    'player',
    'related_player',
    'minute',
    'added_time',
    'description',
)

ALLOWED_STATUS_TRANSITIONS = {
    Match.Status.SCHEDULED: {
        Match.Status.LIVE,
        Match.Status.POSTPONED,
        Match.Status.CANCELLED,
    },
    Match.Status.POSTPONED: {
        Match.Status.SCHEDULED,
        Match.Status.LIVE,
        Match.Status.CANCELLED,
    },
    Match.Status.LIVE: {
        Match.Status.COMPLETED,
        Match.Status.POSTPONED,
        Match.Status.CANCELLED,
    },
}


def _require_league_admin(user):
    if not is_league_admin(user):
        raise PermissionDenied('Only League Admins can perform this operation.')


def _require_match_operator(user, match):
    if not (is_league_admin(user) or can_manage_match(user, match)):
        raise PermissionDenied(
            'You are not authorized to manage this match.'
        )


def _rebuild_completed_match_intelligence(match):
    from apps.statistics.services import (
        _rebuild_completed_match_statistics,
    )
    from apps.standings.services import (
        _rebuild_completed_match_standings,
    )

    _rebuild_completed_match_statistics(match)
    _rebuild_completed_match_standings(match)


@transaction.atomic
def register_team_for_season(*, user, team_id, season_id):
    _require_league_admin(user)
    team = Team.objects.select_for_update().get(pk=team_id)
    season = Season.objects.select_for_update().get(pk=season_id)
    membership = SeasonTeam(season=season, team=team)
    membership.full_clean()
    membership.save()
    return membership


@transaction.atomic
def create_fixture(*, user, values):
    _require_league_admin(user)
    season_value = values.get('season', values.get('season_id'))
    season_id = (
        season_value.pk if hasattr(season_value, 'pk') else season_value
    )
    season = Season.objects.select_for_update().get(
        pk=season_id
    )
    home_value = values.get('home_team', values.get('home_team_id'))
    away_value = values.get('away_team', values.get('away_team_id'))
    home_team_id = home_value.pk if hasattr(home_value, 'pk') else home_value
    away_team_id = away_value.pk if hasattr(away_value, 'pk') else away_value
    team_ids = sorted({home_team_id, away_team_id})
    teams = {
        team.pk: team
        for team in Team.objects.select_for_update()
        .filter(pk__in=team_ids)
        .order_by('pk')
    }

    match = Match(
        season=season,
        home_team=teams.get(home_team_id),
        away_team=teams.get(away_team_id),
        matchweek=values.get('matchweek'),
        kickoff_time=values['kickoff_time'],
        venue=values.get('venue', ''),
    )
    if None in (match.home_team, match.away_team):
        raise Team.DoesNotExist

    list(SeasonTeam.objects.select_for_update().filter(
        season=season,
        team_id__in=team_ids,
    ))
    match.full_clean()
    match.save()
    return match


@transaction.atomic
def update_fixture(*, user, match_id, values):
    _require_league_admin(user)
    match = Match.objects.select_for_update().get(pk=match_id)
    if (
        match.started_at is not None
        or match.status not in (Match.Status.SCHEDULED, Match.Status.POSTPONED)
    ):
        raise ValidationError(
            'Fixture details cannot be changed after a match has started.'
        )

    if 'season' in values or 'season_id' in values:
        season_id = (
            values['season'].pk if hasattr(values.get('season'), 'pk')
            else values.get('season_id')
        )
        match.season = Season.objects.select_for_update().get(pk=season_id)

    team_ids = []
    for field in ('home_team', 'away_team'):
        supplied = values.get(field, values.get(f'{field}_id'))
        if supplied is not None:
            team_ids.append(supplied.pk if hasattr(supplied, 'pk') else supplied)
        else:
            team_ids.append(getattr(match, f'{field}_id'))

    teams = {
        team.pk: team
        for team in Team.objects.select_for_update()
        .filter(pk__in=set(team_ids))
        .order_by('pk')
    }
    if any(team_id not in teams for team_id in team_ids):
        raise Team.DoesNotExist
    match.home_team = teams[team_ids[0]]
    match.away_team = teams[team_ids[1]]

    for field in ('matchweek', 'kickoff_time', 'venue'):
        if field in values:
            setattr(match, field, values[field])

    list(SeasonTeam.objects.select_for_update().filter(
        season=match.season,
        team_id__in=team_ids,
    ))
    match.full_clean()
    match.save()
    return match


@transaction.atomic
def assign_match_official(*, user, match_id, official_user_id, role):
    _require_league_admin(user)
    match = Match.objects.select_for_update().get(pk=match_id)
    if match.started_at is not None or match.status in (
        Match.Status.COMPLETED,
        Match.Status.CANCELLED,
    ):
        raise ValidationError(
            'Officials cannot be assigned after a match has started.'
        )
    User = get_user_model()
    official_user = User.objects.select_for_update().get(pk=official_user_id)
    assignment = MatchOfficial(
        match=match,
        user=official_user,
        role=role,
    )
    assignment.full_clean()
    assignment.save()
    return assignment


@transaction.atomic
def remove_match_official(*, user, assignment_id):
    _require_league_admin(user)
    assignment = MatchOfficial.objects.select_for_update().get(
        pk=assignment_id
    )
    match = Match.objects.select_for_update().get(pk=assignment.match_id)
    if match.started_at is not None:
        raise ValidationError(
            'Officials cannot be removed after a match has started.'
        )
    assignment.delete()


def _recalculate_match_score(match):
    home_score = 0
    away_score = 0
    scoring_types = {
        MatchEvent.EventType.GOAL,
        MatchEvent.EventType.PENALTY_GOAL,
        MatchEvent.EventType.OWN_GOAL,
    }

    for event in match.events.filter(event_type__in=scoring_types).select_related(
        'player'
    ):
        player_teams = event.team_for_player(event.player_id)
        if len(player_teams) != 1:
            raise ValidationError(
                'Scoring events require a player registered to one match team.'
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

    match.home_score = home_score
    match.away_score = away_score
    match.save(update_fields=['home_score', 'away_score', 'updated_at'])
    return home_score, away_score


@transaction.atomic
def transition_match(*, user, match_id, status, home_score=None, away_score=None):
    match = Match.objects.select_for_update().get(pk=match_id)
    _require_match_operator(user, match)
    if (
        home_score is not None
        and (type(home_score) is not int or home_score < 0)
    ) or (
        away_score is not None
        and (type(away_score) is not int or away_score < 0)
    ):
        raise ValidationError('Scores must be non-negative integers.')

    allowed = ALLOWED_STATUS_TRANSITIONS.get(match.status, set())
    if status not in allowed:
        raise ValidationError(
            f'Match cannot transition from {match.status} to {status}.'
        )
    if status == Match.Status.SCHEDULED and match.started_at is not None:
        raise ValidationError(
            'A match that has started cannot return to scheduled status.'
        )

    if status == Match.Status.COMPLETED:
        calculated_home, calculated_away = _recalculate_match_score(match)
        if (home_score is None) != (away_score is None):
            raise ValidationError(
                'Both submitted scores must be provided together.'
            )
        if (
            home_score is not None
            and away_score is not None
            and (home_score, away_score) != (calculated_home, calculated_away)
        ):
            raise ValidationError(
                'Submitted result does not match the recorded scoring events.'
            )
        match.home_score = calculated_home
        match.away_score = calculated_away
    elif home_score is not None or away_score is not None:
        raise ValidationError(
            'Scores are set from match events when the match is completed.'
        )

    match.status = status
    if status == Match.Status.LIVE and match.started_at is None:
        match.started_at = timezone.now()
    match.full_clean()
    match.save(update_fields=[
        'status',
        'started_at',
        'home_score',
        'away_score',
        'updated_at',
    ])
    if status == Match.Status.COMPLETED:
        _rebuild_completed_match_intelligence(match)
    return match


def _save_match_event(*, user, match, event, values):
    if match.status == Match.Status.LIVE:
        _require_match_operator(user, match)
    elif (
        match.status == Match.Status.COMPLETED
        and is_league_admin(user)
    ):
        pass
    elif match.status == Match.Status.COMPLETED:
        raise PermissionDenied(
            'Only League Admins can correct events after match completion.'
        )
    else:
        raise ValidationError(
            'Events can only be changed for live or completed matches.'
        )

    player_ids = {
        event.player_id,
        event.related_player_id,
        getattr(values.get('player'), 'pk', values.get('player_id')),
        getattr(
            values.get('related_player'),
            'pk',
            values.get('related_player_id'),
        ),
    }
    player_ids.discard(None)
    list(
        Player.objects.select_for_update()
        .filter(pk__in=player_ids)
        .order_by('pk')
    )

    for field in EVENT_FIELDS:
        if field in values:
            setattr(event, field, values[field])
    event.match = match
    event.full_clean()
    event.save()
    _recalculate_match_score(match)
    if match.status == Match.Status.COMPLETED:
        match.full_clean()
        match.save(update_fields=['home_score', 'away_score', 'updated_at'])
        _rebuild_completed_match_intelligence(match)
    return event


@transaction.atomic
def create_match_event(*, user, match_id, values):
    match = Match.objects.select_for_update().get(pk=match_id)
    event = MatchEvent(match=match)
    return _save_match_event(
        user=user,
        match=match,
        event=event,
        values=values,
    )


@transaction.atomic
def update_match_event(*, user, event_id, values):
    event = MatchEvent.objects.select_for_update().get(pk=event_id)
    match = Match.objects.select_for_update().get(pk=event.match_id)
    return _save_match_event(
        user=user,
        match=match,
        event=event,
        values=values,
    )


@transaction.atomic
def delete_match_event(*, user, event_id):
    _require_league_admin(user)
    event = MatchEvent.objects.select_for_update().get(pk=event_id)
    match = Match.objects.select_for_update().get(pk=event.match_id)
    if match.status not in (
        Match.Status.LIVE,
        Match.Status.COMPLETED,
    ):
        raise ValidationError(
            'Events can only be deleted for live or completed matches.'
        )
    event.delete()
    _recalculate_match_score(match)
    if match.status == Match.Status.COMPLETED:
        match.full_clean()
        match.save(update_fields=['home_score', 'away_score', 'updated_at'])
        _rebuild_completed_match_intelligence(match)
