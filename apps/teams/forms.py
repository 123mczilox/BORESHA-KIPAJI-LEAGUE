from django import forms
from .models import Team

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = [
            'name', 
            'short_name', 
            'county',
            'description', 
            'founded_year', 
            'is_active'
            ]
        
        widgets = {
            'name':forms.TextInput(attrs={
                'class':'form-control',
                'placeholder':'Enter team name',
            }),
            'short_name':forms.TextInput(attrs={
                'class':'form-control',
                'placeholder':'Enter team short name',
            }),
            'county':forms.TextInput(attrs={
                'class':'form-control',
                'placeholder':'Enter team county',
            }),
            'description':forms.Textarea(attrs={
                'class':'form-control',
                'rows':4,
                'placeholder':'Enter team description',
            }),
            'founded_year':forms.NumberInput(attrs={
                'class':'form-control',
                'placeholder':'Enter team founded year',
            }),
            'is_active':forms.CheckboxInput(attrs={
                'class':'form-check-input',
            }),
        }
    
    def clean_name(self):
        name = self.cleaned_data['name']

        # Remove unnecessary spaces
        name = ' '.join(name.split())

        # Prevent duplicate names, ignoring letter case
        existing_team = Team.objects.filter(name__iexact=name)

        if self.instance.pk:
            existing_team = existing_team.exclude(pk=self.instance.pk)

        if existing_team.exists():
            raise forms.ValidationError(
                'A team with this name already exists.'
            )

        return name

    def clean_short_name(self):
        short_name = self.cleaned_data.get('short_name', '')

        return short_name.strip().upper()

    def clean_founded_year(self):
        founded_year = self.cleaned_data.get('founded_year')

        if founded_year is not None:
            from datetime import date

            current_year = date.today().year

            if founded_year < 1800 or founded_year > current_year:
                raise forms.ValidationError(
                    f'Enter a year between 1800 and {current_year}.'
                )

        return founded_year

class TeamManagerForm(forms.ModelForm):
    """
    Limited form for managers editing their assigned teams.
    """

    class Meta:
        model = Team

        fields = [
            'short_name',
            'description',
        ]

        widgets = {
            'short_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter team short name',
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter team description',
            }),
        }

    def clean_short_name(self):
        short_name = self.cleaned_data.get('short_name', '')
        return short_name.strip().upper()    