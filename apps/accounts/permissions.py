from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
USER_GROUPS = {
    'League Admin': {
        'teams': ['view', 'add', 'change', 'delete'],
        'players': ['view', 'add', 'change', 'delete'],
        'matches': ['view', 'add', 'change', 'delete'],
        'standings': ['view', 'change'],
        'statistics': ['view', 'add', 'change'],
        'news': ['view', 'add', 'change', 'delete'],
        'opportunities': ['view', 'add', 'change', 'delete'],
        'sponsors': ['view', 'add', 'change', 'delete'],
    },

    'Match Official': {
        'matches': ['view', 'add', 'change'],
        'players': ['view'],
        'teams': ['view'],
        'statistics': ['view', 'add', 'change'],
    },

    'Team Manager': {
        'teams': ['view', 'change'],
        'players': ['view', 'add', 'change'],
        'matches': ['view'],
        'statistics': ['view'],
    },

    'Fantasy Manager': {
        'fantasy': ['view', 'add', 'change'],
    },

    'Content Manager': {
        'news': ['view', 'add', 'change', 'delete'],
        'opportunities': ['view', 'add', 'change', 'delete'],
        'sponsors': ['view', 'add', 'change', 'delete'],
    },
}


def create_user_groups():

    for group_name, app_permissions in USER_GROUPS.items():

        group, created = Group.objects.get_or_create(
            name=group_name
        )

        for app_label, actions in app_permissions.items():

            content_types = ContentType.objects.filter(
                app_label=app_label
            )

            for content_type in content_types:

                permissions = Permission.objects.filter(
                    content_type=content_type,
                    codename__in=[
                        f'{action}_{content_type.model}'
                        for action in actions
                    ]
                )

                group.permissions.add(*permissions)
# check if user has a specific role
def has_role(user, role_name):
    """
    Check whether a user belongs to a particular role group.
    Superusers have access to all roles.
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user.groups.filter(name=role_name).exists()


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

            #decorator to check if user has a specific role
def role_required(role_name):
    """
    Restrict access to users belonging to a specific role.
    Superusers can access every protected view.
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # Redirect visitors who haven't logged in.
            if not request.user.is_authenticated:
                return redirect('login')

            # Check whether the user has the required role.
            if not has_role(request.user, role_name):
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator              

def can_manage_team(user, team):

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if is_league_admin(user):
        return True

    if not is_team_manager(user):
        return False

    return team.manager_assignments.filter(
        user=user,
        is_active=True
    ).exists()
    
def team_access_required(team_id_kwarg='team_id'):
    """
    Restrict access to a team based on the user's assignment.
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('login')

            from apps.teams.models import Team

            team_id = kwargs.get(team_id_kwarg)

            if team_id is None:
                raise ValueError(
                    f'Missing URL parameter: {team_id_kwarg}'
                )

            team = get_object_or_404(
                Team,
                pk=team_id
            )

            if not can_manage_team(request.user, team):
                raise PermissionDenied

            request.team = team

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator    