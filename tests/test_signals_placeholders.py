import pytest
from django.urls import resolve, reverse
from django_scopes import scope, scopes_disabled

from pretalx_broadcast_tools.exporter import PDFExporter
from pretalx_broadcast_tools.signals import navbar_info, register_data_exporter
from pretalx_broadcast_tools.utils.placeholders import placeholders


@pytest.mark.django_db
def test_navbar_info_for_orga(orga_user, event):
    orga_url = reverse("plugins:pretalx_broadcast_tools:orga", kwargs={"event": event.slug})

    class FakeRequest:
        user = orga_user
        path_info = orga_url

    FakeRequest.event = event
    with scopes_disabled():
        result = navbar_info(sender=event, request=FakeRequest())
    assert len(result) == 1
    assert result[0]["active"] is True
    assert result[0]["url"] == orga_url


@pytest.mark.django_db
def test_navbar_info_inactive(orga_user, event):
    other_url = reverse("orga:event.dashboard", kwargs={"event": event.slug})

    class FakeRequest:
        user = orga_user
        path_info = other_url

    FakeRequest.event = event
    resolve(other_url)
    with scopes_disabled():
        result = navbar_info(sender=event, request=FakeRequest())
    assert len(result) == 1
    assert result[0]["active"] is False


@pytest.mark.django_db
def test_navbar_info_no_permission(review_user, event):
    orga_url = reverse("plugins:pretalx_broadcast_tools:orga", kwargs={"event": event.slug})

    class FakeRequest:
        user = review_user
        path_info = orga_url

    FakeRequest.event = event
    with scopes_disabled():
        result = navbar_info(sender=event, request=FakeRequest())
    assert result == []


@pytest.mark.django_db
def test_register_data_exporter(event):
    assert register_data_exporter(sender=event) is PDFExporter


@pytest.mark.django_db
def test_placeholders_with_track_html(event, submission, schedule):
    with scope(event=event):
        talk = event.current_schedule.talks.first()
        result = placeholders(event, talk, supports_html_colour=True)
    assert result["CODE"] == submission.code
    assert result["EVENT_SLUG"] == event.slug
    assert "<span" in result["TRACK_NAME_COLOURED"]
    assert result["TRACK_NAME_COLORED"] == result["TRACK_NAME_COLOURED"]


@pytest.mark.django_db
def test_placeholders_with_track_no_html(event, submission, schedule):
    with scope(event=event):
        talk = event.current_schedule.talks.first()
        result = placeholders(event, talk, supports_html_colour=False)
    assert result["TRACK_NAME_COLOURED"] == "Test Track"


@pytest.mark.django_db
def test_placeholders_without_track(event, room, submission_type):
    from pretalx.schedule.domain.release import freeze_schedule
    from pretalx.schedule.models import TalkSlot
    from pretalx.submission.models import Submission

    with scopes_disabled():
        sub = Submission.objects.create(
            title="No track",
            event=event,
            submission_type=submission_type,
            content_locale="en",
        )
        sub.accept()
        sub.confirm()
        TalkSlot.objects.create(
            submission=sub,
            schedule=event.wip_schedule,
            room=room,
            start=event.datetime_from,
            end=event.datetime_from,
            is_visible=True,
        )
        freeze_schedule(event.wip_schedule, name="v1")
    with scope(event=event):
        talk = event.current_schedule.talks.first()
        result = placeholders(event, talk, supports_html_colour=True)
    assert result["TRACK_NAME"] == ""
    assert result["TRACK_NAME_COLOURED"] == ""
