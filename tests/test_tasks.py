import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from pretalx.event.models import Event

from pretalx_broadcast_tools import tasks
from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (
    get_export_targz_path,
)


@pytest.mark.django_db
def test_export_task_event_not_found(caplog):
    tasks.export_voctomix_lower_thirds(event_id=999999)
    assert "Could not find event" in caplog.text


@pytest.mark.django_db
def test_export_task_no_schedule(event, caplog):
    tasks.export_voctomix_lower_thirds(event_id=event.id)
    assert "does not have schedule" in caplog.text


@pytest.mark.django_db
def test_export_task_success(event, submission, schedule, mocker):
    mocked = mocker.patch("django.core.management.call_command")
    tasks.export_voctomix_lower_thirds(event_id=event.id)
    mocked.assert_called_once()


@pytest.mark.django_db
def test_periodic_export_disabled(event, submission, schedule):
    # setting disabled by default -> early return, no exception
    tasks.task_periodic_voctomix_export(event_slug=event.slug)


@pytest.mark.django_db
def test_periodic_export_rebuild_paths(event, submission, schedule, mocker, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    from django.core.cache import cache as dj_cache

    dj_cache.clear()
    apply_async = mocker.patch.object(tasks.export_voctomix_lower_thirds, "apply_async")
    with scopes_disabled():
        event.settings.broadcast_tools_lower_thirds_export_voctomix = True

    def reload():
        return Event.objects.get(slug=event.slug)

    # 1. no targz, no last_rebuild -> rebuild
    tasks.task_periodic_voctomix_export(event_slug=event.slug)
    assert apply_async.call_count == 1

    # 2. recent last_rebuild (set by step 1) + targz present -> no rebuild
    targz = get_export_targz_path(event)
    targz.parent.mkdir(parents=True, exist_ok=True)
    targz.write_bytes(b"x")
    tasks.task_periodic_voctomix_export(event_slug=event.slug)
    assert apply_async.call_count == 1

    # 3. stale last_rebuild -> rebuild
    with scopes_disabled():
        reload().cache.set(
            "broadcast_tools_last_voctomix_export",
            now() - dt.timedelta(hours=2),
            None,
        )
    tasks.task_periodic_voctomix_export(event_slug=event.slug)
    assert apply_async.call_count == 2

    # 4. forced rebuild
    with scopes_disabled():
        reloaded = reload()
        reloaded.cache.set("broadcast_tools_last_voctomix_export", now(), None)
        reloaded.cache.set("broadcast_tools_force_new_voctomix_export", True, None)
    tasks.task_periodic_voctomix_export(event_slug=event.slug)
    assert apply_async.call_count == 3


@pytest.mark.django_db
def test_periodic_event_services(organiser, mocker):
    apply_async = mocker.patch.object(tasks.task_periodic_voctomix_export, "apply_async")
    today = dt.date.today()
    with scopes_disabled():
        from pretalx.event.domain.event import initialise_event
        from pretalx.event.domain.plugins import enable_plugin
        from pretalx.schedule.domain.release import freeze_schedule
        from pretalx.schedule.models import Room, TalkSlot
        from pretalx.submission.models import Submission, SubmissionType

        def make_event(slug, date_to, *, enabled):
            ev = Event.objects.create(
                name=f"Event {slug}",
                is_public=True,
                slug=slug,
                email="o@o.org",
                date_from=date_to - dt.timedelta(days=1),
                date_to=date_to,
                organiser=organiser,
            )
            initialise_event(ev)
            enable_plugin(ev, "pretalx_broadcast_tools")
            ev.save()
            sub_type = SubmissionType.objects.create(event=ev, name="Talk", default_duration=30)
            room = Room.objects.create(event=ev, name="R")
            sub = Submission.objects.create(title="T", event=ev, submission_type=sub_type, content_locale="en")
            sub.accept()
            sub.confirm()
            TalkSlot.objects.create(
                submission=sub,
                schedule=ev.wip_schedule,
                room=room,
                start=ev.datetime_from,
                end=ev.datetime_from + dt.timedelta(minutes=30),
                is_visible=True,
            )
            freeze_schedule(ev.wip_schedule, name="v1")
            if enabled:
                ev.settings.broadcast_tools_lower_thirds_export_voctomix = True
            return ev

        # ongoing event with the feature enabled -> triggers an export
        make_event("live", today, enabled=True)
        # ongoing event with the feature disabled -> skipped (continue)
        make_event("live-disabled", today, enabled=False)
        # event that ended long ago -> excluded by the date filter entirely
        make_event("ancient", today - dt.timedelta(days=10), enabled=True)

    tasks.periodic_event_services(sender=None)
    apply_async.assert_called_once()
