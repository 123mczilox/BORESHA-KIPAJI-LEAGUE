from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.permissions import (
    is_content_manager,
    is_fantasy_manager,
    is_league_admin,
    is_match_official,
    is_super_admin,
    is_team_manager,
)
from apps.matches.models import Match, MatchEvent, Season, SeasonTeam
from apps.news.models import NewsArticle
from apps.players.models import Player, PlayerRegistration
from apps.fantasy.models import (
    FantasyGameWeek,
    FantasyGameweekScore,
    FantasyPlayerSelection,
    FantasyTeam,
)
from apps.sponsors.models import Sponsor
from apps.standings.models import TeamStandings
from apps.statistics.models import PlayerMatchPerformance
from apps.teams.models import Team, TeamManagerAssignment


DASHBOARD_ROLES = {
    'super_admin': {
        'title': 'Super Admin Dashboard',
        'group': None,
        'template': 'dashboards/super_admin/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('League Administration', '▤', False),
            ('Users & Roles', '♙', False),
            ('System Settings', '⚙', False),
        ),
    },
    'league_admin': {
        'title': 'League Admin Dashboard',
        'group': 'League Admin',
        'template': 'dashboards/league_admin/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('Teams', '◆', False),
            ('Players', '♟', False),
            ('Seasons', '◷', False),
            ('Matches', '◉', False),
            ('Standings', '▥', False),
            ('Statistics', '▤', False),
            ('News', '▣', False),
            ('Sponsors', '◇', False),
            ('Opportunities', '↗', False),
        ),
    },
    'team_manager': {
        'title': 'Team Manager Dashboard',
        'group': 'Team Manager',
        'template': 'dashboards/team_manager/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('My Team', '◆', False),
            ('Players', '♟', False),
            ('Registrations', '▤', False),
            ('Matches', '◉', False),
            ('Statistics', '▥', False),
        ),
    },
    'match_official': {
        'title': 'Match Official Dashboard',
        'group': 'Match Official',
        'template': 'dashboards/match_official/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('Assignments', '◉', False),
            ('Match Events', '⚑', False),
            ('Player Performance', '▤', False),
        ),
    },
    'fantasy': {
        'title': 'Fantasy Manager Dashboard',
        'group': 'Fantasy Manager',
        'template': 'dashboards/fantasy/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('Fantasy Teams', '◆', False),
            ('Gameweeks', '◷', False),
            ('Player Selections', '♟', False),
            ('Transfers', '⇄', False),
            ('Scores', '▤', False),
        ),
    },
    'content_manager': {
        'title': 'Content Manager Dashboard',
        'group': 'Content Manager',
        'template': 'dashboards/content_manager/dashboard.html',
        'navigation': (
            ('Overview', '⌂', True),
            ('News & Articles', '▣', False),
            ('Sponsors', '◇', False),
            ('Opportunities', '↗', False),
        ),
    },
}

ROLE_SLUGS = {
    role['group']: slug
    for slug, role in DASHBOARD_ROLES.items()
    if role['group'] is not None
}


def _assigned_dashboard_slugs(user):
    if is_super_admin(user):
        return ['super_admin']

    assigned_roles = list(
        user.groups.filter(name__in=ROLE_SLUGS).values_list('name', flat=True)
    )
    return [ROLE_SLUGS[role_name] for role_name in assigned_roles]


def _safe_reverse(view_name, kwargs=None):
    try:
        return reverse(view_name, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _active_season():
    return (
        Season.objects.filter(is_active=True).first()
        or Season.objects.order_by('-year').first()
    )


def _navigation_context(role_slug, user=None):
    role = DASHBOARD_ROLES[role_slug]
    links = {
        'league_admin': {
            'Teams': _safe_reverse('teams:team_list'),
            'Players': _safe_reverse('players:player_list'),
            'Seasons': _safe_reverse('admin:matches_season_changelist'),
            'Matches': _safe_reverse('matches:match_list_create'),
            'Standings': _safe_reverse('standings:league_table'),
            'Statistics': _safe_reverse('statistics:player_statistics'),
            'News': _safe_reverse('admin:news_newsarticle_changelist'),
            'Sponsors': _safe_reverse('admin:sponsors_sponsor_changelist'),
            'Opportunities': _safe_reverse('admin:opportunities_opportunity_changelist'),
        },
        'team_manager': {
            'My Team': None,
            'Players': _safe_reverse('players:player_list'),
            'Registrations': _safe_reverse('players:registration_create'),
            'Matches': _safe_reverse('matches:match_list_create'),
            'Statistics': _safe_reverse('statistics:player_statistics'),
        },
        'match_official': {
            'Assignments': _safe_reverse('matches:match_list_create'),
            'Match Events': _safe_reverse('matches:match_list_create'),
            'Player Performance': _safe_reverse('matches:match_list_create'),
        },
        'fantasy': {
            'Fantasy Teams': _safe_reverse('admin:fantasy_fantasyteam_changelist'),
            'Gameweeks': _safe_reverse('admin:fantasy_fantasygameweek_changelist'),
            'Player Selections': _safe_reverse('admin:fantasy_fantasyplayerselection_changelist'),
            'Transfers': _safe_reverse('admin:fantasy_fantasytransfer_changelist'),
            'Scores': _safe_reverse('admin:fantasy_fantasygameweekscore_changelist'),
        },
        'content_manager': {
            'News & Articles': _safe_reverse('admin:news_newsarticle_changelist'),
            'Sponsors': _safe_reverse('admin:sponsors_sponsor_changelist'),
            'Opportunities': _safe_reverse('admin:opportunities_opportunity_changelist'),
        },
        'super_admin': {
            'League Administration': _safe_reverse('admin:index'),
            'Users & Roles': _safe_reverse('admin:auth_user_changelist'),
            'System Settings': _safe_reverse('admin:index'),
        },
    }.get(role_slug, {})
    if role_slug == 'team_manager' and user is not None:
        assignment = TeamManagerAssignment.objects.filter(
            user=user,
            is_active=True,
        ).select_related('team').first()
        if assignment:
            links['My Team'] = _safe_reverse(
                'teams:team_detail',
                kwargs={'pk': assignment.team_id},
            )

    navigation = [
        {
            'label': label,
            'icon': icon,
            'url': links.get(label) if enabled is False else (
                links.get(label) or reverse('role_dashboard', kwargs={'role_slug': role_slug})
            ),
            'active': enabled,
        }
        for label, icon, enabled in role['navigation']
    ]
    return navigation


def _super_admin_context(request):
    User = get_user_model()
    upcoming = Match.objects.filter(
        status__in=(Match.Status.SCHEDULED, Match.Status.POSTPONED),
        kickoff_time__gte=timezone.now(),
    ).select_related('season', 'home_team', 'away_team').order_by('kickoff_time')
    recent = Match.objects.filter(status=Match.Status.COMPLETED).select_related(
        'season', 'home_team', 'away_team'
    ).order_by('-kickoff_time')[:5]

    role_counts = []
    role_labels = (
        ('Super Admin', 'Super Admin'),
        ('League Admin', 'League Admin'),
        ('Team Manager', 'Team Manager'),
        ('Match Official', 'Match Official'),
        ('Fantasy Manager', 'Fantasy Manager'),
        ('Content Manager', 'Content Manager'),
    )
    counted_users = set()
    for label, group_name in role_labels:
        if group_name == 'Super Admin':
            count = User.objects.filter(is_superuser=True).count()
            counted_users.update(
                User.objects.filter(is_superuser=True).values_list('pk', flat=True)
            )
        else:
            role_users = User.objects.filter(groups__name=group_name).distinct()
            count = role_users.count()
            counted_users.update(role_users.values_list('pk', flat=True))
        if count:
            role_counts.append({'label': label, 'count': count})

    unassigned_count = User.objects.exclude(pk__in=counted_users).count()
    if unassigned_count:
        role_counts.append({'label': 'Unassigned', 'count': unassigned_count})

    activity_items = []
    for registration in PlayerRegistration.objects.select_related(
        'player', 'team'
    ).order_by('-created_at')[:4]:
        activity_items.append({
            'title': 'Player registration',
            'description': (
                f'{registration.player} registered to {registration.team}'
            ),
            'created_at': registration.created_at,
        })
    for match in Match.objects.select_related(
        'home_team', 'away_team'
    ).order_by('-updated_at')[:4]:
        activity_items.append({
            'title': f'Match {match.get_status_display()}',
            'description': f'{match.home_team} vs {match.away_team}',
            'created_at': match.updated_at,
        })
    for article in NewsArticle.objects.order_by('-updated_at')[:4]:
        activity_items.append({
            'title': f'Article {article.get_status_display()}',
            'description': article.title,
            'created_at': article.updated_at,
        })
    activity_items.sort(
        key=lambda item: item['created_at'],
        reverse=True,
    )

    return {
        'total_users': User.objects.count(),
        'total_teams': Team.objects.count(),
        'total_players': Player.objects.count(),
        'active_seasons': Season.objects.filter(is_active=True).count(),
        'total_matches': Match.objects.count(),
        'upcoming_matches_count': upcoming.count(),
        'user_role_counts': role_counts,
        'upcoming_fixtures': upcoming[:5],
        'recent_results': recent,
        'recent_activities': activity_items[:8],
        'fixtures_url': _safe_reverse('matches:match_list_create'),
        'users_url': _safe_reverse('admin:auth_user_changelist'),
        'results_url': _safe_reverse('matches:match_list_create'),
        'quick_actions': [
            {'title': 'Manage Users', 'description': 'Review accounts and role assignments',
             'icon': '♙', 'url': _safe_reverse('admin:auth_user_changelist')},
            {'title': 'Manage Teams', 'description': 'Review league teams',
             'icon': '◆', 'url': _safe_reverse('teams:team_list')},
            {'title': 'Manage Matches', 'description': 'Create and update fixtures',
             'icon': '◉', 'url': _safe_reverse('matches:match_list_create')},
            {'title': 'Platform Admin', 'description': 'Open Django administration',
             'icon': '⚙', 'url': _safe_reverse('admin:index')},
        ],
    }


def _league_admin_context(request):
    season = _active_season()
    upcoming = Match.objects.filter(
        status=Match.Status.SCHEDULED,
        kickoff_time__gte=timezone.now(),
    ).select_related('season', 'home_team', 'away_team').order_by('kickoff_time')
    completed = Match.objects.filter(status=Match.Status.COMPLETED)
    recent = completed.select_related(
        'season', 'home_team', 'away_team'
    ).order_by('-kickoff_time')[:5]

    standings = []
    if season:
        memberships = SeasonTeam.objects.filter(season=season).select_related('team')
        standing_rows = {
            row.team_id: row
            for row in TeamStandings.objects.filter(session=season).select_related('team')
        }
        for membership in memberships:
            row = standing_rows.get(membership.team_id)
            standings.append({
                'team': membership.team,
                'played': getattr(row, 'played', 0),
                'won': getattr(row, 'won', 0),
                'drawn': getattr(row, 'drawn', 0),
                'lost': getattr(row, 'lost', 0),
                'goal_difference': getattr(row, 'goal_difference', 0),
                'points': getattr(row, 'points', 0),
            })
        standings.sort(key=lambda row: (-row['points'], -row['goal_difference'], row['team'].name))

    return {
        'total_teams': Team.objects.count(),
        'total_players': Player.objects.count(),
        'active_seasons': Season.objects.filter(is_active=True).count(),
        'total_matches': Match.objects.count(),
        'upcoming_matches_count': upcoming.count(),
        'completed_matches_count': completed.count(),
        'upcoming_fixtures': upcoming[:5],
        'standings_preview': standings[:8],
        'recent_results': recent,
        'recent_registrations': PlayerRegistration.objects.select_related(
            'player', 'team', 'season'
        ).order_by('-created_at')[:5],
        'fixtures_url': _safe_reverse('matches:match_list_create'),
        'standings_url': _safe_reverse('standings:league_table'),
        'results_url': _safe_reverse('matches:match_list_create'),
        'registrations_url': _safe_reverse('players:registration_create'),
        'quick_actions': [
            {'title': 'Manage Teams', 'description': 'Create or update league teams',
             'icon': '◆', 'url': _safe_reverse('teams:team_list')},
            {'title': 'Manage Players', 'description': 'Register players and transfers',
             'icon': '♟', 'url': _safe_reverse('players:player_list')},
            {'title': 'Create Fixture', 'description': 'Schedule a league match',
             'icon': '◉', 'url': _safe_reverse('matches:match_list_create')},
            {'title': 'League Standings', 'description': 'Review the league table',
             'icon': '▥', 'url': _safe_reverse('standings:league_table')},
        ],
    }


def _team_manager_context(request):
    today = timezone.localdate()
    assignments = TeamManagerAssignment.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related('team')
    managed_team = assignments.first().team if assignments.exists() else None

    registrations = PlayerRegistration.objects.filter(
        team=managed_team,
    ).select_related('player', 'team', 'season') if managed_team else (
        PlayerRegistration.objects.none()
    )
    active_registrations = registrations.filter(
        start_date__lte=today,
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
    )
    team_players = Player.objects.filter(
        pk__in=active_registrations.values('player_id')
    ).distinct()

    season = _active_season()
    team_matches = Match.objects.none()
    upcoming = Match.objects.none()
    recent = Match.objects.none()
    matches_played = matches_won = matches_drawn = matches_lost = 0
    goals_scored = goals_conceded = league_points = 0

    if managed_team:
        team_matches = Match.objects.filter(
            models.Q(home_team=managed_team) | models.Q(away_team=managed_team)
        )
        if season:
            team_matches = team_matches.filter(season=season)
        upcoming = team_matches.filter(
            status=Match.Status.SCHEDULED,
            kickoff_time__gte=timezone.now(),
        ).select_related('season', 'home_team', 'away_team').order_by('kickoff_time')
        recent = team_matches.filter(
            status=Match.Status.COMPLETED,
        ).select_related('season', 'home_team', 'away_team').order_by('-kickoff_time')[:5]
        completed = team_matches.filter(status=Match.Status.COMPLETED)
        matches_played = completed.count()

        standing = (
            TeamStandings.objects.filter(session=season, team=managed_team).first()
            if season else None
        )
        if standing:
            matches_won = standing.won
            matches_drawn = standing.drawn
            matches_lost = standing.lost
            goals_scored = standing.goals_for
            goals_conceded = standing.goals_against
            league_points = standing.points
        else:
            for match in completed:
                if match.home_team_id == managed_team.pk:
                    team_goals = match.home_score or 0
                    opponent_goals = match.away_score or 0
                else:
                    team_goals = match.away_score or 0
                    opponent_goals = match.home_score or 0
                goals_scored += team_goals
                goals_conceded += opponent_goals
                if team_goals > opponent_goals:
                    matches_won += 1
                    league_points += 3
                elif team_goals == opponent_goals:
                    matches_drawn += 1
                    league_points += 1
                else:
                    matches_lost += 1

    team_edit_url = (
        _safe_reverse('teams:team_update', kwargs={'pk': managed_team.pk})
        if managed_team else None
    )
    team_detail_url = (
        _safe_reverse('teams:team_detail', kwargs={'pk': managed_team.pk})
        if managed_team else None
    )
    team_players_url = _safe_reverse('players:player_list')
    quick_actions = [
        {'title': 'View My Team', 'description': 'Open your team profile',
         'icon': '◆', 'url': team_detail_url},
        {'title': 'Edit Team', 'description': 'Update permitted team details',
         'icon': '✎', 'url': team_edit_url},
        {'title': 'View Players', 'description': 'Review your squad',
         'icon': '♟', 'url': team_players_url},
        {'title': 'Register Player', 'description': 'Create or register a player',
         'icon': '＋', 'url': _safe_reverse('players:player_create')},
        {'title': 'Team Matches', 'description': 'Review fixtures and results',
         'icon': '◉', 'url': _safe_reverse('matches:match_list_create')},
    ]
    quick_actions = [action for action in quick_actions if action['url']]

    return {
        'managed_team': managed_team,
        'total_players': team_players.count(),
        'active_players': team_players.filter(is_active=True).count(),
        'upcoming_matches_count': upcoming.count(),
        'matches_played': matches_played,
        'matches_won': matches_won,
        'matches_drawn': matches_drawn,
        'matches_lost': matches_lost,
        'goals_scored': goals_scored,
        'goals_conceded': goals_conceded,
        'league_points': league_points,
        'pending_registrations': 0,
        'upcoming_matches': upcoming[:5],
        'team_players': team_players.select_related().order_by(
            'last_name', 'first_name'
        )[:8],
        'recent_results': recent,
        'matches_url': _safe_reverse('matches:match_list_create'),
        'players_url': team_players_url,
        'quick_actions': quick_actions,
    }


def _match_official_context(request):
    assignments = Match.objects.filter(
        officials__user=request.user
    ).select_related(
        'season', 'home_team', 'away_team'
    ).distinct()
    assigned_matches = assignments.order_by('kickoff_time')
    upcoming = assigned_matches.filter(
        status__in=(Match.Status.SCHEDULED, Match.Status.LIVE),
        kickoff_time__gte=timezone.now(),
    )
    completed = assigned_matches.filter(status=Match.Status.COMPLETED)
    recent = completed.order_by('-kickoff_time')[:5]
    pending_reports = assigned_matches.filter(status=Match.Status.LIVE).count()

    event_items = []
    for event in MatchEvent.objects.filter(
        match__in=assigned_matches
    ).select_related(
        'match', 'player', 'related_player'
    ).order_by('-created_at')[:8]:
        event_items.append({
            'title': event.get_event_type_display(),
            'description': (
                f'{event.player} - {event.match} '
                f'(minute {event.minute}{("+" + str(event.added_time)) if event.added_time else ""})'
            ),
            'created_at': event.created_at,
        })

    quick_actions = [
        {'title': 'Assigned Matches', 'description': 'Review your match assignments',
         'icon': '◉', 'url': _safe_reverse('matches:match_list_create')},
        {'title': 'Match Events', 'description': 'Open match event management',
         'icon': '⚑', 'url': _safe_reverse('matches:match_list_create')},
        {'title': 'Player Performance', 'description': 'Review match performance tools',
         'icon': '▤', 'url': _safe_reverse('statistics:player_statistics')},
    ]
    quick_actions = [action for action in quick_actions if action['url']]

    return {
        'assigned_matches_count': assigned_matches.count(),
        'upcoming_matches_count': upcoming.count(),
        'completed_matches_count': completed.count(),
        'pending_reports_count': pending_reports,
        'assigned_matches': assigned_matches[:8],
        'recent_matches': recent,
        'recent_match_events': event_items,
        'matches_url': _safe_reverse('matches:match_list_create'),
        'quick_actions': quick_actions,
    }


def _fantasy_context(request):
    active_gameweeks = FantasyGameWeek.objects.filter(
        is_current=True,
        is_finished=False,
    ).select_related('season').order_by('number')
    season = _active_season()
    fantasy_teams = FantasyTeam.objects.select_related(
        'manager', 'season'
    )
    if season:
        fantasy_teams = fantasy_teams.filter(season=season)

    competitions = []
    for gameweek in active_gameweeks[:6]:
        competitions.append({
            'name': gameweek.name or f'Game Week {gameweek.number}',
            'description': f'{gameweek.season.name} fantasy competition',
            'status': 'active',
            'participant_count': FantasyTeam.objects.filter(
                season=gameweek.season
            ).values('manager_id').distinct().count(),
        })

    leaderboard = [
        {
            'participant_name': team.manager.get_full_name() or team.manager.username,
            'team_name': team.name,
            'points': team.total_points,
        }
        for team in fantasy_teams.order_by('-total_points', 'name')[:10]
    ]

    recent_selections = []
    for selection in FantasyPlayerSelection.objects.filter(
        fantasy_team__in=fantasy_teams
    ).select_related(
        'player', 'fantasy_team', 'fantasy_team__manager'
    ).order_by('-selected_at')[:8]:
        recent_selections.append({
            'player_name': str(selection.player),
            'participant_name': (
                selection.fantasy_team.manager.get_full_name()
                or selection.fantasy_team.manager.username
            ),
            'created_at': selection.selected_at,
        })

    recent_points = [
        {
            'participant_name': (
                score.fantasy_team.manager.get_full_name()
                or score.fantasy_team.manager.username
            ),
            'description': (
                f'{score.fantasy_team.name} - '
                f'Game Week {score.gameweek.number}'
            ),
            'points': score.points_earned,
            'created_at': score.updated_at,
        }
        for score in FantasyGameweekScore.objects.filter(
            fantasy_team__in=fantasy_teams
        ).select_related(
            'fantasy_team', 'gameweek'
        ).order_by('-updated_at')[:8]
    ]

    quick_actions = [
        {'title': 'Fantasy Teams', 'description': 'Review fantasy team records',
         'icon': '◆', 'url': _safe_reverse('admin:fantasy_fantasyteam_changelist')},
        {'title': 'Game Weeks', 'description': 'Review fantasy game weeks',
         'icon': '◷', 'url': _safe_reverse('admin:fantasy_fantasygameweek_changelist')},
        {'title': 'Player Selections', 'description': 'Review player selections',
         'icon': '♟', 'url': _safe_reverse('admin:fantasy_fantasyplayerselection_changelist')},
        {'title': 'Transfers', 'description': 'Review fantasy transfers',
         'icon': '⇄', 'url': _safe_reverse('admin:fantasy_fantasytransfer_changelist')},
    ]
    quick_actions = [action for action in quick_actions if action['url']]

    return {
        'total_participants': fantasy_teams.values('manager_id').distinct().count(),
        'active_competitions': active_gameweeks.count(),
        'total_player_selections': FantasyPlayerSelection.objects.filter(
            fantasy_team__in=fantasy_teams
        ).count(),
        'total_fantasy_points': sum(team.total_points for team in fantasy_teams),
        'competitions': competitions,
        'leaderboard': leaderboard,
        'recent_selections': recent_selections,
        'recent_points': recent_points,
        'competitions_url': _safe_reverse('admin:fantasy_fantasygameweek_changelist'),
        'leaderboard_url': _safe_reverse('admin:fantasy_fantasyteam_changelist'),
        'selections_url': _safe_reverse('admin:fantasy_fantasyplayerselection_changelist'),
        'quick_actions': quick_actions,
    }


def _content_manager_context(request):
    articles = NewsArticle.objects.all()
    recent_articles = articles.select_related(
        'category', 'author'
    ).order_by('-updated_at')[:8]
    activity_items = [
        {
            'title': f'Article {article.get_status_display()}',
            'description': article.title,
            'created_at': article.updated_at,
        }
        for article in recent_articles
    ]

    quick_actions = [
        {'title': 'News & Articles', 'description': 'Create and publish league articles',
         'icon': '▣', 'url': _safe_reverse('admin:news_newsarticle_changelist')},
        {'title': 'Sponsors', 'description': 'Manage sponsor information',
         'icon': '◇', 'url': _safe_reverse('admin:sponsors_sponsor_changelist')},
        {'title': 'Opportunities', 'description': 'Manage opportunities and announcements',
         'icon': '↗', 'url': _safe_reverse('admin:opportunities_opportunity_changelist')},
    ]
    quick_actions = [action for action in quick_actions if action['url']]

    return {
        'total_articles': articles.count(),
        'published_articles': articles.filter(
            status=NewsArticle.Status.PUBLISHED
        ).count(),
        'draft_articles': articles.filter(
            status=NewsArticle.Status.DRAFT
        ).count(),
        'pending_articles': 0,
        'total_announcements': 0,
        'recent_articles': recent_articles,
        'recent_announcements': [],
        'recent_activities': activity_items,
        'articles_url': _safe_reverse('admin:news_newsarticle_changelist'),
        'announcements_url': None,
        'quick_actions': quick_actions,
    }
def _render_dashboard(request, role_slug):
    role = DASHBOARD_ROLES[role_slug]
    context_builders = {
        'super_admin': _super_admin_context,
        'league_admin': _league_admin_context,
        'team_manager': _team_manager_context,
        'match_official': _match_official_context,
        'fantasy': _fantasy_context,
        'content_manager': _content_manager_context,
    }
    context = context_builders[role_slug](request)
    context.update({
        'dashboard_heading': role['title'],
        'dashboard_role': role_slug,
        'dashboard_navigation': _navigation_context(role_slug, request.user),
    })
    return render(request, role['template'], context)


@login_required(login_url='login')
@require_GET
def dashboard_entry(request):
    assigned_slugs = _assigned_dashboard_slugs(request.user)
    if len(assigned_slugs) != 1:
        raise PermissionDenied

    return redirect('role_dashboard', role_slug=assigned_slugs[0])


@login_required(login_url='login')
@require_GET
def role_dashboard(request, role_slug):
    role = DASHBOARD_ROLES.get(role_slug)
    if role is None:
        raise PermissionDenied

    assigned_slugs = _assigned_dashboard_slugs(request.user)
    if len(assigned_slugs) != 1 or assigned_slugs[0] != role_slug:
        raise PermissionDenied

    return _render_dashboard(request, role_slug)
