from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import (
    can_manage_player,
    can_view_player,
    create_user_groups,
    visible_registrations_for_user,
)
from apps.matches.models import Match, Season
from apps.statistics.models import PlayerMatchPerformance
from apps.teams.models import Team, TeamManagerAssignment

from .admin import PlayerRegistrationAdmin, PlayerRegistrationInline
from .forms import PlayerCreateForm, PlayerRegistrationForm
from .models import Player, PlayerRegistration
from .services import (
    create_player_with_registration,
    register_player,
    transfer_player,
    update_player,
)


User = get_user_model()

PLAYER_TEST_TEMPLATES = {
    'players/player_list.html': '{{ players|length }}',
    'players/player_detail.html': '{{ player.first_name }}',
    'players/player_form.html': '{{ form.errors }}',
    'players/registration_form.html': '{{ form.errors }}',
    'players/registration_history.html': '{{ registrations|length }}',
    'players/transfer_form.html': '{{ form.errors }}',
}

TEST_TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': False,
        'OPTIONS': {
            'loaders': [
                (
                    'django.template.loaders.locmem.Loader',
                    PLAYER_TEST_TEMPLATES,
                ),
            ],
        },
    },
]


@override_settings(TEMPLATES=TEST_TEMPLATES)
class PlayerWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_user_groups()

        cls.league_admin = User.objects.create_user(
            username='league_admin',
            password='StrongPass123!',
        )
        cls.league_admin.groups.add(Group.objects.get(name='League Admin'))

        cls.team_manager = User.objects.create_user(
            username='team_manager',
            password='StrongPass123!',
        )
        cls.team_manager.groups.add(Group.objects.get(name='Team Manager'))

        cls.other_manager = User.objects.create_user(
            username='other_manager',
            password='StrongPass123!',
        )
        cls.other_manager.groups.add(Group.objects.get(name='Team Manager'))

        cls.content_manager = User.objects.create_user(
            username='content_manager',
            password='StrongPass123!',
        )
        cls.content_manager.groups.add(
            Group.objects.get(name='Content Manager')
        )

        cls.team = Team.objects.create(name='Nairobi Stars')
        cls.other_team = Team.objects.create(name='Mombasa United')
        TeamManagerAssignment.objects.create(
            user=cls.team_manager,
            team=cls.team,
        )
        TeamManagerAssignment.objects.create(
            user=cls.other_manager,
            team=cls.other_team,
        )

        cls.season = Season.objects.create(
            name='Season 2026',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.next_season = Season.objects.create(
            name='Season 2027',
            year=2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )

        cls.player = Player.objects.create(
            first_name='Amina',
            last_name='Otieno',
            date_of_birth=date(2012, 5, 6),
            position=Player.Position.FORWARD,
        )
        cls.registration = PlayerRegistration.objects.create(
            player=cls.player,
            team=cls.team,
            season=cls.season,
            shirt_number=9,
            start_date=date(2026, 2, 1),
        )

    def setUp(self):
        self.transfer_date = timezone.localdate()
        if self.transfer_date <= self.registration.start_date:
            self.transfer_date = date(2026, 11, 20)

    def player_form_data(self, **overrides):
        data = {
            'first_name': 'Brian',
            'last_name': 'Kamau',
            'date_of_birth': '2012-04-03',
            'position': Player.Position.MIDFIELDER,
            'team': self.team.pk,
            'season': self.season.pk,
            'start_date': '2026-03-01',
            'shirt_number': '12',
        }
        data.update(overrides)
        return data

    def registration_form_data(self, **overrides):
        data = {
            'player': self.player.pk,
            'team': self.team.pk,
            'season': self.next_season.pk,
            'shirt_number': '14',
            'start_date': '2027-02-01',
            'end_date': '',
        }
        data.update(overrides)
        return data

    def test_manager_can_create_player_with_assigned_team_registration(self):
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:player_create'),
            self.player_form_data(),
        )

        self.assertEqual(response.status_code, 302)
        player = Player.objects.get(first_name='Brian')
        registration = player.registrations.get()
        self.assertEqual(registration.team, self.team)
        self.assertEqual(registration.season, self.season)
        self.assertEqual(registration.shirt_number, 12)

    def test_forged_unassigned_team_cannot_create_player(self):
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:player_create'),
            self.player_form_data(team=self.other_team.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Player.objects.filter(first_name='Brian').exists())

    def test_league_admin_can_create_and_register_player(self):
        self.client.force_login(self.league_admin)

        response = self.client.post(
            reverse('players:player_create'),
            self.player_form_data(team=self.other_team.pk),
        )

        self.assertEqual(response.status_code, 302)
        player = Player.objects.get(first_name='Brian')
        self.assertEqual(player.registrations.get().team, self.other_team)

    def test_content_manager_cannot_create_player(self):
        self.client.force_login(self.content_manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse('players:player_create'),
            self.player_form_data(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Player.objects.filter(first_name='Brian').exists())

    def test_anonymous_visitor_cannot_view_player_directory_or_post_create(
        self,
    ):
        response = self.client.get(reverse('players:player_list'))
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse('players:player_create'),
            self.player_form_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Player.objects.filter(first_name='Brian').exists())

    def test_manager_can_list_only_players_from_assigned_teams(self):
        other_player = Player.objects.create(
            first_name='Other',
            last_name='Player',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=self.other_team,
            season=self.season,
            start_date=date(2026, 2, 1),
        )
        self.client.force_login(self.team_manager)

        response = self.client.get(reverse('players:player_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1')

    def test_manager_can_view_assigned_player_and_scoped_history(self):
        self.client.force_login(self.team_manager)

        response = self.client.get(
            reverse('players:player_detail', args=[self.player.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Amina')

        response = self.client.get(
            reverse(
                'players:registration_history',
                args=[self.player.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1')

    def test_manager_cannot_view_player_outside_assigned_teams(self):
        other_player = Player.objects.create(
            first_name='Private',
            last_name='Player',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=self.other_team,
            season=self.season,
            start_date=date(2026, 2, 1),
        )
        self.client.force_login(self.team_manager)
        self.client.raise_request_exception = False

        response = self.client.get(
            reverse('players:player_detail', args=[other_player.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_edit_assigned_player_profile(self):
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:player_update', args=[self.player.pk]),
            {
                'first_name': 'Amina',
                'last_name': 'Updated',
                'date_of_birth': '2012-05-06',
                'position': Player.Position.MIDFIELDER,
                'is_active': 'off',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.last_name, 'Updated')
        self.assertEqual(self.player.position, Player.Position.MIDFIELDER)
        self.assertTrue(self.player.is_active)

    def test_manager_cannot_edit_player_from_unassigned_team(self):
        other_player = Player.objects.create(
            first_name='Private',
            last_name='Player',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=self.other_team,
            season=self.season,
            start_date=date(2026, 2, 1),
        )
        self.client.force_login(self.team_manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse('players:player_update', args=[other_player.pk]),
            {
                'first_name': 'Forged',
                'last_name': 'Change',
                'date_of_birth': '2011-02-03',
                'position': Player.Position.DEFENDER,
            },
        )

        self.assertEqual(response.status_code, 403)
        other_player.refresh_from_db()
        self.assertEqual(other_player.first_name, 'Private')

    def test_league_admin_can_edit_any_player(self):
        self.client.force_login(self.league_admin)

        response = self.client.post(
            reverse('players:player_update', args=[self.player.pk]),
            {
                'first_name': 'Amina',
                'last_name': 'AdminEdit',
                'date_of_birth': '2012-05-06',
                'position': Player.Position.FORWARD,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.last_name, 'AdminEdit')

    def test_future_date_of_birth_is_rejected(self):
        form = PlayerCreateForm(
            self.player_form_data(date_of_birth='2030-01-01'),
            user=self.team_manager,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('date_of_birth', form.errors)

    def test_manager_can_register_visible_player_in_next_season(self):
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:registration_create'),
            self.registration_form_data(),
        )

        self.assertEqual(response.status_code, 302)
        new_registration = self.player.registrations.get(
            season=self.next_season
        )
        self.assertEqual(new_registration.team, self.team)

    def test_registration_rejects_unassigned_team(self):
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:registration_create'),
            self.registration_form_data(
                team=self.other_team.pk,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.player.registrations.count(), 1)

    def test_registration_rejects_player_outside_manager_scope(self):
        other_player = Player.objects.create(
            first_name='Other',
            last_name='Player',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=self.other_team,
            season=self.season,
            start_date=date(2026, 2, 1),
        )
        self.client.force_login(self.team_manager)

        response = self.client.post(
            reverse('players:registration_create'),
            self.registration_form_data(player=other_player.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(other_player.registrations.count(), 1)

    def test_duplicate_shirt_number_is_rejected(self):
        second_player = Player.objects.create(
            first_name='Second',
            last_name='Player',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        form = PlayerRegistrationForm(
            {
                'player': second_player.pk,
                'team': self.team.pk,
                'season': self.season.pk,
                'shirt_number': 9,
                'start_date': '2026-04-01',
                'end_date': '',
            },
            user=self.league_admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('shirt_number', form.errors)

    def test_overlapping_registration_is_rejected_across_seasons(self):
        with self.assertRaises(ValidationError):
            PlayerRegistration(
                player=self.player,
                team=self.other_team,
                season=Season.objects.create(
                    name='Overlapping seasons',
                    year=2025,
                    start_date=date(2026, 10, 1),
                    end_date=date(2027, 9, 30),
                ),
                start_date=date(2026, 11, 1),
            ).full_clean()

    def test_registration_start_and_end_must_be_within_season(self):
        form = PlayerRegistrationForm(
            {
                'player': self.player.pk,
                'team': self.team.pk,
                'season': self.season.pk,
                'shirt_number': 14,
                'start_date': '2025-12-31',
                'end_date': '',
            },
            user=self.league_admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('start_date', form.errors)

    def test_transfer_preserves_old_registration_and_adds_new_one(self):
        TeamManagerAssignment.objects.create(
            user=self.team_manager,
            team=self.other_team,
        )

        new_registration = transfer_player(
            user=self.team_manager,
            registration_id=self.registration.pk,
            target_team_id=self.other_team.pk,
            transfer_date=self.transfer_date,
            shirt_number=7,
        )

        self.registration.refresh_from_db()
        self.assertEqual(
            self.registration.end_date,
            self.transfer_date - timedelta(days=1),
        )
        self.assertEqual(new_registration.player, self.player)
        self.assertEqual(new_registration.team, self.other_team)
        self.assertEqual(new_registration.start_date, self.transfer_date)
        self.assertEqual(self.player.registrations.count(), 2)

    def test_future_transfer_access_changes_on_effective_date(self):
        transfer_date = date(2026, 11, 20)
        new_registration = transfer_player(
            user=self.league_admin,
            registration_id=self.registration.pk,
            target_team_id=self.other_team.pk,
            transfer_date=transfer_date,
            shirt_number=7,
        )

        for check_date, old_team_access, new_team_access in (
            (date(2026, 11, 19), True, False),
            (transfer_date, False, True),
            (date(2026, 11, 21), False, True),
        ):
            with self.subTest(date=check_date), patch(
                'django.utils.timezone.localdate',
                return_value=check_date,
            ):
                self.assertEqual(
                    can_view_player(self.team_manager, self.player),
                    old_team_access,
                )
                self.assertEqual(
                    can_manage_player(self.team_manager, self.player),
                    old_team_access,
                )
                self.assertEqual(
                    can_view_player(self.other_manager, self.player),
                    new_team_access,
                )
                self.assertEqual(
                    can_manage_player(self.other_manager, self.player),
                    new_team_access,
                )
                visible_registration_ids = set(
                    visible_registrations_for_user(
                        self.team_manager
                    ).values_list('pk', flat=True)
                )
                self.assertEqual(
                    self.registration.pk in visible_registration_ids,
                    old_team_access,
                )
                visible_registration_ids = set(
                    visible_registrations_for_user(
                        self.other_manager
                    ).values_list('pk', flat=True)
                )
                self.assertEqual(
                    new_registration.pk in visible_registration_ids,
                    new_team_access,
                )

    def test_transfer_preserves_historical_match_performance(self):
        match = Match.objects.create(
            season=self.season,
            home_team=self.team,
            away_team=self.other_team,
            kickoff_time=timezone.make_aware(
                datetime(2026, 11, 10, 15, 0)
            ),
        )
        performance = PlayerMatchPerformance(
            match=match,
            player=self.player,
            appeared=True,
            minutes_played=90,
            goals_scored=1,
        )
        performance.full_clean()
        performance.save()

        transfer_player(
            user=self.league_admin,
            registration_id=self.registration.pk,
            target_team_id=self.other_team.pk,
            transfer_date=date(2026, 11, 20),
            shirt_number=7,
        )

        performance.refresh_from_db()
        performance.full_clean()
        retained_registration = self.player.registrations.get(
            team=self.team,
            season=match.season,
        )
        match_date = timezone.localtime(match.kickoff_time).date()
        self.assertLessEqual(retained_registration.start_date, match_date)
        self.assertGreaterEqual(retained_registration.end_date, match_date)
        self.assertIn(
            retained_registration.team_id,
            (match.home_team_id, match.away_team_id),
        )
        self.assertEqual(performance.match_id, match.pk)
        self.assertEqual(performance.match.season_id, self.season.pk)
        self.assertEqual(
            PlayerMatchPerformance.objects.get(pk=performance.pk).goals_scored,
            1,
        )

    def test_manager_cannot_transfer_to_unassigned_team(self):
        with self.assertRaises(PermissionDenied):
            transfer_player(
                user=self.team_manager,
                registration_id=self.registration.pk,
                target_team_id=self.other_team.pk,
                transfer_date=self.transfer_date,
                shirt_number=7,
            )

        self.registration.refresh_from_db()
        self.assertIsNone(self.registration.end_date)
        self.assertEqual(self.player.registrations.count(), 1)

    def test_failed_transfer_rolls_back_old_registration_end_date(self):
        TeamManagerAssignment.objects.create(
            user=self.team_manager,
            team=self.other_team,
        )
        other_player = Player.objects.create(
            first_name='Other',
            last_name='Squad',
            date_of_birth=date(2011, 2, 3),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=other_player,
            team=self.other_team,
            season=self.season,
            shirt_number=7,
            start_date=date(2026, 2, 1),
        )

        with self.assertRaises(ValidationError):
            transfer_player(
                user=self.team_manager,
                registration_id=self.registration.pk,
                target_team_id=self.other_team.pk,
                transfer_date=self.transfer_date,
                shirt_number=7,
            )

        self.registration.refresh_from_db()
        self.assertIsNone(self.registration.end_date)
        self.assertEqual(self.player.registrations.count(), 1)

    def test_manager_cannot_transfer_registration_from_unassigned_team(self):
        self.client.force_login(self.other_manager)
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse(
                'players:registration_transfer',
                args=[self.registration.pk],
            ),
            {
                'team': self.other_team.pk,
                'transfer_date': self.transfer_date.isoformat(),
                'shirt_number': 7,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.registration.refresh_from_db()
        self.assertIsNone(self.registration.end_date)

    def test_admin_cannot_delete_registration_history(self):
        request = type('Request', (), {'user': self.league_admin})()
        model_admin = PlayerRegistrationAdmin(
            PlayerRegistration,
            admin.site,
        )
        inline = PlayerRegistrationInline(Player, admin.site)

        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(inline.has_add_permission(request, self.player))
        self.assertFalse(inline.has_change_permission(request, self.player))
        self.assertFalse(inline.has_delete_permission(request, self.player))

    def test_admin_registration_creation_uses_service_validation(self):
        model_admin = PlayerRegistrationAdmin(
            PlayerRegistration,
            admin.site,
        )
        request = type('Request', (), {'user': self.league_admin})()
        duplicate = PlayerRegistration(
            player=Player.objects.create(
                first_name='Admin',
                last_name='Duplicate',
                date_of_birth=date(2012, 1, 1),
                position=Player.Position.FORWARD,
            ),
            team=self.team,
            season=self.season,
            shirt_number=self.registration.shirt_number,
            start_date=date(2026, 3, 1),
        )

        with self.assertRaises(ValidationError):
            model_admin.save_model(
                request,
                duplicate,
                form=None,
                change=False,
            )

        self.assertFalse(
            PlayerRegistration.objects.filter(player=duplicate.player).exists()
        )

    def test_direct_registration_service_checks_assignment_and_model_rules(
        self,
    ):
        with self.assertRaises(PermissionDenied):
            register_player(
                user=self.team_manager,
                player_id=self.player.pk,
                team_id=self.other_team.pk,
                season_id=self.next_season.pk,
                start_date=date(2027, 2, 1),
            )

        with self.assertRaises(ValidationError):
            register_player(
                user=self.league_admin,
                player_id=self.player.pk,
                team_id=self.other_team.pk,
                season_id=self.next_season.pk,
                start_date=date(2026, 11, 1),
            )

        self.assertEqual(self.player.registrations.count(), 1)

    def test_direct_player_update_service_checks_manager_scope(self):
        with self.assertRaises(PermissionDenied):
            update_player(
                user=self.other_manager,
                player_id=self.player.pk,
                values={'last_name': 'Unauthorized'},
            )

        self.player.refresh_from_db()
        self.assertEqual(self.player.last_name, 'Otieno')

    def test_create_service_rolls_back_player_if_registration_invalid(self):
        player = Player(
            first_name='Rollback',
            last_name='Player',
            date_of_birth=date(2012, 1, 1),
            position=Player.Position.FORWARD,
        )

        with self.assertRaises(ValidationError):
            create_player_with_registration(
                user=self.team_manager,
                player=player,
                team_id=self.team.pk,
                season_id=self.season.pk,
                start_date=date(2025, 12, 31),
                shirt_number=11,
            )

        self.assertFalse(Player.objects.filter(first_name='Rollback').exists())
