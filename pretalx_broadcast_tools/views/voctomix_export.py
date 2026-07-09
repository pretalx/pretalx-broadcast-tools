from django.http import FileResponse, Http404
from django.views import View

from pretalx.common.text.path import safe_filename
from pretalx.common.views.mixins import EventPermissionRequired


class BroadcastToolsLowerThirdsVoctomixDownloadView(EventPermissionRequired, View):
    permission_required = "schedule.list_schedule"

    def get(self, request, *args, **kwargs):
        # Deferred so that the plugin's URLconf import doesn't drag in the
        # management command's heavy module-level dependencies (PIL.Image,
        # ImageDraw, ImageFont, plus the whole pretalx.agenda.html_export
        # subtree, which itself unconditionally imports django.test.Client).
        # That's ~100+ ms saved off every web-process startup, and the cost
        # only materialises when someone hits the download endpoint.
        from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (  # noqa: PLC0415
            get_export_targz_path,
        )

        targz_path = get_export_targz_path(self.request.event)
        if not targz_path.exists():
            raise Http404
        response = FileResponse(targz_path.open("rb"), as_attachment=True)
        response["Content-Disposition"] = (
            f"attachment; filename={safe_filename(targz_path.name)}"
        )
        return response
