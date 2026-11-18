from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import create_user_groups
from apps.matches.models import Match, Season
from apps.matches.services import register_team_for_season
from apps.teams.models import Team

from .models import TeamStandings
from .services import (
    recalculate_completed_match_standings,
    recalculate_season_standings,
)


User = get_user_model()


class LeagueStandingsEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_user_groups()
        cls.admin = User.objects.create_user(username='standings_admin')
        cls.admin.groups.add(Group.objects.get(name='League Admin'))
        cls.manager = User.objects.create_user(username='standings_manager')
        cls.manager.groups.add(Group.objects.get(name='Team Manager'))
        cls.official = User.objects.create_user(username='standings_official')
        cls.official.groups.add(Group.objects.get(name='Match Official'))

        cls.season = Season.objects.create(
            name='Standings Season 2026',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.next_season = Season.objects.create(
            name='Standings Season 2027',
            year=2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )
        cls.home = Team.objects.create(name='Standings Home')
        cls.away = Team.objects.create(name='Standings Away')
        cls.third = Team.objects.create(name='Standings Third')
        cls.unplayed = Team.objects.create(name='Standings Unplayed')
        cls.outside = Team.objects.create(name='Standings Outside')
        for season in (cls.season, cls.next_season):
            for team in (cls.home, cls.away, cls.third, cls.unplayed):
                register_team_for_season(
                    user=cls.admin,
                    team_id=team.pk,
                    season_id=season.pk,
                )

        cls.home_win = cls.make_match(
            cls.season,
            cls.home,
            cls.away,
            datetime(2026, 3, 1, 15, 0),
            2,
            0,
        )
        cls.draw = cls.make_match(
            cls.season,
            cls.away,
            cls.third,
            datetime(2026, 3, 8, 15, 0),
            1,
            1,
        )
        cls.home_win_again = cls.make_match(
            cls.season,
            cls.third,
            cls.home,
            datetime(2026, 3, 15, 15, 0),
            0,
            1,
        )
        cls.next_season_draw = cls.make_match(
            cls.next_season,
            cls.home,
            cls.away,
            datetime(2027, 3, 1, 15, 0),
            2,
            2,
        )

        cls.unfinished = Match.objects.create(
            season=cls.season,
            home_team=cls.home,
            away_team=cls.third,
            kickoff_time=timezone.make_aware(
                datetime(2026, 4, 1, 15, 0)
            ),
            status=Match.Status.POSTPONED,
            home_score=9,
            away_score=0,
        )
        cls.cancelled = Match.objects.create(
            season=cls.season,
            home_team=cls.home,
            away_team=cls.third,
            kickoff_time=timezone.make_aware(
                datetime(2026, 4, 8, 15, 0)
            ),
            status=Match.Status.CANCELLED,
            home_score=99,
            away_score=0,
        )

    @classmethod
    def make_match(cls, season, home, away, kickoff, home_score, away_score):
        match = Match(
            season=season,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.make_aware(kickoff),
            status=Match.Status.COMPLETED,
            home_score=home_score,
            away_score=away_score,
        )
        match.full_clean()
        match.save()
        return match

    def recalculate(self, season=None):
        return recalculate_season_standings(
            user=self.admin,
            season_id=(season or self.season).pk,
        )

    def test_completed_results_generate_win_draw_loss_and_goal_totals(self):
        standings = {
            row.team_id: row
            for row in self.recalculate()
        }
        home = standings[self.home.pk]
        self.assertEqual(
            (
                home.played,
                home.won,
                home.drawn,
                home.lost,
                home.goals_for,
                home.goals_against,
                home.goal_difference,
                home.points,
            ),
            (2, 2, 0, 0, 3, 0, 3, 6),
        )
        away = standings[self.away.pk]
        self.assertEqual(
            (
                away.played,
                away.won,
                away.drawn,
                away.lost,
                away.goals_for,
                away.goals_against,
                away.goal_difference,
                away.points,
            ),
            (2, 0, 1, 1, 1, 3, -2, 1),
        )
        third = standings[self.third.pk]
        self.assertEqual(
            (
                third.played,
                third.won,
                third.drawn,
                third.lost,
                third.goal_difference,
                third.points,
            ),
            (2, 0, 1, 1, -1, 1),
        )
        self.assertEqual(len(standings), 4)

    def test_recalculation_is_idempotent_and_ignores_unfinished_matches(self):
        for _ in range(2):
            self.recalculate()

        home = TeamStandings.objects.get(
            session=self.season,
            team=self.home,
        )
        self.assertEqual(home.played, 2)
        self.assertEqual(home.goals_for, 3)
        self.assertEqual(home.points, 6)

    def test_public_table_is_read_only_season_scoped_and_includes_zero_match_teams(self):
        response = self.client.get(
            reverse('standings:league_table'),
            {'season_id': self.season.pk},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.json()['standings']
        self.assertEqual(len(rows), 4)
        unplayed = next(
            row for row in rows
            if row['team']['id'] == self.unplayed.pk
        )
        self.assertEqual(unplayed['played'], 0)
        self.assertEqual(
            self.client.post(
                reverse('standings:league_table'),
                data={'season_id': self.season.pk},
            ).status_code,
            405,
        )

    def test_season_recalculation_does_not_mix_season_results(self):
        self.recalculate(self.season)
        current = {
            row.team_id: row
            for row in self.recalculate(self.next_season)
        }
        self.assertEqual(current[self.home.pk].played, 1)
        self.assertEqual(current[self.home.pk].drawn, 1)
        self.assertEqual(current[self.home.pk].points, 1)
        self.assertEqual(current[self.third.pk].played, 0)
        self.assertEqual(current[self.unplayed.pk].played, 0)
        self.assertEqual(
            TeamStandings.objects.get(
                session=self.season,
                team=self.home,
            ).played,
            2,
        )

    def test_authorized_result_correction_rebuilds_standings(self):
        self.recalculate()
        Match.objects.filter(pk=self.home_win.pk).update(
            home_score=0,
            away_score=4,
        )
        standings = {
            row.team_id: row
            for row in self.recalculate()
        }
        self.assertEqual(standings[self.home.pk].won, 1)
        self.assertEqual(standings[self.home.pk].lost, 1)
        self.assertEqual(standings[self.home.pk].points, 3)
        self.assertEqual(standings[self.away.pk].won, 1)
        self.assertEqual(standings[self.away.pk].points, 4)

    def test_non_enrolled_completed_match_is_rejected(self):
        Match.objects.create(
            season=self.season,
            home_team=self.home,
            away_team=self.outside,
            kickoff_time=timezone.make_aware(
                datetime(2026, 6, 1, 15, 0)
            ),
            status=Match.Status.COMPLETED,
            home_score=1,
            away_score=0,
        )
        with self.assertRaises(ValidationError):
            self.recalculate()

    def test_recalculation_requires_league_admin(self):
        with self.assertRaises(PermissionDenied):
            recalculate_season_standings(
                user=self.manager,
                season_id=self.season.pk,
            )
        with self.assertRaises(PermissionDenied):
            recalculate_completed_match_standings(
                user=self.official,
                match_id=self.home_win.pk,
            )

    def test_season_team_membership_without_matches_has_zero_standing(self):
        standings = {
            row.team_id: row
            for row in self.recalculate()
        }
        self.assertEqual(standings[self.third.pk].played, 2)
        self.assertEqual(standings[self.unplayed.pk].played, 0)
        self.assertNotIn(self.outside.pk, standings)

    def test_standings_update_rolls_back_if_recalculation_fails(self):
        with patch(
            'apps.standings.services._calculate_season_standings',
            side_effect=RuntimeError('simulated standings failure'),
        ):
            with self.assertRaises(RuntimeError):
                self.recalculate()
        self.assertFalse(
            TeamStandings.objects.filter(session=self.season).exists()
        )
