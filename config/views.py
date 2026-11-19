from django.db import DatabaseError
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.matches.models import Match, Season, SeasonTeam
from apps.news.models import NewsArticle
from apps.players.models import Player, PlayerRegistration
from apps.sponsors.models import Sponsor
from apps.standings.models import TeamStandings
from apps.teams.models import Team


@require_GET
def home(request):
    try:
        return _home(request)
    except DatabaseError:
        return render(request, 'public/home.html', {
            'participating_team_count': 0,
            'registered_player_count': 0,
            'matches_played_count': 0,
            'season_count': 0,
            'upcoming_fixtures': [],
            'recent_results': [],
            'standings_preview': [],
            'latest_news': [],
            'active_sponsors': [],
        })


def _home(request):
    active_season = (
        Season.objects.filter(is_active=True).first()
        or Season.objects.order_by('-year').first()
    )

    season_matches = Match.objects.all()
    if active_season:
        season_matches = season_matches.filter(season=active_season)

    participating_team_count = (
        SeasonTeam.objects.filter(season=active_season).count()
        if active_season
        else Team.objects.filter(is_active=True).count()
    )

    if active_season:
        registered_player_count = (
            PlayerRegistration.objects.filter(
                season=active_season,
                end_date__isnull=True,
                player__is_active=True,
            )
            .values('player_id')
            .distinct()
            .count()
        )
    else:
        registered_player_count = Player.objects.filter(is_active=True).count()

    matches_played_count = season_matches.filter(
        status=Match.Status.COMPLETED,
    ).count()

    now = timezone.now()
    upcoming_fixtures = (
        season_matches.filter(
            status=Match.Status.SCHEDULED,
            kickoff_time__gte=now,
        )
        .select_related('season', 'home_team', 'away_team')
        .order_by('kickoff_time')[:3]
    )

    recent_results = (
        season_matches.filter(status=Match.Status.COMPLETED)
        .select_related('season', 'home_team', 'away_team')
        .order_by('-kickoff_time')[:4]
    )

    standings_preview = []
    if active_season:
        membership_team_ids = list(
            SeasonTeam.objects.filter(season=active_season)
            .values_list('team_id', flat=True)
        )
        standing_rows = {
            row.team_id: row
            for row in TeamStandings.objects.filter(
                session=active_season,
                team_id__in=membership_team_ids,
            ).select_related('team')
        }

        standings_preview = []
        for membership in (
            SeasonTeam.objects.filter(season=active_season)
            .select_related('team')
            .order_by('team__name')
        ):
            row = standing_rows.get(membership.team_id)
            standings_preview.append({
                'team': {'name': membership.team.name},
                'played': getattr(row, 'played', 0),
                'won': getattr(row, 'won', 0),
                'drawn': getattr(row, 'drawn', 0),
                'lost': getattr(row, 'lost', 0),
                'goal_difference': getattr(row, 'goal_difference', 0),
                'points': getattr(row, 'points', 0),
            })

        standings_preview.sort(
            key=lambda row: (
                -row['points'],
                -row['goal_difference'],
                row['team']['name'],
            )
        )
        standings_preview = standings_preview[:5]

    latest_news = (
        NewsArticle.objects.filter(
            status=NewsArticle.Status.PUBLISHED,
            published_at__isnull=False,
        )
        .select_related('category')
        .order_by('-published_at', '-created_at')[:3]
    )

    active_sponsors = (
        Sponsor.objects.filter(is_active=True)
        .order_by('display_order', 'name')
    )

    context = {
        'participating_team_count': participating_team_count,
        'registered_player_count': registered_player_count,
        'matches_played_count': matches_played_count,
        'season_count': Season.objects.count(),
        'upcoming_fixtures': upcoming_fixtures,
        'recent_results': recent_results,
        'standings_preview': standings_preview,
        'latest_news': latest_news,
        'active_sponsors': active_sponsors,
    }

    return render(request, 'public/home.html', context)
