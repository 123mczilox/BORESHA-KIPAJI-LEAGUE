
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import UserProfile
from django.contrib.auth.models import Group
from apps.accounts.permissions import (
    has_role,
    is_league_admin,
    is_match_official,
    is_team_manager,
    is_fantasy_manager,
    is_content_manager,
)
from apps.accounts.permissions import can_manage_team
from apps.teams.models import Team, TeamManagerAssignment
User = get_user_model()


class RegistrationTests(TestCase):

    def test_user_can_register_successfully(self):
        """A visitor should be able to create an account."""

        response = self.client.post(
            reverse('register'),
            {
                'username': 'newuser',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }
        )

        self.assertRedirects(response, reverse('login'))

        self.assertTrue(
            User.objects.filter(username='newuser').exists()
        )

    def test_registration_creates_user_profile(self):
        """Every newly registered user should receive a profile."""

        self.client.post(
            reverse('register'),
            {
                'username': 'profileuser',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'email': 'jane@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }
        )

        user = User.objects.get(username='profileuser')

        self.assertTrue(
            UserProfile.objects.filter(user=user).exists()
        )

    def test_duplicate_email_is_rejected(self):
        """A user should not register with an existing email."""

        User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='StrongPass123!'
        )

        response = self.client.post(
            reverse('register'),
            {
                'username': 'anotheruser',
                'first_name': 'Another',
                'last_name': 'User',
                'email': 'existing@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            User.objects.filter(username='anotheruser').exists()
        )
        
class LoginLogoutTests(TestCase):

    def setUp(self):
        """Create a test user before each test."""

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='StrongPass123!'
        )

    def test_user_can_login(self):
        """A user with correct credentials should log in."""

        response = self.client.post(
            reverse('login'),
            {
                'username': 'testuser',
                'password': 'StrongPass123!',
            }
        )

        self.assertRedirects(response, reverse('login'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_fails_with_wrong_password(self):
        """Incorrect credentials should not authenticate the user."""

        response = self.client.post(
            reverse('login'),
            {
                'username': 'testuser',
                'password': 'WrongPassword123!',
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_user_can_logout(self):
        """An authenticated user should be able to log out."""

        self.client.force_login(self.user)

        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('login'))

        response = self.client.get(reverse('login'))

        self.assertFalse(response.wsgi_request.user.is_authenticated)        

class RolePermissionTests(TestCase):

    def setUp(self):
        """Create a normal user and the required role groups."""

        self.user = User.objects.create_user(
            username='role_test_user',
            email='role@example.com',
            password='StrongPass123!'
        )

        self.fantasy_group, _ = Group.objects.get_or_create(
            name='Fantasy Manager'
        )

        self.user.groups.add(self.fantasy_group)

    def test_user_has_assigned_role(self):
        self.assertTrue(
            has_role(self.user, 'Fantasy Manager')
        )

    def test_user_does_not_have_unassigned_roles(self):
        self.assertFalse(is_league_admin(self.user))
        self.assertFalse(is_match_official(self.user))
        self.assertFalse(is_team_manager(self.user))
        self.assertFalse(is_content_manager(self.user))

    def test_fantasy_manager_role_is_recognized(self):
        self.assertTrue(is_fantasy_manager(self.user))

    def test_ordinary_user_is_not_superuser(self):
        self.assertFalse(self.user.is_superuser)

    def test_superuser_passes_all_role_checks(self):
        admin = User.objects.create_superuser(
            username='superadmin',
            email='admin@example.com',
            password='StrongPass123!'
        )

        self.assertTrue(is_league_admin(admin))
        self.assertTrue(is_match_official(admin))
        self.assertTrue(is_team_manager(admin))
        self.assertTrue(is_fantasy_manager(admin))
        self.assertTrue(is_content_manager(admin))        
    
class TeamPermissionTests(TestCase):

    def setUp(self):
        """Create two teams and a manager assigned to only one."""

        self.manager = User.objects.create_user(
            username='team_manager',
            email='manager@example.com',
            password='StrongPass123!'
        )

        self.team_manager_group, _ = Group.objects.get_or_create(
            name='Team Manager'
        )

        self.manager.groups.add(self.team_manager_group)

        self.team_a = Team.objects.create(
            name='Nairobi Stars',
            short_name='NST',
            county='Nairobi'
        )

        self.team_b = Team.objects.create(
            name='Mombasa United',
            short_name='MU',
            county='Mombasa'
        )

        self.assignment = TeamManagerAssignment.objects.create(
            user=self.manager,
            team=self.team_a,
            is_active=True
        )

    def test_manager_can_manage_assigned_team(self):
        self.assertTrue(
            can_manage_team(self.manager, self.team_a)
        )

    def test_manager_cannot_manage_unassigned_team(self):
        self.assertFalse(
            can_manage_team(self.manager, self.team_b)
        )

    def test_inactive_assignment_does_not_grant_access(self):
        self.assignment.is_active = False
        self.assignment.save()

        self.assertFalse(
            can_manage_team(self.manager, self.team_a)
        )

    def test_user_without_team_manager_role_cannot_manage_team(self):
        ordinary_user = User.objects.create_user(
            username='ordinary_user',
            email='ordinary@example.com',
            password='StrongPass123!'
        )

        self.assertFalse(
            can_manage_team(ordinary_user, self.team_a)
        )        