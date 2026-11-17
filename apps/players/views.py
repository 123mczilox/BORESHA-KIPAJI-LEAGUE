from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import (
    can_manage_player,
    can_manage_team,
    can_view_player,
    is_league_admin,
    is_match_official,
    is_team_manager,
    visible_players_for_user,
    visible_registrations_for_user,
)

from .forms import (
    PlayerCreateForm,
    PlayerEditForm,
    PlayerRegistrationForm,
    PlayerTransferForm,
)
from .models import Player, PlayerRegistration
from .services import (
    create_player_with_registration,
    register_player,
    transfer_player,
    update_player,
)


def _show_validation_error(form, error):
    form.add_error(None, '; '.join(error.messages))


@login_required
def player_list(request):
    if not (
        is_league_admin(request.user)
        or is_team_manager(request.user)
        or is_match_official(request.user)
    ):
        raise PermissionDenied

    players = visible_players_for_user(request.user).select_related().distinct()
    return render(
        request,
        'players/player_list.html',
        {'players': players},
    )


@login_required
def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if not can_view_player(request.user, player):
        raise PermissionDenied

    registrations = visible_registrations_for_user(request.user).filter(
        player=player
    )
    return render(
        request,
        'players/player_detail.html',
        {
            'player': player,
            'registrations': registrations,
            'can_edit': can_manage_player(request.user, player),
        },
    )


@login_required
def player_create(request):
    if not (
        is_league_admin(request.user)
        or is_team_manager(request.user)
    ):
        raise PermissionDenied

    form = PlayerCreateForm(
        request.POST if request.method == 'POST' else None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        player = form.save(commit=False)
        try:
            player, _ = create_player_with_registration(
                user=request.user,
                player=player,
                team_id=form.cleaned_data['team'].pk,
                season_id=form.cleaned_data['season'].pk,
                start_date=form.cleaned_data['start_date'],
                shirt_number=form.cleaned_data['shirt_number'],
            )
        except ValidationError as error:
            _show_validation_error(form, error)
        else:
            messages.success(
                request,
                f'{player} was created and registered successfully.',
            )
            return redirect('players:player_detail', pk=player.pk)

    return render(
        request,
        'players/player_form.html',
        {
            'form': form,
            'player': None,
            'page_title': 'Register a player',
        },
    )


@login_required
def player_update(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if not can_manage_player(request.user, player):
        raise PermissionDenied

    form = PlayerEditForm(
        request.POST if request.method == 'POST' else None,
        instance=player,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            update_player(
                user=request.user,
                player_id=player.pk,
                values=form.cleaned_data,
            )
        except ValidationError as error:
            _show_validation_error(form, error)
        else:
            messages.success(request, f'{player} was updated successfully.')
            return redirect('players:player_detail', pk=player.pk)

    return render(
        request,
        'players/player_form.html',
        {
            'form': form,
            'player': player,
            'page_title': f'Edit {player}',
        },
    )


@login_required
def registration_create(request):
    if not (
        is_league_admin(request.user)
        or is_team_manager(request.user)
    ):
        raise PermissionDenied

    form = PlayerRegistrationForm(
        request.POST if request.method == 'POST' else None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            registration = register_player(
                user=request.user,
                player_id=form.cleaned_data['player'].pk,
                team_id=form.cleaned_data['team'].pk,
                season_id=form.cleaned_data['season'].pk,
                start_date=form.cleaned_data['start_date'],
                end_date=form.cleaned_data['end_date'],
                shirt_number=form.cleaned_data['shirt_number'],
            )
        except ValidationError as error:
            _show_validation_error(form, error)
        else:
            messages.success(
                request,
                f'{registration.player} was registered to '
                f'{registration.team}.',
            )
            return redirect(
                'players:registration_history',
                pk=registration.player_id,
            )

    return render(
        request,
        'players/registration_form.html',
        {
            'form': form,
            'page_title': 'Register a player to a team',
        },
    )


@login_required
def registration_history(request, pk):
    player = get_object_or_404(visible_players_for_user(request.user), pk=pk)
    registrations = visible_registrations_for_user(request.user).filter(
        player=player
    )
    return render(
        request,
        'players/registration_history.html',
        {
            'player': player,
            'registrations': registrations,
        },
    )


@login_required
def registration_transfer(request, registration_id):
    registration = get_object_or_404(
        visible_registrations_for_user(request.user),
        pk=registration_id,
    )
    if not registration.end_date and not can_manage_team(
        request.user,
        registration.team,
    ):
        raise PermissionDenied
    if registration.end_date:
        raise PermissionDenied('Only a current registration can be transferred.')

    form = PlayerTransferForm(
        request.POST if request.method == 'POST' else None,
        user=request.user,
        source_team=registration.team,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            new_registration = transfer_player(
                user=request.user,
                registration_id=registration.pk,
                target_team_id=form.cleaned_data['team'].pk,
                transfer_date=form.cleaned_data['transfer_date'],
                shirt_number=form.cleaned_data['shirt_number'],
            )
        except ValidationError as error:
            _show_validation_error(form, error)
        else:
            messages.success(
                request,
                f'{registration.player} was transferred to '
                f'{new_registration.team}.',
            )
            return redirect(
                'players:registration_history',
                pk=registration.player_id,
            )

    return render(
        request,
        'players/transfer_form.html',
        {
            'form': form,
            'registration': registration,
            'page_title': f'Transfer {registration.player}',
        },
    )
