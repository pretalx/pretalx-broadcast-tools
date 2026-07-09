import hashlib
import pathlib

from django.http import JsonResponse
from django.views import View


def _compute_static_hash():
    base = pathlib.Path(__file__).parent.parent
    files = sorted([*base.glob("static/**/*.js"), *base.glob("templates/**/*.html")])
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()


_static_hash = _compute_static_hash()


class BroadcastToolsEventInfoView(View):
    def get(self, request, *args, **kwargs):
        color = self.request.event.primary_color or "#3aa57c"
        return JsonResponse(
            {
                "color": color,
                "name": self.request.event.name.localize(self.request.event.locale),
                "no_talk": str(
                    self.request.event.settings.broadcast_tools_lower_thirds_no_talk_info
                ),
                "room-info": {
                    "lower_info": self.request.event.settings.broadcast_tools_room_info_lower_content
                    or "",
                    "show_next_talk": bool(
                        self.request.event.settings.broadcast_tools_room_info_show_next_talk
                    ),
                },
                "rooms": {
                    str(room.uuid): room.name.localize(self.request.event.locale)
                    for room in self.request.event.rooms.all()
                },
                "slug": self.request.event.slug,
                "start": self.request.event.date_from.isoformat(),
                "end": self.request.event.date_to.isoformat(),
                "timezone": str(self.request.event.tz),
                "locale": self.request.event.locale,
                "static_hash": _static_hash,
            }
        )
