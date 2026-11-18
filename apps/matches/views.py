import json
from json import JSONDecodeError

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import (
    can_manage_match,
    can_view_match,
    is_league_admin,
    is_match_official,
    is_team_manager,
)

from .forms import (
    MatchEventForm,
    MatchFixtureForm,
    MatchOfficialAssignmentForm,
)
from .models import Match, MatchEvent, MatchOfficial
from .services import (
    assign_match_official,
    create_fixture,
    create_match_event,
    delete_match_event,
    remove_match_official,
    transition_match,
    update_fixture,
    update_match_event,
)


def _json_body(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except (JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _payload_error():
    return JsonResponse(
        {'errors': {'__all__': ['A JSON object is required.']}},
        status=400,
    )


def _form_errors(form):
    return JsonResponse({'errors': form.errors.get_json_data()}, status=400)


def _validation_error(error):
    return JsonResponse({'errors': error.messages}, status=400)


def _reject_unexpected_fields(data, allowed_fields):
    unexpected = set(data) - set(allowed_fields)
    if not unexpected:
        return None
    return JsonResponse(
        {
            'errors': {
                '__all__': [
                    'Unexpected fields: ' + ', '.join(sorted(unexpected))
                ]
            }
        },
        status=400,
    )


def _require_authenticated(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)
    return None


def _require_match_viewer(request):
    if not (
        is_league_admin(request.user)
        or is_match_official(request.user)
        or is_team_manager(request.user)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    return None


def _match_data(match):
    return {
        'id': match.pk,
        'season': {'id': match.season_id, 'name': match.season.name},
        'home_team': {'id': match.home_team_id, 'name': match.home_team.name},
        'away_team': {'id': match.away_team_id, 'name': match.away_team.name},
        'matchweek': match.matchweek,
        'kickoff_time': match.kickoff_time.isoformat(),
        'venue': match.venue,
        'status': match.status,
        'started_at': (
            match.started_at.isoformat() if match.started_at else None
        ),
        'home_score': match.home_score,
        'away_score': match.away_score,
    }


def _event_data(event):
    return {
        'id': event.pk,
        'match': event.match_id,
        'event_type': event.event_type,
        'player': {'id': event.player_id, 'name': str(event.player)},
        'related_player': (
            {
                'id': event.related_player_id,
                'name': str(event.related_player),
            }
            if event.related_player_id else None
        ),
        'minute': event.minute,
        'added_time': event.added_time,
        'description': event.description,
    }


@require_http_methods(['GET', 'POST'])
def match_list_create(request):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    role_error = _require_match_viewer(request)
    if role_error:
        return role_error

    if request.method == 'GET':
        matches = Match.objects.select_related(
            'season',
            'home_team',
            'away_team',
        )
        if not is_league_admin(request.user):
            if is_match_official(request.user):
                matches = matches.filter(officials__user=request.user)
            elif is_team_manager(request.user):
                from django.db.models import Q

                matches = matches.filter(
                    Q(
                        home_team__manager_assignments__user=request.user,
                        home_team__manager_assignments__is_active=True,
                    )
                    | Q(
                        away_team__manager_assignments__user=request.user,
                        away_team__manager_assignments__is_active=True,
                    )
                )
        return JsonResponse(
            {'matches': [_match_data(match) for match in matches.distinct()]},
        )

    if not is_league_admin(request.user):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        (
            'season',
            'home_team',
            'away_team',
            'matchweek',
            'kickoff_time',
            'venue',
        ),
    )
    if extra_fields:
        return extra_fields
    form = MatchFixtureForm(data)
    if not form.is_valid():
        return _form_errors(form)
    try:
        match = create_fixture(user=request.user, values=form.cleaned_data)
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_match_data(match), status=201)


@require_http_methods(['GET', 'PATCH'])
def match_detail(request, match_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    match = get_object_or_404(
        Match.objects.select_related('season', 'home_team', 'away_team'),
        pk=match_id,
    )
    if request.method == 'GET':
        if not can_view_match(request.user, match):
            return JsonResponse({'detail': 'Permission denied.'}, status=403)
        return JsonResponse(_match_data(match))

    if not is_league_admin(request.user):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        (
            'season',
            'home_team',
            'away_team',
            'matchweek',
            'kickoff_time',
            'venue',
        ),
    )
    if extra_fields:
        return extra_fields
    merged = {
        'season': match.season_id,
        'home_team': match.home_team_id,
        'away_team': match.away_team_id,
        'matchweek': match.matchweek,
        'kickoff_time': match.kickoff_time.isoformat(),
        'venue': match.venue,
    }
    merged.update(data)
    form = MatchFixtureForm(merged, instance=match)
    if not form.is_valid():
        return _form_errors(form)
    try:
        match = update_fixture(
            user=request.user,
            match_id=match.pk,
            values=form.cleaned_data,
        )
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_match_data(match))


@require_http_methods(['POST'])
def match_lifecycle(request, match_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    match = get_object_or_404(Match, pk=match_id)
    if not (
        is_league_admin(request.user)
        or can_manage_match(request.user, match)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        ('status', 'home_score', 'away_score'),
    )
    if extra_fields:
        return extra_fields
    try:
        match = transition_match(
            user=request.user,
            match_id=match.pk,
            status=data.get('status'),
            home_score=data.get('home_score'),
            away_score=data.get('away_score'),
        )
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_match_data(match))


@require_http_methods(['GET', 'POST'])
def match_officials(request, match_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    match = get_object_or_404(Match, pk=match_id)
    if request.method == 'GET':
        if not (
            is_league_admin(request.user)
            or can_manage_match(request.user, match)
        ):
            return JsonResponse({'detail': 'Permission denied.'}, status=403)
        assignments = match.officials.select_related('user').order_by('pk')
        return JsonResponse({
            'officials': [
                {
                    'id': assignment.pk,
                    'user_id': assignment.user_id,
                    'username': assignment.user.get_username(),
                    'role': assignment.role,
                }
                for assignment in assignments
            ],
        })

    if not is_league_admin(request.user):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        ('user', 'role'),
    )
    if extra_fields:
        return extra_fields
    form = MatchOfficialAssignmentForm(data)
    if not form.is_valid():
        return _form_errors(form)
    try:
        assignment = assign_match_official(
            user=request.user,
            match_id=match.pk,
            official_user_id=form.cleaned_data['user'].pk,
            role=form.cleaned_data['role'],
        )
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(
        {
            'id': assignment.pk,
            'user_id': assignment.user_id,
            'role': assignment.role,
        },
        status=201,
    )


@require_http_methods(['DELETE'])
def match_official_remove(request, assignment_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    if not is_league_admin(request.user):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    get_object_or_404(MatchOfficial, pk=assignment_id)
    try:
        remove_match_official(user=request.user, assignment_id=assignment_id)
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse({}, status=200)


@require_http_methods(['GET', 'POST'])
def match_events(request, match_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    match = get_object_or_404(Match, pk=match_id)
    if request.method == 'GET':
        if not (
            is_league_admin(request.user)
            or can_manage_match(request.user, match)
        ):
            return JsonResponse({'detail': 'Permission denied.'}, status=403)
        events = match.events.select_related(
            'player',
            'related_player',
        ).order_by('minute', 'added_time', 'pk')
        return JsonResponse(
            {'events': [_event_data(event) for event in events]},
        )

    if not (
        is_league_admin(request.user)
        or can_manage_match(request.user, match)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    if (
        match.status == Match.Status.COMPLETED
        and not is_league_admin(request.user)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        (
            'event_type',
            'player',
            'related_player',
            'minute',
            'added_time',
            'description',
        ),
    )
    if extra_fields:
        return extra_fields
    form = MatchEventForm(data, match=match)
    if not form.is_valid():
        return _form_errors(form)
    try:
        event = create_match_event(
            user=request.user,
            match_id=match.pk,
            values=form.cleaned_data,
        )
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_event_data(event), status=201)


@require_http_methods(['PATCH', 'DELETE'])
def match_event_detail(request, event_id):
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error
    event = get_object_or_404(
        MatchEvent.objects.select_related('match', 'player', 'related_player'),
        pk=event_id,
    )
    if request.method == 'DELETE':
        if not is_league_admin(request.user):
            return JsonResponse({'detail': 'Permission denied.'}, status=403)
        try:
            delete_match_event(user=request.user, event_id=event.pk)
        except ValidationError as error:
            return _validation_error(error)
        return JsonResponse({}, status=200)

    if not (
        is_league_admin(request.user)
        or can_manage_match(request.user, event.match)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    if (
        event.match.status == Match.Status.COMPLETED
        and not is_league_admin(request.user)
    ):
        return JsonResponse({'detail': 'Permission denied.'}, status=403)
    data = _json_body(request)
    if data is None:
        return _payload_error()
    extra_fields = _reject_unexpected_fields(
        data,
        (
            'event_type',
            'player',
            'related_player',
            'minute',
            'added_time',
            'description',
        ),
    )
    if extra_fields:
        return extra_fields
    merged = {
        'event_type': event.event_type,
        'player': event.player_id,
        'related_player': event.related_player_id,
        'minute': event.minute,
        'added_time': event.added_time,
        'description': event.description,
    }
    merged.update(data)
    form = MatchEventForm(merged, match=event.match, instance=event)
    if not form.is_valid():
        return _form_errors(form)
    try:
        event = update_match_event(
            user=request.user,
            event_id=event.pk,
            values=form.cleaned_data,
        )
    except ValidationError as error:
        return _validation_error(error)
    return JsonResponse(_event_data(event))
