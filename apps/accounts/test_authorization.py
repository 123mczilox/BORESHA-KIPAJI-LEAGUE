from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import (
    can_manage_fantasy_team,
    can_manage_match,
    create_user_groups,
    fantasy_team_access_required,
    is_super_admin,
    match_access_required,
    visible_players_for_user,
)
from apps.fantasy.admin import (
    FantasyPlayerSelectionInline,
)
from apps.fantasy.admin import FantasyTeamAdmin
from apps.fantasy.models import FantasyPlayerSelection, FantasyTeam
from apps.matches.admin import MatchAdmin
from apps.matches.models import Match, MatchOfficial, Season
from apps.players.models import Player, PlayerRegistration
from apps.sponsors.admin import SponsorAdmin
from apps.sponsors.models import Sponsor
from apps.teams.admin import TeamAdmin
from apps.teams.models import Team, TeamManagerAssignment


User = get_user_model()


class AuthorizationTestCase(TestCase):
    def setUp(self):
        create_user_groups()
        self.request_factory = RequestFactory()

    def create_role_user(self, username, role, *, is_staff=False):
        user = User.objects.create_user(
            username=username,
            password='StrongPass123!',
            is_staff=is_staff,
        )
        user.groups.add(Group.objects.get(name=role))
        return user

    def create_match(self, season, home_team, away_team):
        return Match.objects.create(
            season=season,
            home_team=home_team,
            away_team=away_team,
            kickoff_time=timezone.now(),
        )


class RolePermissionAssignmentTests(AuthorizationTestCase):
    def test_role_groups_receive_only_their_model_permissions(self):
        team_manager = Group.objects.get(name='Team Manager')
        match_official = Group.objects.get(name='Match Official')
        fantasy_manager = Group.objects.get(name='Fantasy Manager')
        content_manager = Group.objects.get(name='Content Manager')

        self.assertTrue(team_manager.permissions.filter(
            codename='change_team'
        ).exists())
        self.assertFalse(team_manager.permissions.filter(
            codename='delete_team'
        ).exists())
        self.assertFalse(team_manager.permissions.filter(
            codename='change_teammanagerassignment'
        ).exists())

        self.assertTrue(match_official.permissions.filter(
            codename='change_match'
        ).exists())
        self.assertFalse(match_official.permissions.filter(
            codename='add_match'
        ).exists())
        self.assertFalse(match_official.permissions.filter(
            codename='add_matchofficial'
        ).exists())

        self.assertTrue(fantasy_manager.permissions.filter(
            codename='change_fantasyteam'
        ).exists())
        self.assertFalse(fantasy_manager.permissions.filter(
            codename='change_fantasygameweek'
        ).exists())
        self.assertFalse(fantasy_manager.permissions.filter(
            codename='change_fantasytransfer'
        ).exists())

        self.assertTrue(content_manager.permissions.filter(
            codename='change_sponsor'
        ).exists())
        self.assertFalse(content_manager.permissions.filter(
            codename='add_team'
        ).exists())

    def test_group_creation_removes_stale_permissions(self):
        group = Group.objects.get(name='Team Manager')
        team_permission = group.permissions.model.objects.get(
            codename='delete_team'
        )
        group.permissions.add(team_permission)

        create_user_groups()

        self.assertFalse(group.permissions.filter(
            pk=team_permission.pk
        ).exists())

    def test_super_admin_is_a_django_superuser(self):
        user = User.objects.create_superuser(
            username='platform_admin',
            password='StrongPass123!',
        )

        self.assertTrue(is_super_admin(user))


class TeamAuthorizationTests(AuthorizationTestCase):
    def setUp(self):
        super().setUp()
        self.manager = self.create_role_user(
            'assigned_manager',
            'Team Manager',
            is_staff=True,
        )
        self.other_manager = self.create_role_user(
            'other_manager',
            'Team Manager',
            is_staff=True,
        )
        self.team = Team.objects.create(name='Nairobi Stars')
        self.other_team = Team.objects.create(name='Mombasa United')
        TeamManagerAssignment.objects.create(
            user=self.manager,
            team=self.team,
        )
        TeamManagerAssignment.objects.create(
            user=self.other_manager,
            team=self.other_team,
        )

    def test_manager_can_update_assigned_team_but_forged_fields_are_ignored(
        self,
    ):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('teams:team_update', args=[self.team.pk]),
            {
                'short_name': 'NST',
                'description': 'Updated by assigned manager',
                'name': 'Forged name',
                'county': 'Forged county',
                'founded_year': '2020',
                'is_active': 'off',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.team.refresh_from_db()
        self.assertEqual(self.team.short_name, 'NST')
        self.assertEqual(
            self.team.description,
            'Updated by assigned manager',
        )
        self.assertEqual(self.team.name, 'Nairobi Stars')
        self.assertEqual(self.team.county, '')
        self.assertIsNone(self.team.founded_year)
        self.assertTrue(self.team.is_active)

    def test_manager_cannot_modify_an_unassigned_team(self):
        self.client.force_login(self.manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse('teams:team_update', args=[self.other_team.pk]),
            {
                'short_name': 'HACKED',
                'description': 'Unauthorized',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.other_team.refresh_from_db()
        self.assertEqual(self.other_team.short_name, '')
        self.assertEqual(self.other_team.description, '')

    def test_anonymous_user_cannot_post_team_changes(self):
        response = self.client.post(
            reverse('teams:team_update', args=[self.team.pk]),
            {'short_name': 'ANON'},
        )

        self.assertEqual(response.status_code, 302)
        self.team.refresh_from_db()
        self.assertEqual(self.team.short_name, '')

    def test_manager_cannot_toggle_team_status(self):
        self.client.force_login(self.manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse('teams:team_toggle_status', args=[self.team.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.team.refresh_from_db()
        self.assertTrue(self.team.is_active)

    def test_team_admin_limits_manager_to_assigned_teams_and_fields(self):
        request = self.request_factory.get('/admin/teams/team/')
        request.user = self.manager
        model_admin = admin.site._registry[Team]

        self.assertEqual(
            list(model_admin.get_queryset(request)),
            [self.team],
        )
        self.assertEqual(
            model_admin.get_fields(request, self.team),
            ('short_name', 'description'),
        )
        self.assertTrue(model_admin.has_change_permission(
            request,
            self.team,
        ))
        self.assertFalse(model_admin.has_change_permission(
            request,
            self.other_team,
        ))
        self.assertFalse(model_admin.has_add_permission(request))

    def test_admin_post_cannot_change_another_teams_record(self):
        self.client.force_login(self.manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse('admin:teams_team_change', args=[self.other_team.pk]),
            {
                'short_name': 'FORGED',
                'description': 'Unauthorized',
                '_save': 'Save',
            },
        )

        self.assertNotEqual(response.status_code, 200)
        self.other_team.refresh_from_db()
        self.assertEqual(self.other_team.short_name, '')
        self.assertEqual(self.other_team.description, '')

    def test_league_admin_can_toggle_team_status(self):
        administrator = self.create_role_user(
            'league_admin',
            'League Admin',
        )
        self.client.force_login(administrator)

        response = self.client.post(
            reverse('teams:team_toggle_status', args=[self.team.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.team.refresh_from_db()
        self.assertFalse(self.team.is_active)


class MatchOfficialAuthorizationTests(AuthorizationTestCase):
    def setUp(self):
        super().setUp()
        self.official = self.create_role_user(
            'official',
            'Match Official',
            is_staff=True,
        )
        self.home = Team.objects.create(name='Home team')
        self.away = Team.objects.create(name='Away team')
        self.other_home = Team.objects.create(name='Other home')
        self.other_away = Team.objects.create(name='Other away')
        self.season = Season.objects.create(
            name='2026 Season',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.assigned_match = self.create_match(
            self.season,
            self.home,
            self.away,
        )
        self.unassigned_match = self.create_match(
            self.season,
            self.other_home,
            self.other_away,
        )
        MatchOfficial.objects.create(
            match=self.assigned_match,
            user=self.official,
            role=MatchOfficial.Role.REFEREE,
        )

    def test_official_can_manage_only_assigned_matches(self):
        request = self.request_factory.get('/admin/matches/match/')
        request.user = self.official
        model_admin = admin.site._registry[Match]

        self.assertTrue(can_manage_match(
            self.official,
            self.assigned_match,
        ))
        self.assertFalse(can_manage_match(
            self.official,
            self.unassigned_match,
        ))
        self.assertEqual(
            list(model_admin.get_queryset(request)),
            [self.assigned_match],
        )
        self.assertTrue(model_admin.has_change_permission(
            request,
            self.assigned_match,
        ))
        self.assertFalse(model_admin.has_change_permission(
            request,
            self.unassigned_match,
        ))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertTrue(
            set(model_admin.get_readonly_fields(
                request,
                self.assigned_match,
            )).issuperset({
                'season',
                'home_team',
                'away_team',
                'kickoff_time',
            })
        )
        change_form = model_admin.get_form(
            request,
            self.assigned_match,
        )
        self.assertIn('status', change_form.base_fields)
        self.assertNotIn('home_score', change_form.base_fields)
        self.assertNotIn('home_team', change_form.base_fields)

    def test_match_access_decorator_allows_assigned_match_only(self):
        @match_access_required()
        def protected_view(request, match_id):
            return request.match.pk

        request = self.request_factory.post('/')
        request.user = self.official
        self.assertEqual(
            protected_view(request, match_id=self.assigned_match.pk),
            self.assigned_match.pk,
        )

        with self.assertRaises(PermissionDenied):
            protected_view(request, match_id=self.unassigned_match.pk)

    def test_official_player_visibility_matches_assigned_fixture_teams(self):
        eligible_player = Player.objects.create(
            first_name='Eligible',
            last_name='Player',
            date_of_birth=date(2012, 1, 1),
            position=Player.Position.FORWARD,
        )
        unrelated_player = Player.objects.create(
            first_name='Unrelated',
            last_name='Player',
            date_of_birth=date(2012, 1, 1),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=eligible_player,
            team=self.home,
            season=self.season,
            start_date=self.season.start_date,
        )
        PlayerRegistration.objects.create(
            player=unrelated_player,
            team=self.other_home,
            season=self.season,
            start_date=self.season.start_date,
        )

        visible_ids = set(
            visible_players_for_user(self.official).values_list(
                'pk',
                flat=True,
            )
        )

        self.assertIn(eligible_player.pk, visible_ids)
        self.assertNotIn(unrelated_player.pk, visible_ids)

    def test_anonymous_user_is_redirected_by_match_decorator(self):
        @match_access_required()
        def protected_view(request, match_id):
            return request.match.pk

        request = self.request_factory.post('/')
        request.user = AnonymousUser()

        response = protected_view(request, match_id=self.assigned_match.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)


class FantasyManagerAuthorizationTests(AuthorizationTestCase):
    def setUp(self):
        super().setUp()
        self.manager = self.create_role_user(
            'fantasy_owner',
            'Fantasy Manager',
            is_staff=True,
        )
        self.other_manager = self.create_role_user(
            'other_fantasy_owner',
            'Fantasy Manager',
            is_staff=True,
        )
        self.season = Season.objects.create(
            name='Fantasy Season',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.other_season = Season.objects.create(
            name='Other Fantasy Season',
            year=2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )
        self.own_team = FantasyTeam.objects.create(
            manager=self.manager,
            season=self.season,
            name='My team',
        )
        self.other_team = FantasyTeam.objects.create(
            manager=self.other_manager,
            season=self.season,
            name='Their team',
        )

    def test_manager_can_access_only_their_fantasy_team(self):
        request = self.request_factory.get('/admin/fantasy/fantasyteam/')
        request.user = self.manager
        model_admin = admin.site._registry[FantasyTeam]

        self.assertTrue(can_manage_fantasy_team(
            self.manager,
            self.own_team,
        ))
        self.assertFalse(can_manage_fantasy_team(
            self.manager,
            self.other_team,
        ))
        self.assertEqual(
            list(model_admin.get_queryset(request)),
            [self.own_team],
        )
        self.assertTrue(model_admin.has_change_permission(
            request,
            self.own_team,
        ))
        self.assertFalse(model_admin.has_change_permission(
            request,
            self.other_team,
        ))
        self.assertEqual(
            model_admin.get_fields(request, self.own_team),
            ('season', 'name'),
        )
        self.assertIn(
            'season',
            model_admin.get_readonly_fields(request, self.own_team),
        )

    def test_admin_cannot_reassign_new_fantasy_team_by_forged_owner(self):
        request = self.request_factory.post('/admin/fantasy/fantasyteam/add/')
        request.user = self.manager
        model_admin = admin.site._registry[FantasyTeam]
        forged_team = FantasyTeam(
            manager=self.other_manager,
            season=self.other_season,
            name='Forged owner',
        )

        model_admin.save_model(request, forged_team, form=None, change=False)

        self.assertEqual(forged_team.manager_id, self.manager.pk)
        self.assertEqual(
            FantasyTeam.objects.get(pk=forged_team.pk).manager_id,
            self.manager.pk,
        )

    def test_fantasy_selection_inline_is_scoped_to_owning_team(self):
        inline = FantasyPlayerSelectionInline(
            FantasyPlayerSelection,
            admin.site,
        )
        request = self.request_factory.get('/')
        request.user = self.manager

        self.assertTrue(inline.has_change_permission(request, self.own_team))
        self.assertFalse(
            inline.has_change_permission(request, self.other_team)
        )

    def test_fantasy_team_access_decorator_denies_another_owner(self):
        @fantasy_team_access_required()
        def protected_view(request, fantasy_team_id):
            return request.fantasy_team.pk

        request = self.request_factory.post('/')
        request.user = self.manager

        self.assertEqual(
            protected_view(request, fantasy_team_id=self.own_team.pk),
            self.own_team.pk,
        )
        with self.assertRaises(PermissionDenied):
            protected_view(request, fantasy_team_id=self.other_team.pk)

    def test_anonymous_user_is_redirected_by_fantasy_team_decorator(self):
        @fantasy_team_access_required()
        def protected_view(request, fantasy_team_id):
            return request.fantasy_team.pk

        request = self.request_factory.post('/')
        request.user = AnonymousUser()

        response = protected_view(
            request,
            fantasy_team_id=self.own_team.pk,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)


class ContentManagerAuthorizationTests(AuthorizationTestCase):
    def test_content_manager_has_content_but_not_league_permissions(self):
        manager = self.create_role_user(
            'content_manager',
            'Content Manager',
            is_staff=True,
        )
        request = self.request_factory.get('/admin/')
        request.user = manager

        sponsor_admin = SponsorAdmin(Sponsor, admin.site)
        team_admin = TeamAdmin(Team, admin.site)

        self.assertTrue(sponsor_admin.has_add_permission(request))
        self.assertFalse(team_admin.has_add_permission(request))
        self.assertFalse(team_admin.has_change_permission(request))
