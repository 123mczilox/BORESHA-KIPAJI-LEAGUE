import json
from datetime import date, datetime
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import create_user_groups
from apps.players.models import Player, PlayerRegistration
from apps.teams.models import Team, TeamManagerAssignment

from .admin import MatchAdmin, MatchEventAdmin, MatchOfficialAdmin
from .models import (
    Match,
    MatchEvent,
    MatchOfficial,
    Season,
    SeasonTeam,
)
from .services import (
    assign_match_official,
    create_fixture,
    create_match_event,
    register_team_for_season,
    transition_match,
    update_fixture,
)


User = get_user_model()


class MatchManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_user_groups()

        cls.league_admin = User.objects.create_user(
            username='league_admin',
            password='StrongPass123!',
            is_staff=True,
        )
        cls.league_admin.groups.add(Group.objects.get(name='League Admin'))
        cls.manager = User.objects.create_user(
            username='team_manager',
            password='StrongPass123!',
            is_staff=True,
        )
        cls.manager.groups.add(Group.objects.get(name='Team Manager'))
        cls.other_manager = User.objects.create_user(
            username='other_manager',
            password='StrongPass123!',
            is_staff=True,
        )
        cls.other_manager.groups.add(Group.objects.get(name='Team Manager'))
        cls.official = User.objects.create_user(
            username='match_official',
            password='StrongPass123!',
            is_staff=True,
        )
        cls.official.groups.add(Group.objects.get(name='Match Official'))
        cls.other_official = User.objects.create_user(
            username='other_official',
            password='StrongPass123!',
            is_staff=True,
        )
        cls.other_official.groups.add(Group.objects.get(name='Match Official'))
        cls.ordinary_user = User.objects.create_user(
            username='ordinary_user',
            password='StrongPass123!',
            is_staff=True,
        )

        cls.home_team = Team.objects.create(name='Home FC')
        cls.away_team = Team.objects.create(name='Away FC')
        cls.outside_team = Team.objects.create(name='Outside FC')
        TeamManagerAssignment.objects.create(
            user=cls.manager,
            team=cls.home_team,
        )
        TeamManagerAssignment.objects.create(
            user=cls.other_manager,
            team=cls.away_team,
        )
        cls.season = Season.objects.create(
            name='2026 Season',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.other_season = Season.objects.create(
            name='2027 Season',
            year=2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )
        register_team_for_season(
            user=cls.league_admin,
            team_id=cls.home_team.pk,
            season_id=cls.season.pk,
        )
        register_team_for_season(
            user=cls.league_admin,
            team_id=cls.away_team.pk,
            season_id=cls.season.pk,
        )

        cls.home_player = Player.objects.create(
            first_name='Home',
            last_name='Player',
            date_of_birth=date(2010, 3, 1),
            position=Player.Position.FORWARD,
        )
        cls.away_player = Player.objects.create(
            first_name='Away',
            last_name='Player',
            date_of_birth=date(2010, 4, 1),
            position=Player.Position.DEFENDER,
        )
        PlayerRegistration.objects.create(
            player=cls.home_player,
            team=cls.home_team,
            season=cls.season,
            start_date=date(2026, 1, 1),
        )
        PlayerRegistration.objects.create(
            player=cls.away_player,
            team=cls.away_team,
            season=cls.season,
            start_date=date(2026, 1, 1),
        )
        cls.fixture_values = {
            'season': cls.season,
            'home_team': cls.home_team,
            'away_team': cls.away_team,
            'matchweek': 1,
            'kickoff_time': timezone.make_aware(
                datetime(2026, 11, 20, 15, 0)
            ),
            'venue': 'Community Ground',
        }
        cls.match = create_fixture(
            user=cls.league_admin,
            values=cls.fixture_values,
        )
        cls.assignment = assign_match_official(
            user=cls.league_admin,
            match_id=cls.match.pk,
            official_user_id=cls.official.pk,
            role=MatchOfficial.Role.REFEREE,
        )

    def post_json(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def patch_json(self, url, data):
        return self.client.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def test_league_admin_can_create_fixture(self):
        self.client.force_login(self.league_admin)
        response = self.post_json(
            reverse('matches:match_list_create'),
            {
                'season': self.season.pk,
                'home_team': self.home_team.pk,
                'away_team': self.away_team.pk,
                'matchweek': 2,
                'kickoff_time': '2026-11-21T15:00:00+03:00',
                'venue': 'Second Ground',
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], Match.Status.SCHEDULED)
        self.assertEqual(Match.objects.count(), 2)

    def test_fixture_rejects_same_home_and_away_team(self):
        self.client.force_login(self.league_admin)
        response = self.post_json(
            reverse('matches:match_list_create'),
            {
                'season': self.season.pk,
                'home_team': self.home_team.pk,
                'away_team': self.home_team.pk,
                'matchweek': 1,
                'kickoff_time': '2026-11-21T15:00:00+03:00',
                'venue': '',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Match.objects.count(), 1)

    def test_fixture_requires_both_teams_to_be_enrolled_in_season(self):
        self.client.force_login(self.league_admin)
        response = self.post_json(
            reverse('matches:match_list_create'),
            {
                'season': self.other_season.pk,
                'home_team': self.home_team.pk,
                'away_team': self.away_team.pk,
                'matchweek': 1,
                'kickoff_time': '2027-02-01T15:00:00+03:00',
                'venue': '',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Match.objects.count(), 1)

    def test_fixture_validates_matchweek_and_season_kickoff_range(self):
        self.client.force_login(self.league_admin)
        zero_matchweek = self.post_json(
            reverse('matches:match_list_create'),
            {
                **self.fixture_payload(),
                'matchweek': 0,
            },
        )
        out_of_season = self.post_json(
            reverse('matches:match_list_create'),
            {
                **self.fixture_payload(),
                'kickoff_time': '2027-01-01T12:00:00+03:00',
            },
        )

        self.assertEqual(zero_matchweek.status_code, 400)
        self.assertEqual(out_of_season.status_code, 400)
        self.assertEqual(Match.objects.count(), 1)

    def test_league_admin_can_edit_unstarted_fixture(self):
        self.client.force_login(self.league_admin)
        response = self.patch_json(
            reverse('matches:match_detail', args=[self.match.pk]),
            {'venue': 'Updated Ground'},
        )

        self.assertEqual(response.status_code, 200)
        self.match.refresh_from_db()
        self.assertEqual(self.match.venue, 'Updated Ground')

    def fixture_payload(self):
        return {
            'season': self.season.pk,
            'home_team': self.home_team.pk,
            'away_team': self.away_team.pk,
            'matchweek': 1,
            'kickoff_time': '2026-11-21T15:00:00+03:00',
            'venue': '',
        }

    def test_only_league_admin_can_register_season_team(self):
        with self.assertRaises(PermissionDenied):
            register_team_for_season(
                user=self.manager,
                team_id=self.home_team.pk,
                season_id=self.other_season.pk,
            )

        membership = register_team_for_season(
            user=self.league_admin,
            team_id=self.home_team.pk,
            season_id=self.other_season.pk,
        )
        self.assertEqual(membership.season, self.other_season)

    def test_only_league_admin_can_assign_officials_and_duplicates_rejected(
        self,
    ):
        self.client.force_login(self.manager)
        denied = self.post_json(
            reverse('matches:match_officials', args=[self.match.pk]),
            {'user': self.other_official.pk, 'role': 'assistant'},
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.league_admin)
        duplicate = self.post_json(
            reverse('matches:match_officials', args=[self.match.pk]),
            {'user': self.official.pk, 'role': 'assistant'},
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(self.match.officials.count(), 1)

        created = self.post_json(
            reverse('matches:match_officials', args=[self.match.pk]),
            {'user': self.other_official.pk, 'role': 'assistant'},
        )
        self.assertEqual(created.status_code, 201)

    def test_match_official_can_only_access_assigned_match(self):
        self.client.force_login(self.official)
        assigned = self.client.get(
            reverse('matches:match_detail', args=[self.match.pk])
        )
        self.client.force_login(self.other_official)
        unassigned = self.client.get(
            reverse('matches:match_detail', args=[self.match.pk])
        )

        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(unassigned.status_code, 403)

    def test_team_manager_cannot_view_official_assignments_or_match_events(
        self,
    ):
        self.client.force_login(self.manager)
        assignments = self.client.get(
            reverse('matches:match_officials', args=[self.match.pk])
        )
        events = self.client.get(
            reverse('matches:match_events', args=[self.match.pk])
        )

        self.assertEqual(assignments.status_code, 403)
        self.assertEqual(events.status_code, 403)

    def test_status_transitions_and_completion_result(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values={
                'event_type': MatchEvent.EventType.GOAL,
                'player': self.home_player,
                'minute': 12,
                'added_time': 0,
                'description': '',
            },
        )
        create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values={
                'event_type': MatchEvent.EventType.OWN_GOAL,
                'player': self.away_player,
                'minute': 30,
                'added_time': 0,
                'description': '',
            },
        )

        completed = transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.COMPLETED,
            home_score=2,
            away_score=0,
        )

        self.assertEqual(completed.home_score, 2)
        self.assertEqual(completed.away_score, 0)

    def test_invalid_status_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            transition_match(
                user=self.official,
                match_id=self.match.pk,
                status=Match.Status.COMPLETED,
            )

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.SCHEDULED)
        self.assertIsNone(self.match.home_score)

    def test_league_admin_can_complete_a_scoreless_match(self):
        transition_match(
            user=self.league_admin,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        completed = transition_match(
            user=self.league_admin,
            match_id=self.match.pk,
            status=Match.Status.COMPLETED,
        )

        self.assertEqual(completed.home_score, 0)
        self.assertEqual(completed.away_score, 0)

    def test_completed_match_cannot_be_edited_or_reopened(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.COMPLETED,
        )
        with self.assertRaises(ValidationError):
            update_fixture(
                user=self.league_admin,
                match_id=self.match.pk,
                values={'venue': 'Changed after completion'},
            )
        with self.assertRaises(ValidationError):
            transition_match(
                user=self.league_admin,
                match_id=self.match.pk,
                status=Match.Status.LIVE,
            )

    def test_started_postponed_match_cannot_be_rescheduled_as_fixture_edit(
        self,
    ):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.POSTPONED,
        )

        with self.assertRaises(ValidationError):
            update_fixture(
                user=self.league_admin,
                match_id=self.match.pk,
                values={'kickoff_time': timezone.make_aware(
                    datetime(2026, 11, 25, 15, 0)
                )},
            )

        self.match.refresh_from_db()
        self.assertIsNotNone(self.match.started_at)
        self.assertEqual(self.match.status, Match.Status.POSTPONED)

    def test_manager_cannot_change_lifecycle_or_forge_scores(self):
        self.client.force_login(self.manager)
        response = self.post_json(
            reverse('matches:match_lifecycle', args=[self.match.pk]),
            {
                'status': Match.Status.COMPLETED,
                'home_score': 99,
                'away_score': 0,
            },
        )
        self.assertEqual(response.status_code, 403)

        fixture_response = self.patch_json(
            reverse('matches:match_detail', args=[self.match.pk]),
            {'home_score': 99, 'status': Match.Status.COMPLETED},
        )
        self.assertEqual(fixture_response.status_code, 403)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.SCHEDULED)
        self.assertIsNone(self.match.home_score)

    def test_league_admin_cannot_forge_scores_through_fixture_edit(self):
        self.client.force_login(self.league_admin)
        response = self.patch_json(
            reverse('matches:match_detail', args=[self.match.pk]),
            {'home_score': 5, 'status': Match.Status.COMPLETED},
        )

        self.assertEqual(response.status_code, 400)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.SCHEDULED)
        self.assertIsNone(self.match.home_score)

    def test_unassigned_official_cannot_change_lifecycle(self):
        self.client.force_login(self.other_official)
        response = self.post_json(
            reverse('matches:match_lifecycle', args=[self.match.pk]),
            {'status': Match.Status.LIVE},
        )

        self.assertEqual(response.status_code, 403)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.SCHEDULED)

    def test_nonofficial_cannot_be_assigned(self):
        with self.assertRaises(ValidationError):
            assign_match_official(
                user=self.league_admin,
                match_id=self.match.pk,
                official_user_id=self.ordinary_user.pk,
                role=MatchOfficial.Role.REFEREE,
            )

    def test_events_require_live_status_and_eligible_player(self):
        with self.assertRaises(ValidationError):
            create_match_event(
                user=self.official,
                match_id=self.match.pk,
                values={
                    'event_type': MatchEvent.EventType.GOAL,
                    'player': self.home_player,
                    'minute': 1,
                },
            )

        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        outsider = Player.objects.create(
            first_name='Outside',
            last_name='Player',
            date_of_birth=date(2010, 1, 1),
            position=Player.Position.MIDFIELDER,
        )
        PlayerRegistration.objects.create(
            player=outsider,
            team=self.outside_team,
            season=self.season,
            start_date=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            create_match_event(
                user=self.official,
                match_id=self.match.pk,
                values={
                    'event_type': MatchEvent.EventType.GOAL,
                    'player': outsider,
                    'minute': 1,
                },
            )

    def test_identical_match_event_cannot_be_recorded_twice(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        event_values = {
            'event_type': MatchEvent.EventType.GOAL,
            'player': self.home_player,
            'minute': 12,
            'added_time': 0,
            'description': '',
        }
        create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values=event_values,
        )

        with self.assertRaises(ValidationError):
            create_match_event(
                user=self.official,
                match_id=self.match.pk,
                values=event_values,
            )

        self.assertEqual(self.match.events.count(), 1)
        self.match.refresh_from_db()
        self.assertEqual((self.match.home_score, self.match.away_score), (1, 0))

    def test_event_minute_and_substitution_participants_are_validated(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        with self.assertRaises(ValidationError):
            create_match_event(
                user=self.official,
                match_id=self.match.pk,
                values={
                    'event_type': MatchEvent.EventType.GOAL,
                    'player': self.home_player,
                    'minute': 0,
                },
            )
        with self.assertRaises(ValidationError):
            create_match_event(
                user=self.official,
                match_id=self.match.pk,
                values={
                    'event_type': MatchEvent.EventType.SUBSTITUTION,
                    'player': self.home_player,
                    'minute': 20,
                },
            )

        same_team_substitute = Player.objects.create(
            first_name='Substitute',
            last_name='Home',
            date_of_birth=date(2010, 5, 1),
            position=Player.Position.MIDFIELDER,
        )
        PlayerRegistration.objects.create(
            player=same_team_substitute,
            team=self.home_team,
            season=self.season,
            start_date=date(2026, 1, 1),
        )
        substitution = create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values={
                'event_type': MatchEvent.EventType.SUBSTITUTION,
                'player': self.home_player,
                'related_player': same_team_substitute,
                'minute': 20,
            },
        )
        self.assertEqual(substitution.related_player, same_team_substitute)

    def test_failed_result_completion_rolls_back_recalculated_scores(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values={
                'event_type': MatchEvent.EventType.GOAL,
                'player': self.home_player,
                'minute': 12,
            },
        )
        before = Match.objects.get(pk=self.match.pk)

        with self.assertRaises(ValidationError):
            transition_match(
                user=self.official,
                match_id=self.match.pk,
                status=Match.Status.COMPLETED,
                home_score=9,
                away_score=0,
            )

        after = Match.objects.get(pk=self.match.pk)
        self.assertEqual(after.status, Match.Status.LIVE)
        self.assertEqual(after.home_score, before.home_score)
        self.assertEqual(after.away_score, before.away_score)

    def test_failed_event_score_update_rolls_back_event_creation(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )
        with patch(
            'apps.matches.services._recalculate_match_score',
            side_effect=ValidationError('Score recalculation failed.'),
        ):
            with self.assertRaises(ValidationError):
                create_match_event(
                    user=self.official,
                    match_id=self.match.pk,
                    values={
                        'event_type': MatchEvent.EventType.GOAL,
                        'player': self.home_player,
                        'minute': 12,
                    },
                )

        self.assertFalse(self.match.events.exists())

    def test_admin_permissions_block_unauthorized_match_changes(self):
        request = type('Request', (), {'user': self.manager})()
        match_admin = MatchAdmin(Match, admin.site)
        official_admin = MatchOfficialAdmin(MatchOfficial, admin.site)
        event_admin = MatchEventAdmin(MatchEvent, admin.site)

        self.assertFalse(match_admin.has_change_permission(request, self.match))
        self.assertFalse(
            official_admin.has_add_permission(request)
        )
        self.assertFalse(event_admin.has_add_permission(request))
        self.assertFalse(official_admin.has_delete_permission(request))
        self.assertFalse(event_admin.has_delete_permission(request))

        request.user = self.official
        self.assertTrue(match_admin.has_change_permission(request, self.match))
        self.assertTrue(event_admin.has_add_permission(request))

        request.user = self.league_admin
        self.assertTrue(match_admin.has_change_permission(request, self.match))
        self.assertTrue(official_admin.has_add_permission(request))

    def test_match_admin_routes_official_status_change_through_service(self):
        request = type('Request', (), {'user': self.official})()
        model_admin = MatchAdmin(Match, admin.site)
        match = Match.objects.get(pk=self.match.pk)
        match.status = Match.Status.LIVE

        model_admin.save_model(request, match, form=None, change=True)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.LIVE)
        self.assertIsNotNone(self.match.started_at)
