import datetime as dt

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString
from pretalx.schedule.domain.release import freeze_schedule
from pretalx.schedule.enums import SlotType
from pretalx.schedule.models import TalkSlot
from pretalx.submission.models import Submission

from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (
    VoctomixLowerThirdsExporter,
    get_export_path,
    get_export_targz_path,
)


@pytest.mark.django_db
def test_command_success(event, submission, schedule):
    with scopes_disabled():
        event.settings.broadcast_tools_lower_thirds_info_string = LazyI18nString(
            "Code: {CODE} long-info-line-to-render"
        )
    targz_path = get_export_targz_path(event)
    targz_path.parent.mkdir(parents=True, exist_ok=True)
    targz_path.with_suffix(".tmp").write_bytes(b"stale")
    call_command("export_voctomix_lower_thirds", event.slug)
    assert targz_path.exists()
    # source files were cleaned up by default
    assert not get_export_path(event).exists()


@pytest.mark.django_db
def test_command_keep_source_files(event, submission, schedule):
    call_command("export_voctomix_lower_thirds", event.slug, "--no-delete-source-files")
    assert get_export_path(event).exists()


@pytest.mark.django_db
def test_command_event_not_found(event):
    with pytest.raises(CommandError):
        call_command("export_voctomix_lower_thirds", "does-not-exist")


@pytest.mark.django_db
def test_command_no_schedule_logs_exception(event, caplog):
    # No schedule -> exporter raises CommandError, caught and logged.
    call_command("export_voctomix_lower_thirds", event.slug)
    assert not get_export_targz_path(event).exists()


@pytest.mark.django_db
def test_exporter_without_primary_color(event, submission, schedule, tmp_path):
    with scopes_disabled():
        event.primary_color = None
        event.save()
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        # Falls back to the default colour and a full export still works.
        assert exporter.primary_colour == (58, 165, 124)
        result = exporter.export()
    assert len(result) >= 1


@pytest.mark.django_db
def test_exporter_export_no_schedule(event, tmp_path):
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        with pytest.raises(CommandError):
            exporter.export()


@pytest.mark.django_db
def test_exporter_duplicate_slot(event, submission, schedule, tmp_path):
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        for talk in event.current_schedule.talks.filter(is_visible=True):
            exporter.exported.add(talk.id)
        result = exporter.export()
    assert result == set()


@pytest.mark.django_db
def test_exporter_break_slot(event, submission, room, tmp_path):
    with scopes_disabled():
        TalkSlot.objects.create(
            submission=submission,
            schedule=event.wip_schedule,
            room=room,
            start=event.datetime_from,
            end=event.datetime_from + dt.timedelta(minutes=30),
            is_visible=True,
        )
        TalkSlot.objects.create(
            submission=None,
            slot_type=SlotType.BREAK,
            schedule=event.wip_schedule,
            room=room,
            start=event.datetime_from + dt.timedelta(minutes=30),
            end=event.datetime_from + dt.timedelta(minutes=45),
            is_visible=True,
        )
        freeze_schedule(event.wip_schedule, name="v1")
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        result = exporter.export()
    assert len(result) >= 1


@pytest.mark.django_db
def test_exporter_track_without_color(event, submission_type, room, tmp_path):
    with scopes_disabled():
        from pretalx.person.models import User
        from pretalx.submission.domain.submission import add_speaker

        sub = Submission.objects.create(
            title="Trackless",
            event=event,
            submission_type=submission_type,
            content_locale="en",
        )
        spk = User.objects.create_user(password="x", email="s2@example.org", name="S Two")
        add_speaker(sub, user=spk)
        sub.accept()
        sub.confirm()
        TalkSlot.objects.create(
            submission=sub,
            schedule=event.wip_schedule,
            room=room,
            start=event.datetime_from,
            end=event.datetime_from + dt.timedelta(minutes=30),
            is_visible=True,
        )
        freeze_schedule(event.wip_schedule, name="v1")
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        result = exporter.export()
    assert len(result) >= 2


@pytest.mark.django_db
def test_fit_text_branches(event, tmp_path):
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
    font = exporter.font_title
    # wide max_width so the colon-terminated word fits -> elif branch, and the
    # text ends on that word so the trailing ``if line`` is skipped.
    lines = exporter._fit_text("short colon:", font, 100000)
    assert lines == ["short colon:"]
    # narrow max_width forces the wrapping branch as well.
    wrapped = exporter._fit_text("aaaa bbbb cccc dddd", font, 30)
    assert len(wrapped) > 1


@pytest.mark.django_db
def test_export_talk_without_title_or_speakers(event, submission_type, room, tmp_path):
    with scopes_disabled():
        sub = Submission.objects.create(
            title="placeholder",
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
            end=event.datetime_from + dt.timedelta(minutes=30),
            is_visible=True,
        )
        freeze_schedule(event.wip_schedule, name="v1")
    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        talk = event.current_schedule.talks.filter(is_visible=True).first()
        talk.submission.title = ""  # in-memory only, exercises empty-title path
        filename = exporter.export_talk(talk)
    assert filename.exists()


@pytest.mark.django_db
def test_export_speaker_without_display_name(event, submission, schedule, tmp_path):
    class _BlankSpeaker:
        id = 999

        def get_display_name(self):
            return ""

    with scope(event=event):
        exporter = VoctomixLowerThirdsExporter(event, tmp_path)
        talk = event.current_schedule.talks.filter(is_visible=True).first()
        filename = exporter.export_speaker(talk, _BlankSpeaker())
    assert filename.exists()
