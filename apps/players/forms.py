from django import forms
from django.utils import timezone

from apps.accounts.permissions import (
    is_league_admin,
    is_team_manager,
    visible_players_for_user,
)
from apps.matches.models import Season
from apps.teams.models import Team

from .models import Player, PlayerRegistration


class PlayerCreateForm(forms.ModelForm):
    team = forms.ModelChoiceField(queryset=Team.objects.none())
    season = forms.ModelChoiceField(queryset=Season.objects.none())
    shirt_number = forms.IntegerField(
        min_value=1,
        required=False,
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = Player
        fields = (
            'first_name',
            'last_name',
            'date_of_birth',
            'position',
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['start_date'].initial = timezone.localdate()

        if is_league_admin(user):
            self.fields['team'].queryset = Team.objects.filter(
                is_active=True
            ).order_by('name')
        elif is_team_manager(user):
            self.fields['team'].queryset = Team.objects.filter(
                is_active=True,
                manager_assignments__user=user,
                manager_assignments__is_active=True,
            ).distinct().order_by('name')

        self.fields['season'].queryset = Season.objects.order_by('-year')


class PlayerEditForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = (
            'first_name',
            'last_name',
            'date_of_birth',
            'position',
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }


class PlayerRegistrationForm(forms.ModelForm):
    class Meta:
        model = PlayerRegistration
        fields = (
            'player',
            'team',
            'season',
            'shirt_number',
            'start_date',
            'end_date',
        )
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user is None:
            return

        self.fields['player'].queryset = visible_players_for_user(user)
        self.fields['season'].queryset = Season.objects.order_by('-year')

        if is_league_admin(user):
            self.fields['team'].queryset = Team.objects.order_by('name')
        elif is_team_manager(user):
            self.fields['team'].queryset = Team.objects.filter(
                is_active=True,
                manager_assignments__user=user,
                manager_assignments__is_active=True,
            ).distinct().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        team = cleaned_data.get('team')

        if (
            self.user is not None
            and
            team
            and not self.fields['team'].queryset.filter(pk=team.pk).exists()
        ):
            self.add_error('team', 'You cannot register players to this team.')

        return cleaned_data


class PlayerTransferForm(forms.Form):
    team = forms.ModelChoiceField(queryset=Team.objects.none())
    shirt_number = forms.IntegerField(
        min_value=1,
        required=False,
    )
    transfer_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, user, source_team, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.source_team = source_team
        self.fields['transfer_date'].initial = timezone.localdate()

        if is_league_admin(user):
            self.fields['team'].queryset = Team.objects.filter(
                is_active=True
            ).exclude(pk=source_team.pk).order_by('name')
        elif is_team_manager(user):
            self.fields['team'].queryset = Team.objects.filter(
                is_active=True,
                manager_assignments__user=user,
                manager_assignments__is_active=True,
            ).exclude(pk=source_team.pk).distinct().order_by('name')
        else:
            self.fields['team'].queryset = Team.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        target_team = cleaned_data.get('team')
        if target_team and target_team.pk == self.source_team.pk:
            self.add_error(
                'team',
                'A transfer must be to a different team.',
            )
        return cleaned_data
