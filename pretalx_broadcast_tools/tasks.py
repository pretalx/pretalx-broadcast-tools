import logging
from datetime import timedelta

from django.core.management import call_command
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from pretalx.celery_app import app
from pretalx.common.signals import periodic_task
from pretalx.event.models import Event

LOG = logging.getLogger(__name__)


@app.task(name="pretalx_broadcast_tools.export_voctomix_lower_thirds")
def export_voctomix_lower_thirds(*, event_id):
    with scopes_disabled():
        event = Event.objects.filter(pk=event_id).first()
    if not event:
        LOG.error("Could not find event %s for export", event_id)
        return

    with scope(event=event):
        if not event.current_schedule:
            LOG.error("event %s does not have schedule, can't export", event.slug)
            return

    call_command("export_voctomix_lower_thirds", event.slug)


def needs_voctomix_export(event):
    from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (  # noqa: PLC0415 -- slow import
        get_export_targz_path,
    )

    if event.cache.get("broadcast_tools_force_new_voctomix_export"):
        return True
    if not get_export_targz_path(event).exists():
        return True
    last_rebuild = event.cache.get("broadcast_tools_last_voctomix_export")
    return not last_rebuild or now() - last_rebuild >= timedelta(hours=1)


@receiver(periodic_task)
def periodic_event_services(sender, **kwargs):
    two_days_ago = now().date() - timedelta(days=2)
    events = Event.objects.with_plugin("pretalx_broadcast_tools").filter(
        date_to__gte=two_days_ago
    )
    for event in events:
        with scope(event=event):
            if (
                not event.settings.broadcast_tools_lower_thirds_export_voctomix
                or not event.current_schedule
                or not needs_voctomix_export(event)
            ):
                continue
            event.cache.delete("broadcast_tools_force_new_voctomix_export")
            event.cache.set("broadcast_tools_last_voctomix_export", now(), None)
            export_voctomix_lower_thirds.apply_async(
                kwargs={"event_id": event.id}, ignore_result=True
            )
