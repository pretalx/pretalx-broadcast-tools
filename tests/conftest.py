import datetime as dt

import pytest
from django.core import management
from django_scopes import scopes_disabled
from pretalx.event.domain.event import initialise_event
from pretalx.event.domain.plugins import enable_plugin
from pretalx.event.models import Event, Organiser, Team
from pretalx.person.models import User
from pretalx.schedule.domain.release import freeze_schedule
from pretalx.schedule.models import Room, TalkSlot
from pretalx.submission.domain.submission import add_speaker
from pretalx.submission.models import (
    Answer,
    Question,
    Submission,
    SubmissionType,
    Track,
)
from pretalx.submission.models.question import QuestionTarget


@pytest.fixture(scope="session", autouse=True)
def collect_static(request):
    management.call_command("collectstatic", "--noinput", "--clear")


@pytest.fixture(autouse=True)
def isolate_htmlexport(settings, tmp_path):
    settings.HTMLEXPORT_ROOT = tmp_path / "htmlexport"
    settings.HTMLEXPORT_ROOT.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def organiser():
    with scopes_disabled():
        o = Organiser.objects.create(name="Super Organiser", slug="superorganiser")
        Team.objects.create(
            name="Organisers",
            organiser=o,
            can_create_events=True,
            can_change_teams=True,
            can_change_organiser_settings=True,
            can_change_event_settings=True,
            can_change_submissions=True,
        )
        Team.objects.create(name="Reviewers", organiser=o, is_reviewer=True)
    return o


@pytest.fixture
def event(organiser):
    today = dt.date.today()
    with scopes_disabled():
        event = Event.objects.create(
            name="Fancy testevent",
            is_public=True,
            slug="test",
            email="orga@orga.org",
            primary_color="#abcdef",
            date_from=today,
            date_to=today + dt.timedelta(days=3),
            organiser=organiser,
        )
        initialise_event(event)
        enable_plugin(event, "pretalx_broadcast_tools")
        event.save()
        for team in organiser.teams.all():
            team.limit_events.add(event)
        # Reload so I18n fields (e.g. event.name) behave like in production.
        event.refresh_from_db()
    return event


@pytest.fixture
def orga_user(event):
    with scopes_disabled():
        user = User.objects.create_user(password="orgapassw0rd", email="orgauser@orga.org", name="Orga User")
        team = event.organiser.teams.filter(can_change_organiser_settings=True, is_reviewer=False).first()
        team.members.add(user)
        team.save()
    return user


@pytest.fixture
def review_user(event):
    with scopes_disabled():
        user = User.objects.create_user(password="reviewpassw0rd", email="reviewuser@orga.org", name="Review User")
        team = event.organiser.teams.filter(can_change_organiser_settings=False, is_reviewer=True).first()
        team.members.add(user)
        team.save()
    return user


@pytest.fixture
def orga_client(orga_user, client):
    client.force_login(orga_user)
    return client


@pytest.fixture
def review_client(review_user, client):
    client.force_login(review_user)
    return client


@pytest.fixture
def room(event):
    with scopes_disabled():
        return Room.objects.create(event=event, name="Main Room", position=0)


@pytest.fixture
def track(event):
    with scopes_disabled():
        return Track.objects.create(event=event, name="Test Track", color="#ff0000")


@pytest.fixture
def submission_type(event):
    with scopes_disabled():
        sub_type = SubmissionType.objects.filter(event=event).first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=event, name="Talk", default_duration=60)
        return sub_type


@pytest.fixture
def speaker(event):
    with scopes_disabled():
        return User.objects.create_user(
            password="speakerpassw0rd",
            email="speaker@example.org",
            name="Jane Speaker",
        )


@pytest.fixture
def submission(event, submission_type, track, speaker):
    with scopes_disabled():
        sub = Submission.objects.create(
            title="A Long And Interesting Talk Title For Testing Purposes",
            event=event,
            submission_type=submission_type,
            track=track,
            content_locale="en",
            abstract="This is the abstract of the talk.",
            notes="Some notes.\n\n  \nAnother note line.",
            internal_notes="Internal note one.\n\nInternal note two.",
        )
        add_speaker(sub, user=speaker)
        sub.accept()
        sub.confirm()
        return sub


@pytest.fixture
def submission_question(event, submission):
    with scopes_disabled():
        question = Question.objects.create(
            event=event,
            question="What is your favourite colour?",
            variant="string",
            target=QuestionTarget.SUBMISSION,
            position=0,
        )
        Answer.objects.create(question=question, submission=submission, answer="Blue.")
        return question


@pytest.fixture
def speaker_question(event, submission):
    with scopes_disabled():
        question = Question.objects.create(
            event=event,
            question="How are you today?",
            variant="string",
            target=QuestionTarget.SPEAKER,
            position=1,
        )
        for profile in submission.speakers.all():
            Answer.objects.create(question=question, speaker=profile, answer="Doing great.")
        return question


@pytest.fixture
def slot(event, submission, room):
    with scopes_disabled():
        return TalkSlot.objects.create(
            submission=submission,
            schedule=event.wip_schedule,
            room=room,
            start=event.datetime_from,
            end=event.datetime_from + dt.timedelta(minutes=60),
            is_visible=True,
        )


@pytest.fixture
def schedule(event, slot):
    with scopes_disabled():
        freeze_schedule(event.wip_schedule, name="v1")
        return event.current_schedule
