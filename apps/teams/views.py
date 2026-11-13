from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import (
    can_manage_team,
    is_league_admin,
    role_required,
)

from .forms import TeamForm, TeamManagerForm
from .models import Team


def team_list(request):
    """
    Display the team directory.
    League Admins can also see inactive teams.
    """

    if request.user.is_authenticated and is_league_admin(request.user):
        teams = Team.objects.all()
    else:
        teams = Team.objects.filter(is_active=True)

    teams = teams.order_by('name')

    return render(
        request,
        'teams/team_list.html',
        {'teams': teams}
    )


def team_detail(request, pk):
    """
    Display an individual team's profile.
    Inactive teams are visible only to League Admins.
    """

    team = get_object_or_404(Team, pk=pk)

    if not team.is_active:
        if not (
            request.user.is_authenticated
            and is_league_admin(request.user)
        ):
            raise PermissionDenied

    return render(
        request,
        'teams/team_detail.html',
        {'team': team}
    )


@login_required
@role_required('League Admin')
def team_create(request):
    """
    Allow League Admins to register new teams.
    """

    if request.method == 'POST':
        form = TeamForm(request.POST)

        if form.is_valid():
            team = form.save()

            messages.success(
                request,
                f'{team.name} has been registered successfully.'
            )

            return redirect('teams:team_detail', pk=team.pk)

    else:
        form = TeamForm()

    return render(
        request,
        'teams/team_form.html',
        {
            'form': form,
            'page_title': 'Register a Team',
            'submit_label': 'Register Team',
        }
    )


@login_required
def team_update(request, pk):
    """
    League Admins can edit all team information.
    Team Managers can edit only their assigned teams
    and only the fields exposed by TeamManagerForm.
    """

    team = get_object_or_404(Team, pk=pk)

    if not can_manage_team(request.user, team):
        raise PermissionDenied

    if is_league_admin(request.user):
        form_class = TeamForm
    else:
        form_class = TeamManagerForm

    if request.method == 'POST':
        form = form_class(
            request.POST,
            instance=team
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                f'{team.name} has been updated successfully.'
            )

            return redirect('teams:team_detail', pk=team.pk)

    else:
        form = form_class(instance=team)

    return render(
        request,
        'teams/team_form.html',
        {
            'form': form,
            'team': team,
            'page_title': f'Edit {team.name}',
            'submit_label': 'Save Changes',
        }
    )


@login_required
@role_required('League Admin')
@require_POST
def team_toggle_status(request, pk):
    """
    Activate or deactivate a team.
    Only League Admins can perform this operation.
    """

    team = get_object_or_404(Team, pk=pk)

    team.is_active = not team.is_active
    team.save(update_fields=['is_active', 'updated_at'])

    status = 'activated' if team.is_active else 'deactivated'

    messages.success(
        request,
        f'{team.name} has been {status}.'
    )

    return redirect('teams:team_detail', pk=team.pk)