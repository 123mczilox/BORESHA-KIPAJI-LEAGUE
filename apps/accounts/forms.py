# from django import forms
# from django.contrib.auth.forms import UserCreationForm
# from .models import User

# class UserRegistrationForm(UserCreationForm):
#     email = forms.EmailField(
#         required=True,
#         # widget=forms.EmailInput(attrs={'class': 'form-control'}),
#         help_text='Required. Enter a valid email address.'
#     )
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
    
#         for field in self.fields.values():
#             field.widget.attrs.update({
#                 'class': (
#                     'w-full rounded-lg border border-gray-300 '
#                     'px-4 py-3 text-gray-900 outline-none '
#                     'focus:border-green-700 focus:ring-2 '
#                     'focus:ring-green-100'
#                 )
#             })
    
#     class Meta:
#         model = User
#         fields = [
#             'username',
#             'first_name',
#             'last_name',
#             'email',
            
#             ]
       
        
#     def clean_email(self):
#         email = self.cleaned_data.get('email')
#         if User.objects.filter(email__iexact=email).exists():
#             raise forms.ValidationError(
#                 "An account with this email already exists. Please use a different email address."
#             )
#         return email    
    
    
    
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class UserRegistrationForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        help_text='Required. Enter a valid email address.'
    )

    class Meta:
        model = User

        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': (
                    'w-full rounded-lg border border-gray-300 '
                    'px-4 py-3 text-gray-900 outline-none '
                    'focus:border-green-700 focus:ring-2 '
                    'focus:ring-green-100'
                )
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )

        return email    