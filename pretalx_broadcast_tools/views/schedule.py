import datetime as dt

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from pretalx.agenda.views.schedule import ScheduleMixin
from pretalx.common.views.mixins import EventPermissionRequired
from pretalx.schedule.interfaces.exporters import ScheduleData

from ..utils.placeholders import placeholders


class BroadcastToolsScheduleView(EventPermissionRequired, ScheduleMixin, View):
    permission_required = "schedule.list_schedule"

    def get(self, request, *args, **kwargs):
        schedule = ScheduleData(
            event=self.request.event,
            schedule=self.schedule,
        )
        infoline = str(schedule.event.settings.broadcast_tools_lower_thirds_info_string or "")
        try:
            return JsonResponse(
                {
                    "rooms": sorted(
                        {room["name"].localize(schedule.event.locale) for day in schedule.data for room in day["rooms"]}
                    ),
                    "talks": [
                        {
                            "id": talk.submission.id,
                            "start": talk.start.astimezone(schedule.event.tz).isoformat(),
                            "start_ts": int(talk.start.timestamp()),
                            "end": (talk.start + dt.timedelta(minutes=talk.duration))
                            .astimezone(schedule.event.tz)
                            .isoformat(),
                            "end_ts": int((talk.start + dt.timedelta(minutes=talk.duration)).timestamp()),
                            "slug": talk.frab_slug,
                            "title": talk.submission.title,
                            "persons": [person.get_display_name() for person in talk.submission.speakers.all()],
                            "track": (
                                {
                                    "color": talk.submission.track.color,
                                    "name": str(talk.submission.track.name),
                                }
                                if talk.submission.track
                                else None
                            ),
                            "room": room["name"].localize(schedule.event.locale),
                            "infoline": infoline.format(
                                **placeholders(schedule.event, talk, supports_html_colour=True)
                            ),
                            "image_url": talk.submission.image_url,
                            "locale": talk.submission.content_locale,
                            "do_not_record": talk.submission.do_not_record,
                            "abstract": talk.submission.abstract,
                            "urls": {
                                "feedback": "{}{}".format(
                                    schedule.event.custom_domain or settings.SITE_URL,
                                    talk.submission.urls.feedback,
                                ),
                                "feedback_qr": reverse(
                                    "plugins:pretalx_broadcast_tools:feedback_qr_id",
                                    kwargs={
                                        "event": schedule.event.slug,
                                        "talk": talk.submission.id,
                                    },
                                ),
                                "public": "{}{}".format(
                                    schedule.event.custom_domain or settings.SITE_URL,
                                    talk.submission.urls.public,
                                ),
                                "public_qr": reverse(
                                    "plugins:pretalx_broadcast_tools:public_qr_id",
                                    kwargs={
                                        "event": schedule.event.slug,
                                        "talk": talk.submission.id,
                                    },
                                ),
                            },
                        }
                        for day in schedule.data
                        for room in day["rooms"]
                        for talk in room["talks"]
                    ],
                },
            )
        except KeyError as e:
            key = str(e)[1:-1]
            return JsonResponse(
                {
                    "error": [
                        f"Could not find value for placeholder {{{key}}} in info line.",
                        f"If you want to use {{{key}}} without evaluating it, please use as follows: {{{{{key}}}}}",
                    ],
                }
            )
        except Exception as e:
            return JsonResponse(
                {
                    "error": [
                        repr(e),
                    ],
                }
            )
