from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import (
    can_manage_player,
    can_manage_team,
    can_view_player,
    is_league_admin,
    is_team_manager,
)
from apps.matches.models import Season
from apps.teams.models import Team

from .models import Player, PlayerRegistration


@transaction.atomic
def create_player_with_registration(
    *,
    user,
    player,
    team_id,
    season_id,
    start_date,
    shirt_number=None,
):
    if player.pk is not None:
        raise ValueError('A new player instance is required.')

    team = Team.objects.select_for_update().get(pk=team_id)
    if not can_manage_team(user, team):
        raise PermissionDenied('You cannot manage this team.')

    season = Season.objects.select_for_update().get(pk=season_id)
    player.full_clean()
    player.save()

    registration = PlayerRegistration(
        player=player,
        team=team,
        season=season,
        start_date=start_date,
        shirt_number=shirt_number,
    )
    registration.full_clean()
    registration.save()
    return player, registration


@transaction.atomic
def update_player(*, user, player_id, values):
    player = Player.objects.select_for_update().get(pk=player_id)
    if not can_manage_player(user, player):
        raise PermissionDenied('You cannot manage this player.')

    for field in ('first_name', 'last_name', 'date_of_birth', 'position'):
        if field in values:
            setattr(player, field, values[field])

    player.full_clean()
    player.save()
    return player


@transaction.atomic
def register_player(
    *,
    user,
    player_id,
    team_id,
    season_id,
    start_date,
    shirt_number=None,
    end_date=None,
):
    player = Player.objects.select_for_update().get(pk=player_id)
    team = Team.objects.select_for_update().get(pk=team_id)
    if not can_manage_team(user, team):
        raise PermissionDenied('You cannot manage this team.')
    if (
        not is_league_admin(user)
        and (
            not is_team_manager(user)
            or not can_view_player(user, player)
        )
    ):
        raise PermissionDenied(
            'You cannot register a player outside your authorized scope.'
        )

    season = Season.objects.select_for_update().get(pk=season_id)
    registration = PlayerRegistration(
        player=player,
        team=team,
        season=season,
        start_date=start_date,
        end_date=end_date,
        shirt_number=shirt_number,
    )
    registration.full_clean()
    registration.save()
    return registration


@transaction.atomic
def transfer_player(
    *,
    user,
    registration_id,
    target_team_id,
    transfer_date=None,
    shirt_number=None,
):
    registration = PlayerRegistration.objects.select_for_update().get(
        pk=registration_id
    )
    player = Player.objects.select_for_update().get(pk=registration.player_id)
    transfer_date = transfer_date or timezone.localdate()

    if registration.end_date is not None:
        raise ValidationError('Only a current registration can be transferred.')
    if transfer_date <= registration.start_date:
        raise ValidationError(
            'The transfer date must be after the current registration start.'
        )

    target_team_id = int(target_team_id)
    team_ids = sorted({registration.team_id, target_team_id})
    locked_teams = {
        team.pk: team
        for team in Team.objects.select_for_update()
        .filter(pk__in=team_ids)
        .order_by('pk')
    }
    target_team = locked_teams.get(target_team_id)
    if target_team is None:
        raise Team.DoesNotExist
    season = Season.objects.select_for_update().get(
        pk=registration.season_id
    )

    if not is_league_admin(user) and (
        not is_team_manager(user)
        or not can_manage_team(user, registration.team)
        or not can_manage_team(user, target_team)
    ):
        raise PermissionDenied(
            'You must manage both teams to transfer this player.'
        )

    if transfer_date < season.start_date:
        raise ValidationError('Transfer date is before the season starts.')
    if transfer_date > season.end_date:
        raise ValidationError('Transfer date is after the season ends.')
    if transfer_date > timezone.localdate() and not is_league_admin(user):
        raise ValidationError(
            'Only a League Admin can schedule a future transfer.'
        )

    registration.end_date = transfer_date - timedelta(days=1)
    registration.full_clean()
    registration.save(update_fields=['end_date'])

    new_registration = PlayerRegistration(
        player=player,
        team=target_team,
        season=season,
        shirt_number=shirt_number,
        start_date=transfer_date,
    )
    new_registration.full_clean()
    new_registration.save()
    return new_registration
