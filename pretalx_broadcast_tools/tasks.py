import logging
from datetime import timedelta

from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled
from pretalx.celery_app import app
from pretalx.common.signals import periodic_task
from pretalx.event.models import Event

LOG = logging.getLogger(__name__)


@app.task(name="pretalx_broadcast_tools.export_voctomix_lower_thirds")
def export_voctomix_lower_thirds(*, event_id):
    from django.core.management import call_command

    with scopes_disabled():
        event = Event.objects.filter(pk=event_id).first()
    if not event:
        LOG.error(f"Could not find event {event_id=} for export")
        return

    with scope(event=event):
        if not event.current_schedule:
            LOG.error(f"event {event.slug} does not have schedule, can't export")
            return

    call_command(
        "export_voctomix_lower_thirds",
        event.slug,
    )


@app.task(name="pretalx_broadcast_tools.periodic_voctomix_export")
def task_periodic_voctomix_export(*, event_slug):
    from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (
        get_export_targz_path,
    )

    with scopes_disabled():
        event = Event.objects.filter(slug=event_slug).first()

    with scope(event=event):
        if not event.settings.broadcast_tools_lower_thirds_export_voctomix or not event.current_schedule:
            return

        targz_path = get_export_targz_path(event)
        needs_rebuild = False
        last_rebuild = event.cache.get("broadcast_tools_last_voctomix_export")
        _now = now()
        if not targz_path.exists():
            needs_rebuild = True
        if not last_rebuild or _now - last_rebuild >= timedelta(hours=1):
            needs_rebuild = True
        if event.cache.get("broadcast_tools_force_new_voctomix_export"):
            needs_rebuild = True

        if needs_rebuild:
            event.cache.delete("broadcast_tools_force_new_voctomix_export")
            event.cache.set("broadcast_tools_last_voctomix_export", _now, None)
            export_voctomix_lower_thirds.apply_async(kwargs={"event_id": event.id}, ignore_result=True)


@receiver(periodic_task)
def periodic_event_services(sender, **kwargs):
    two_days_ago = now().date() - timedelta(days=2)
    for event in Event.objects.filter(date_to__gte=two_days_ago):
        with scope(event=event):
            if not event.settings.broadcast_tools_lower_thirds_export_voctomix or not event.current_schedule:
                continue
            task_periodic_voctomix_export.apply_async(kwargs={"event_slug": event.slug}, ignore_result=True)
