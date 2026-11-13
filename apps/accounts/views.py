from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import UserRegistrationForm


def register_view(request):

    if request.method == 'POST':

        form = UserRegistrationForm(request.POST)

        if form.is_valid():

            user = form.save()

            messages.success(
                request,
                f"Welcome to Boresha Kipaji League, {user.username}! "
                "Your account has been created successfully."
            )

            return redirect('login')

    else:
        form = UserRegistrationForm()

    context = {
        'form': form,
    }

    return render(request, 'accounts/register.html', context)