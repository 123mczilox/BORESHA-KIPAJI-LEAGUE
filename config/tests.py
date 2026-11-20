from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.fantasy.models import (
    FantasyGameWeek,
    FantasyPlayerSelection,
    FantasyTeam,
)
from apps.matches.models import Match, MatchOfficial, Season
from apps.news.models import NewsArticle, NewsCategory
from apps.players.models import Player, PlayerRegistration
from apps.teams.models import Team, TeamManagerAssignment

from config.dashboard_views import DASHBOARD_ROLES


User = get_user_model()


class DashboardRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_users = {}
        for role_slug, role in DASHBOARD_ROLES.items():
            username = role_slug
            user = User.objects.create_user(
                username=username,
                is_superuser=(role_slug == 'super_admin'),
            )
            if role['group']:
                group, _ = Group.objects.get_or_create(name=role['group'])
                user.groups.add(group)
            cls.role_users[role_slug] = user

        cls.unassigned_user = User.objects.create_user(
            username='unassigned',
        )
        cls.multi_role_user = User.objects.create_user(
            username='multi_role',
        )
        cls.multi_role_user.groups.add(
            Group.objects.get(name='Team Manager'),
            Group.objects.get(name='Content Manager'),
        )

    def test_dashboard_entry_requires_authentication(self):
        response = self.client.get(reverse('dashboard_entry'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard_entry')}",
        )

    def test_each_role_is_redirected_to_and_can_render_its_dashboard(self):
        for role_slug, user in self.role_users.items():
            with self.subTest(role=role_slug):
                self.client.force_login(user)
                response = self.client.get(reverse('dashboard_entry'))
                self.assertRedirects(
                    response,
                    reverse('role_dashboard', kwargs={'role_slug': role_slug}),
                )
                dashboard = self.client.get(
                    reverse('role_dashboard', kwargs={'role_slug': role_slug})
                )
                self.assertEqual(dashboard.status_code, 200)
                self.assertTemplateUsed(
                    dashboard,
                    DASHBOARD_ROLES[role_slug]['template'],
                )
                self.client.logout()

    def test_user_cannot_open_another_roles_dashboard(self):
        client = Client()
        client.raise_request_exception = False
        client.force_login(self.role_users['team_manager'])
        response = client.get(
            reverse('role_dashboard', kwargs={'role_slug': 'content_manager'})
        )
        self.assertEqual(response.status_code, 403)

    def test_dashboard_routes_reject_non_get_requests(self):
        self.client.force_login(self.role_users['team_manager'])
        response = self.client.post(reverse('dashboard_entry'))
        self.assertEqual(response.status_code, 405)

    def test_unassigned_user_is_denied_dashboard_entry(self):
        client = Client()
        client.raise_request_exception = False
        client.force_login(self.unassigned_user)
        response = client.get(reverse('dashboard_entry'))
        self.assertEqual(response.status_code, 403)

    def test_multi_role_user_is_denied_ambiguous_dashboard_entry(self):
        client = Client()
        client.raise_request_exception = False
        client.force_login(self.multi_role_user)
        response = client.get(reverse('dashboard_entry'))
        self.assertEqual(response.status_code, 403)

    def test_multi_role_user_cannot_choose_one_role_manually(self):
        client = Client()
        client.raise_request_exception = False
        client.force_login(self.multi_role_user)
        response = client.get(
            reverse('role_dashboard', kwargs={'role_slug': 'team_manager'})
        )
        self.assertEqual(response.status_code, 403)

    def test_team_manager_dashboard_is_scoped_to_assigned_team(self):
        team = Team.objects.create(name='Assigned Team', is_active=True)
        other_team = Team.objects.create(name='Other Team', is_active=True)
        TeamManagerAssignment.objects.create(
            user=self.role_users['team_manager'],
            team=team,
            is_active=True,
        )
        season = Season.objects.create(
            name='2026',
            year=2026,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() + timedelta(days=300),
            is_active=True,
        )
        assigned_player = Player.objects.create(
            first_name='Assigned',
            last_name='Player',
            date_of_birth=timezone.localdate() - timedelta(days=20 * 365),
            position='MID',
        )
        other_player = Player.objects.create(
            first_name='Other',
            last_name='Player',
            date_of_birth=timezone.localdate() - timedelta(days=19 * 365),
            position='FWD',
        )
        PlayerRegistration.objects.create(
            player=assigned_player,
            team=team,
            season=season,
            start_date=timezone.localdate() - timedelta(days=10),
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=other_team,
            season=season,
            start_date=timezone.localdate() - timedelta(days=10),
        )

        self.client.force_login(self.role_users['team_manager'])
        response = self.client.get(
            reverse('role_dashboard', kwargs={'role_slug': 'team_manager'})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['managed_team'], team)
        self.assertEqual(
            list(response.context['team_players']),
            [assigned_player],
        )
        self.assertNotIn(other_player, response.context['team_players'])

    def test_match_official_dashboard_only_contains_assigned_matches(self):
        season = Season.objects.create(
            name='Official Season',
            year=2026,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() + timedelta(days=300),
            is_active=True,
        )
        assigned_team = Team.objects.create(name='Official Home')
        other_team = Team.objects.create(name='Official Away')
        match = Match.objects.create(
            season=season,
            home_team=assigned_team,
            away_team=other_team,
            kickoff_time=timezone.now() + timedelta(days=2),
        )
        MatchOfficial.objects.create(
            match=match,
            user=self.role_users['match_official'],
            role=MatchOfficial.Role.REFEREE,
        )

        self.client.force_login(self.role_users['match_official'])
        response = self.client.get(
            reverse('role_dashboard', kwargs={'role_slug': 'match_official'})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['assigned_matches_count'], 1)
        self.assertEqual(list(response.context['assigned_matches']), [match])

    def test_fantasy_dashboard_reads_existing_fantasy_models(self):
        season = Season.objects.create(
            name='Fantasy Season',
            year=2026,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() + timedelta(days=300),
            is_active=True,
        )
        gameweek = FantasyGameWeek.objects.create(
            season=season,
            number=1,
            name='Opening Week',
            deadline=timezone.now() + timedelta(days=1),
            is_current=True,
        )
        fantasy_team = FantasyTeam.objects.create(
            manager=self.role_users['fantasy'],
            season=season,
            name='Fantasy Stars',
            budget_remaining='900.00',
            total_points=25,
        )

        self.client.force_login(self.role_users['fantasy'])
        response = self.client.get(
            reverse('role_dashboard', kwargs={'role_slug': 'fantasy'})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_competitions'], 1)
        self.assertEqual(response.context['total_participants'], 1)
        self.assertEqual(response.context['competitions'][0]['name'], 'Opening Week')
        self.assertEqual(response.context['leaderboard'][0]['team_name'], fantasy_team.name)

    def test_content_dashboard_reads_news_without_inventing_announcements(self):
        category = NewsCategory.objects.create(
            name='League News',
            slug='league-news',
        )
        NewsArticle.objects.create(
            title='Test Article',
            slug='test-article',
            category=category,
            author=self.role_users['content_manager'],
            content='Test content',
            status=NewsArticle.Status.DRAFT,
        )

        self.client.force_login(self.role_users['content_manager'])
        response = self.client.get(
            reverse(
                'role_dashboard',
                kwargs={'role_slug': 'content_manager'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_articles'], 1)
        self.assertEqual(response.context['draft_articles'], 1)
        self.assertEqual(response.context['total_announcements'], 0)
        self.assertEqual(response.context['recent_announcements'], [])
