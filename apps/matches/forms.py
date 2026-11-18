from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Match, MatchEvent, MatchOfficial


class MatchFixtureForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = (
            'season',
            'home_team',
            'away_team',
            'matchweek',
            'kickoff_time',
            'venue',
        )
        widgets = {
            'kickoff_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }


class MatchOfficialAssignmentForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(
            Q(groups__name='Match Official') | Q(is_superuser=True),
        ).distinct(),
    )
    role = forms.ChoiceField(choices=MatchOfficial.Role.choices)


class MatchEventForm(forms.ModelForm):
    class Meta:
        model = MatchEvent
        fields = (
            'event_type',
            'player',
            'related_player',
            'minute',
            'added_time',
            'description',
        )

    def __init__(self, *args, match, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.match = match
