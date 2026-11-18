from functools import wraps

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect


USER_GROUPS = {
    'League Admin': {
        'teams.Team': ('view', 'add', 'change', 'delete'),
        'teams.TeamManagerAssignment': ('view', 'add', 'change', 'delete'),
        'players.Player': ('view', 'add', 'change', 'delete'),
        'players.PlayerRegistration': ('view', 'add', 'change', 'delete'),
        'matches.Season': ('view', 'add', 'change', 'delete'),
        'matches.SeasonTeam': ('view', 'add', 'change', 'delete'),
        'matches.Match': ('view', 'add', 'change', 'delete'),
        'matches.MatchOfficial': ('view', 'add', 'change', 'delete'),
        'matches.MatchEvent': ('view', 'add', 'change', 'delete'),
        'standings.TeamStandings': ('view', 'change'),
        'statistics.PlayerMatchPerformance': (
            'view', 'add', 'change', 'delete'
        ),
        'statistics.PlayerSeasonStatistics': ('view',),
        'fantasy.FantasyTeam': ('view', 'add', 'change', 'delete'),
        'fantasy.FantasyPlayerSelection': (
            'view', 'add', 'change', 'delete'
        ),
        'fantasy.FantasyGameWeek': ('view', 'add', 'change', 'delete'),
        'fantasy.FantasyGameweekMatch': ('view', 'add', 'change', 'delete'),
        'fantasy.PlayerFantasyValue': ('view', 'add', 'change', 'delete'),
        'fantasy.FantasyTransfer': ('view', 'add', 'change', 'delete'),
        'fantasy.FantasyScoringRule': ('view', 'add', 'change', 'delete'),
        'fantasy.PlayerGameweekScore': ('view', 'add', 'change', 'delete'),
        'fantasy.FantasyGameweekScore': ('view', 'add', 'change', 'delete'),
        'news.NewsCategory': ('view', 'add', 'change', 'delete'),
        'news.NewsArticle': ('view', 'add', 'change', 'delete'),
        'sponsors.Sponsor': ('view', 'add', 'change', 'delete'),
        'opportunities.Opportunity': ('view', 'add', 'change', 'delete'),
    },
    'Match Official': {
        'players.Player': ('view',),
        'players.PlayerRegistration': ('view',),
        'matches.Season': ('view',),
        'matches.Match': ('view', 'change'),
        'matches.MatchOfficial': ('view',),
        'matches.MatchEvent': ('view', 'add', 'change'),
        'statistics.PlayerMatchPerformance': ('view', 'add', 'change'),
        'statistics.PlayerSeasonStatistics': ('view',),
    },
    'Team Manager': {
        'teams.Team': ('view', 'change'),
        'players.Player': ('view',),
        'players.PlayerRegistration': ('view', 'add', 'change'),
        'matches.Season': ('view',),
        'matches.Match': ('view',),
        'statistics.PlayerMatchPerformance': ('view',),
        'statistics.PlayerSeasonStatistics': ('view',),
    },
    'Fantasy Manager': {
        'fantasy.FantasyTeam': ('view', 'add', 'change'),
        'fantasy.FantasyPlayerSelection': (
            'view', 'add', 'change', 'delete'
        ),
        'fantasy.FantasyGameWeek': ('view',),
        'fantasy.FantasyGameweekMatch': ('view',),
        'fantasy.PlayerFantasyValue': ('view',),
        'fantasy.FantasyTransfer': ('view',),
        'fantasy.FantasyScoringRule': ('view',),
        'fantasy.PlayerGameweekScore': ('view',),
        'fantasy.FantasyGameweekScore': ('view',),
    },
    'Content Manager': {
        'news.NewsCategory': ('view', 'add', 'change', 'delete'),
        'news.NewsArticle': ('view', 'add', 'change', 'delete'),
        'sponsors.Sponsor': ('view', 'add', 'change', 'delete'),
        'opportunities.Opportunity': ('view', 'add', 'change', 'delete'),
    },
}


def create_user_groups():
    """Create role groups and replace their direct permissions with policy."""
    for group_name, model_permissions in USER_GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permission_ids = []

        for model_label, actions in model_permissions.items():
            app_label, model_name = model_label.split('.')
            codenames = [
                f'{action}_{model_name.lower()}'
                for action in actions
            ]
            permission_ids.extend(
                Permission.objects.filter(
                    content_type__app_label=app_label,
                    content_type__model=model_name.lower(),
                    codename__in=codenames,
                ).values_list('pk', flat=True)
            )

        group.permissions.set(permission_ids)


def is_super_admin(user):
    return bool(user.is_authenticated and user.is_superuser)


def has_role(user, role_name):
    """Superusers bypass role checks; ordinary users need the named group."""
    if not user.is_authenticated:
        return False

    return is_super_admin(user) or user.groups.filter(name=role_name).exists()


def is_league_admin(user):
    return has_role(user, 'League Admin')


def is_match_official(user):
    return has_role(user, 'Match Official')


def is_team_manager(user):
    return has_role(user, 'Team Manager')


def is_fantasy_manager(user):
    return has_role(user, 'Fantasy Manager')


def is_content_manager(user):
    return has_role(user, 'Content Manager')


def role_required(role_name):
    """Restrict a view to an authenticated member of the named role."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not has_role(request.user, role_name):
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def can_manage_team(user, team):
    if not user.is_authenticated:
        return False

    if is_league_admin(user):
        return True

    return is_team_manager(user) and team.manager_assignments.filter(
        user=user,
        is_active=True,
    ).exists()


def can_manage_match(user, match):
    if not user.is_authenticated:
        return False

    if is_league_admin(user):
        return True

    return is_match_official(user) and match.officials.filter(
        user=user,
    ).exists()


def can_view_match(user, match):
    if not user.is_authenticated:
        return False

    if is_league_admin(user) or can_manage_match(user, match):
        return True

    if is_team_manager(user):
        return (
            can_manage_team(user, match.home_team)
            or can_manage_team(user, match.away_team)
        )

    return False


def can_manage_fantasy_team(user, fantasy_team):
    if not user.is_authenticated:
        return False

    if is_league_admin(user):
        return True

    return (
        is_fantasy_manager(user)
        and fantasy_team.manager_id == user.pk
    )


def visible_players_for_user(user):
    """Return player records visible to a league role, scoped by assignment."""
    from django.db.models import F, Q
    from django.utils import timezone

    from apps.players.models import Player

    players = Player.objects.all()
    if is_league_admin(user):
        return players

    if is_team_manager(user):
        today = timezone.localdate()
        return players.filter(
            Q(registrations__end_date__isnull=True)
            | Q(registrations__end_date__gte=today),
            registrations__team__manager_assignments__user=user,
            registrations__team__manager_assignments__is_active=True,
            registrations__start_date__lte=today,
        ).distinct()

    if is_match_official(user):
        return players.filter(
            Q(
                registrations__team__home_matches__officials__user=user,
                registrations__season=F(
                    'registrations__team__home_matches__season'
                ),
            )
            | Q(
                registrations__team__away_matches__officials__user=user,
                registrations__season=F(
                    'registrations__team__away_matches__season'
                ),
            )
        ).distinct()

    return players.none()


def can_view_player(user, player):
    return (
        user.is_authenticated
        and visible_players_for_user(user).filter(pk=player.pk).exists()
    )


def can_manage_player(user, player):
    if not user.is_authenticated:
        return False

    if is_league_admin(user):
        return True

    if not is_team_manager(user):
        return False

    from django.db.models import Q
    from django.utils import timezone

    today = timezone.localdate()
    return player.registrations.filter(
        team__manager_assignments__user=user,
        team__manager_assignments__is_active=True,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True)
        | Q(end_date__gte=today)
    ).exists()


def can_manage_registration(user, registration):
    if not user.is_authenticated:
        return False

    if is_league_admin(user):
        return True

    if not is_team_manager(user):
        return False

    from django.utils import timezone

    today = timezone.localdate()
    return (
        registration.start_date <= today
        and (registration.end_date is None or registration.end_date >= today)
        and registration.team.manager_assignments.filter(
            user=user,
            is_active=True,
        ).exists()
    )


def visible_registrations_for_user(user):
    from django.db.models import F, Q
    from django.utils import timezone

    from apps.players.models import PlayerRegistration

    registrations = PlayerRegistration.objects.select_related(
        'player',
        'team',
        'season',
    )
    if is_league_admin(user):
        return registrations

    if is_team_manager(user):
        today = timezone.localdate()
        return registrations.filter(
            team__manager_assignments__user=user,
            team__manager_assignments__is_active=True,
            start_date__lte=today,
        ).filter(
            Q(end_date__isnull=True)
            | Q(end_date__gte=today)
        ).distinct()

    if is_match_official(user):
        return registrations.filter(
            Q(
                team__home_matches__officials__user=user,
                team__home_matches__season=F('season'),
            )
            | Q(
                team__away_matches__officials__user=user,
                team__away_matches__season=F('season'),
            )
        ).distinct()

    return registrations.none()


def can_view_registration(user, registration):
    if not user.is_authenticated:
        return False

    return visible_registrations_for_user(user).filter(
        pk=registration.pk
    ).exists()


def team_access_required(team_id_kwarg='team_id'):
    """Restrict a view to administrators and assigned team managers."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            from apps.teams.models import Team

            team_id = kwargs.get(team_id_kwarg)
            if team_id is None:
                raise ValueError(f'Missing URL parameter: {team_id_kwarg}')

            team = get_object_or_404(Team, pk=team_id)
            if not can_manage_team(request.user, team):
                raise PermissionDenied

            request.team = team
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def match_access_required(match_id_kwarg='match_id'):
    """Restrict a view to league administrators or assigned match officials."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            from apps.matches.models import Match

            match_id = kwargs.get(match_id_kwarg)
            if match_id is None:
                raise ValueError(f'Missing URL parameter: {match_id_kwarg}')

            match = get_object_or_404(Match, pk=match_id)
            if not can_manage_match(request.user, match):
                raise PermissionDenied

            request.match = match
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def fantasy_team_access_required(team_id_kwarg='fantasy_team_id'):
    """Restrict a view to league admins or the fantasy team's owner."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            from apps.fantasy.models import FantasyTeam

            team_id = kwargs.get(team_id_kwarg)
            if team_id is None:
                raise ValueError(f'Missing URL parameter: {team_id_kwarg}')

            fantasy_team = get_object_or_404(FantasyTeam, pk=team_id)
            if not can_manage_fantasy_team(request.user, fantasy_team):
                raise PermissionDenied

            request.fantasy_team = fantasy_team
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
