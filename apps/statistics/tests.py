from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import create_user_groups
from apps.matches.models import Match, MatchEvent, MatchOfficial, Season
from apps.matches.services import (
    assign_match_official,
    create_fixture,
    create_match_event,
    register_team_for_season,
    transition_match,
    update_match_event,
)
from apps.players.models import Player, PlayerRegistration
from apps.standings.models import TeamStandings
from apps.teams.models import Team

from .models import PlayerMatchPerformance, PlayerSeasonStatistics
from .admin import PlayerMatchPerformanceAdmin
from .services import (
    recalculate_completed_match_statistics,
    recalculate_player_season_statistics,
    record_match_performance,
)


User = get_user_model()


class PlayerStatisticsEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_user_groups()
        cls.admin = User.objects.create_user(username='statistics_admin')
        cls.admin.groups.add(Group.objects.get(name='League Admin'))
        cls.official = User.objects.create_user(username='statistics_official')
        cls.official.groups.add(Group.objects.get(name='Match Official'))
        cls.unassigned_official = User.objects.create_user(
            username='unassigned_statistics_official'
        )
        cls.unassigned_official.groups.add(
            Group.objects.get(name='Match Official')
        )
        cls.manager = User.objects.create_user(username='statistics_manager')
        cls.manager.groups.add(Group.objects.get(name='Team Manager'))

        cls.season = Season.objects.create(
            name='Statistics Season 2026',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.home = Team.objects.create(name='Statistics Home')
        cls.away = Team.objects.create(name='Statistics Away')
        for team in (cls.home, cls.away):
            register_team_for_season(
                user=cls.admin,
                team_id=team.pk,
                season_id=cls.season.pk,
            )

        cls.scorer = cls.make_player('Multiple', 'Scorer')
        cls.carded = cls.make_player('Carded', 'Player')
        cls.own_goal = cls.make_player('Own', 'Goal')
        cls.goalkeeper = cls.make_player(
            'Home',
            'Goalkeeper',
            Player.Position.GOALKEEPER,
        )
        for player, team in (
            (cls.scorer, cls.home),
            (cls.carded, cls.home),
            (cls.own_goal, cls.away),
            (cls.goalkeeper, cls.home),
        ):
            PlayerRegistration.objects.create(
                player=player,
                team=team,
                season=cls.season,
                start_date=cls.season.start_date,
            )

        cls.match = cls.make_match(
            cls.season,
            cls.home,
            cls.away,
            datetime(2026, 11, 20, 15, 0),
        )
        assign_match_official(
            user=cls.admin,
            match_id=cls.match.pk,
            official_user_id=cls.official.pk,
            role=MatchOfficial.Role.REFEREE,
        )

    @classmethod
    def make_player(cls, first_name, last_name, position=Player.Position.FORWARD):
        return Player.objects.create(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date(2010, 3, 1),
            position=position,
        )

    @classmethod
    def make_match(cls, season, home, away, kickoff):
        return create_fixture(
            user=cls.admin,
            values={
                'season': season,
                'home_team': home,
                'away_team': away,
                'matchweek': 1,
                'kickoff_time': timezone.make_aware(kickoff),
            },
        )

    def record_event(self, player, event_type, minute):
        return create_match_event(
            user=self.official,
            match_id=self.match.pk,
            values={
                'event_type': event_type,
                'player': player,
                'minute': minute,
                'added_time': 0,
                'description': '',
            },
        )

    def start_match(self):
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.LIVE,
        )

    def complete_match(self):
        return transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.COMPLETED,
        )

    def test_completed_match_aggregates_events_and_verified_performance(self):
        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 10)
        self.record_event(self.scorer, MatchEvent.EventType.PENALTY_GOAL, 24)
        self.record_event(self.carded, MatchEvent.EventType.YELLOW_CARD, 35)
        self.record_event(self.carded, MatchEvent.EventType.RED_CARD, 82)
        self.record_event(self.own_goal, MatchEvent.EventType.OWN_GOAL, 56)

        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.scorer.pk,
            values={
                'appeared': True,
                'minutes_played': 90,
                'assists': 2,
                'player_of_the_match': True,
            },
        )
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.goalkeeper.pk,
            values={
                'appeared': True,
                'minutes_played': 90,
                'clean_sheet': True,
                'penalties_saved': 1,
            },
        )
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.carded.pk,
            values={'appeared': True, 'minutes_played': 82},
        )
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.own_goal.pk,
            values={'appeared': True, 'minutes_played': 56},
        )
        self.complete_match()

        scorer = PlayerMatchPerformance.objects.get(
            match=self.match,
            player=self.scorer,
        )
        self.assertEqual(scorer.goals_scored, 2)
        self.assertEqual(scorer.assists, 2)
        self.assertTrue(scorer.player_of_the_match)
        carded = PlayerMatchPerformance.objects.get(
            match=self.match,
            player=self.carded,
        )
        self.assertEqual(carded.yellow_cards, 1)
        self.assertEqual(carded.red_cards, 1)
        own_goal = PlayerMatchPerformance.objects.get(
            match=self.match,
            player=self.own_goal,
        )
        self.assertEqual(own_goal.own_goals, 1)

        scorer_season = PlayerSeasonStatistics.objects.get(
            season=self.season,
            player=self.scorer,
        )
        self.assertEqual(scorer_season.appearances, 1)
        self.assertEqual(scorer_season.goals_scored, 2)
        self.assertEqual(scorer_season.assists, 2)
        self.assertEqual(scorer_season.minutes_played, 90)
        goalkeeper_season = PlayerSeasonStatistics.objects.get(
            season=self.season,
            player=self.goalkeeper,
        )
        self.assertEqual(goalkeeper_season.clean_sheets, 1)
        self.assertEqual(goalkeeper_season.penalties_saved, 1)
        self.assertEqual(goalkeeper_season.appearances, 1)
        self.assertEqual(
            PlayerSeasonStatistics.objects.get(
                season=self.season,
                player=self.carded,
            ).red_cards,
            1,
        )
        home_standing = TeamStandings.objects.get(
            session=self.season,
            team=self.home,
        )
        self.assertEqual(
            (home_standing.played, home_standing.won,
             home_standing.goals_for, home_standing.points),
            (1, 1, 3, 3),
        )
        away_standing = TeamStandings.objects.get(
            session=self.season,
            team=self.away,
        )
        self.assertEqual(
            (away_standing.played, away_standing.lost,
             away_standing.goals_against, away_standing.points),
            (1, 1, 3, 0),
        )

    def test_recalculation_is_idempotent_and_correction_updates_totals(self):
        self.start_match()
        goal = self.record_event(
            self.scorer,
            MatchEvent.EventType.GOAL,
            12,
        )
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.scorer.pk,
            values={'appeared': True, 'minutes_played': 90},
        )
        self.complete_match()

        for _ in range(2):
            recalculate_player_season_statistics(
                user=self.admin,
                season_id=self.season.pk,
            )
        statistics = PlayerSeasonStatistics.objects.get(
            season=self.season,
            player=self.scorer,
        )
        self.assertEqual(statistics.goals_scored, 1)
        self.assertEqual(statistics.appearances, 1)

        update_match_event(
            user=self.admin,
            event_id=goal.pk,
            values={
                'event_type': MatchEvent.EventType.YELLOW_CARD,
            },
        )
        statistics.refresh_from_db()
        self.assertEqual(statistics.goals_scored, 0)
        self.assertEqual(statistics.yellow_cards, 1)
        self.match.refresh_from_db()
        self.assertEqual((self.match.home_score, self.match.away_score), (0, 0))
        home_standing = TeamStandings.objects.get(
            session=self.season,
            team=self.home,
        )
        self.assertEqual(
            (home_standing.drawn, home_standing.points),
            (1, 1),
        )
        self.assertEqual(
            TeamStandings.objects.get(
                session=self.season,
                team=self.away,
            ).points,
            1,
        )

    def test_player_statistics_endpoint_is_public_read_only_and_season_scoped(self):
        PlayerSeasonStatistics.objects.create(
            player=self.scorer,
            season=self.season,
            appearances=1,
            goals_scored=1,
        )

        response = self.client.get(
            reverse('statistics:player_statistics'),
            {'season_id': self.season.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['season']['id'], self.season.pk)
        self.assertEqual(len(response.json()['players']), 1)
        self.assertEqual(response.json()['players'][0]['goals'], 1)
        self.assertEqual(
            self.client.post(
                reverse('statistics:player_statistics'),
                data={'season_id': self.season.pk},
            ).status_code,
            405,
        )

    def test_cancelled_match_performance_does_not_count(self):
        cancelled = Match.objects.create(
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            kickoff_time=timezone.make_aware(
                datetime(2026, 11, 21, 15, 0)
            ),
            status=Match.Status.CANCELLED,
        )
        performance = PlayerMatchPerformance(
            match=cancelled,
            player=self.scorer,
            appeared=True,
            minutes_played=90,
            goals_scored=4,
        )
        performance.full_clean()
        performance.save()

        recalculate_player_season_statistics(
            user=self.admin,
            season_id=self.season.pk,
        )

        self.assertFalse(
            PlayerSeasonStatistics.objects.filter(
                season=self.season,
                player=self.scorer,
            ).exists()
        )

    def test_incomplete_and_postponed_matches_do_not_count(self):
        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 12)
        transition_match(
            user=self.official,
            match_id=self.match.pk,
            status=Match.Status.POSTPONED,
        )

        recalculate_player_season_statistics(
            user=self.admin,
            season_id=self.season.pk,
        )
        self.assertFalse(
            PlayerSeasonStatistics.objects.filter(
                season=self.season,
                player=self.scorer,
                appearances__gt=0,
            ).exists()
        )
        self.assertFalse(
            PlayerMatchPerformance.objects.filter(
                match=self.match,
                player=self.scorer,
            ).exists()
        )

    def test_statistics_recalculation_requires_league_admin(self):
        with self.assertRaises(PermissionDenied):
            recalculate_player_season_statistics(
                user=self.manager,
                season_id=self.season.pk,
            )
        with self.assertRaises(PermissionDenied):
            recalculate_player_season_statistics(
                user=self.unassigned_official,
                season_id=self.season.pk,
            )
        with self.assertRaises(PermissionDenied):
            recalculate_completed_match_statistics(
                user=self.official,
                match_id=self.match.pk,
            )

    def test_team_manager_cannot_record_verified_performance(self):
        with self.assertRaises(PermissionDenied):
            record_match_performance(
                user=self.manager,
                match_id=self.match.pk,
                player_id=self.scorer.pk,
                values={'assists': 1},
            )

    def test_match_official_cannot_edit_completed_performance_in_admin(self):
        self.match.status = Match.Status.COMPLETED
        self.match.home_score = 0
        self.match.away_score = 0
        self.match.save()
        performance = PlayerMatchPerformance.objects.create(
            match=self.match,
            player=self.scorer,
            appeared=True,
            minutes_played=90,
        )
        request = RequestFactory().get('/admin/')
        request.user = self.official
        model_admin = PlayerMatchPerformanceAdmin(
            PlayerMatchPerformance,
            admin.site,
        )

        self.assertFalse(
            model_admin.has_change_permission(request, performance)
        )
        with self.assertRaises(PermissionDenied):
            record_match_performance(
                user=self.official,
                match_id=self.match.pk,
                player_id=self.scorer.pk,
                values={'assists': 1},
            )

    def test_event_derived_fields_cannot_be_forged_in_performance_service(self):
        self.start_match()
        with self.assertRaises(ValidationError):
            record_match_performance(
                user=self.official,
                match_id=self.match.pk,
                player_id=self.scorer.pk,
                values={'goals_scored': 99},
            )
        self.assertFalse(
            PlayerMatchPerformance.objects.filter(
                match=self.match,
                player=self.scorer,
            ).exists()
        )

    def test_appearance_requires_positive_minutes_and_clean_sheet_requires_appearance(self):
        self.start_match()
        with self.assertRaises(ValidationError):
            record_match_performance(
                user=self.official,
                match_id=self.match.pk,
                player_id=self.scorer.pk,
                values={'appeared': True},
            )
        with self.assertRaises(ValidationError):
            record_match_performance(
                user=self.official,
                match_id=self.match.pk,
                player_id=self.goalkeeper.pk,
                values={'minutes_played': 90},
            )
        with self.assertRaises(ValidationError):
            record_match_performance(
                user=self.official,
                match_id=self.match.pk,
                player_id=self.goalkeeper.pk,
                values={'clean_sheet': True},
            )
        self.assertFalse(
            PlayerMatchPerformance.objects.filter(match=self.match).exists()
        )

    def test_player_transfer_keeps_performance_in_historical_season_totals(self):
        target = Team.objects.create(name='Statistics Transfer Team')
        register_team_for_season(
            user=self.admin,
            team_id=target.pk,
            season_id=self.season.pk,
        )
        PlayerRegistration.objects.filter(
            player=self.scorer,
            season=self.season,
        ).update(end_date=date(2026, 11, 20))
        PlayerRegistration.objects.create(
            player=self.scorer,
            team=target,
            season=self.season,
            start_date=date(2026, 11, 21),
        )
        after_transfer_match = self.make_match(
            self.season,
            target,
            self.away,
            datetime(2026, 11, 22, 15, 0),
        )
        assign_match_official(
            user=self.admin,
            match_id=after_transfer_match.pk,
            official_user_id=self.official.pk,
            role=MatchOfficial.Role.REFEREE,
        )

        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 12)
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.scorer.pk,
            values={'appeared': True, 'minutes_played': 90},
        )
        self.complete_match()
        transition_match(
            user=self.official,
            match_id=after_transfer_match.pk,
            status=Match.Status.LIVE,
        )
        create_match_event(
            user=self.official,
            match_id=after_transfer_match.pk,
            values={
                'event_type': MatchEvent.EventType.GOAL,
                'player': self.scorer,
                'minute': 17,
                'added_time': 0,
                'description': '',
            },
        )
        record_match_performance(
            user=self.official,
            match_id=after_transfer_match.pk,
            player_id=self.scorer.pk,
            values={'appeared': True, 'minutes_played': 90},
        )
        transition_match(
            user=self.official,
            match_id=after_transfer_match.pk,
            status=Match.Status.COMPLETED,
        )

        statistics = PlayerSeasonStatistics.objects.get(
            season=self.season,
            player=self.scorer,
        )
        self.assertEqual(statistics.appearances, 2)
        self.assertEqual(statistics.goals_scored, 2)
        self.assertEqual(
            PlayerMatchPerformance.objects.filter(
                player=self.scorer,
                match__season=self.season,
            ).count(),
            2,
        )

    def test_player_statistics_are_separate_between_seasons(self):
        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 12)
        record_match_performance(
            user=self.official,
            match_id=self.match.pk,
            player_id=self.scorer.pk,
            values={'appeared': True, 'minutes_played': 90},
        )
        self.complete_match()

        next_season = Season.objects.create(
            name='Statistics Season 2027',
            year=2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )
        for team in (self.home, self.away):
            register_team_for_season(
                user=self.admin,
                team_id=team.pk,
                season_id=next_season.pk,
            )
        PlayerRegistration.objects.create(
            player=self.scorer,
            team=self.home,
            season=next_season,
            start_date=next_season.start_date,
        )
        next_match = self.make_match(
            next_season,
            self.home,
            self.away,
            datetime(2027, 2, 1, 15, 0),
        )
        assign_match_official(
            user=self.admin,
            match_id=next_match.pk,
            official_user_id=self.official.pk,
            role=MatchOfficial.Role.REFEREE,
        )
        transition_match(
            user=self.official,
            match_id=next_match.pk,
            status=Match.Status.LIVE,
        )
        create_match_event(
            user=self.official,
            match_id=next_match.pk,
            values={
                'event_type': MatchEvent.EventType.GOAL,
                'player': self.scorer,
                'minute': 12,
                'added_time': 0,
                'description': '',
            },
        )
        record_match_performance(
            user=self.official,
            match_id=next_match.pk,
            player_id=self.scorer.pk,
            values={'appeared': True, 'minutes_played': 90},
        )
        transition_match(
            user=self.official,
            match_id=next_match.pk,
            status=Match.Status.COMPLETED,
        )

        self.assertEqual(
            PlayerSeasonStatistics.objects.get(
                player=self.scorer,
                season=self.season,
            ).goals_scored,
            1,
        )
        self.assertEqual(
            PlayerSeasonStatistics.objects.get(
                player=self.scorer,
                season=next_season,
            ).goals_scored,
            1,
        )

    def test_completion_rolls_back_if_statistics_rebuild_fails(self):
        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 12)
        self.match.refresh_from_db()
        scores_before = (self.match.home_score, self.match.away_score)
        with patch(
            'apps.statistics.services._rebuild_season_statistics',
            side_effect=RuntimeError('simulated statistics failure'),
        ):
            with self.assertRaises(RuntimeError):
                self.complete_match()

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.LIVE)
        self.assertEqual(
            (self.match.home_score, self.match.away_score),
            scores_before,
        )
        self.assertFalse(
            PlayerMatchPerformance.objects.filter(match=self.match).exists()
        )

    def test_completion_rolls_back_if_standings_rebuild_fails(self):
        self.start_match()
        self.record_event(self.scorer, MatchEvent.EventType.GOAL, 12)
        with patch(
            'apps.standings.services._calculate_season_standings',
            side_effect=RuntimeError('simulated standings failure'),
        ):
            with self.assertRaises(RuntimeError):
                self.complete_match()

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.LIVE)
        self.assertFalse(
            PlayerMatchPerformance.objects.filter(match=self.match).exists()
        )
        self.assertFalse(
            PlayerSeasonStatistics.objects.filter(season=self.season).exists()
        )
        self.assertFalse(
            TeamStandings.objects.filter(session=self.season).exists()
        )

    def test_completed_event_correction_rolls_back_as_one_operation(self):
        self.start_match()
        goal = self.record_event(
            self.scorer,
            MatchEvent.EventType.GOAL,
            12,
        )
        self.complete_match()
        with patch(
            'apps.statistics.services._rebuild_season_statistics',
            side_effect=RuntimeError('simulated statistics failure'),
        ):
            with self.assertRaises(RuntimeError):
                update_match_event(
                    user=self.admin,
                    event_id=goal.pk,
                    values={
                        'event_type': MatchEvent.EventType.YELLOW_CARD,
                    },
                )

        goal.refresh_from_db()
        self.match.refresh_from_db()
        self.assertEqual(goal.event_type, MatchEvent.EventType.GOAL)
        self.assertEqual((self.match.home_score, self.match.away_score), (1, 0))
