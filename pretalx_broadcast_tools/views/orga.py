from django.views.generic import FormView

from pretalx.common.views.mixins import PermissionRequired

from pretalx_broadcast_tools.forms import BroadcastToolsSettingsForm


class BroadcastToolsOrgaView(PermissionRequired, FormView):
    form_class = BroadcastToolsSettingsForm
    permission_required = "event.update_event"
    template_name = "pretalx_broadcast_tools/orga.html"

    def get_success_url(self):
        return self.request.path

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def get_object(self):
        return self.request.event

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return {
            "obj": self.request.event,
            "attribute_name": "settings",
            "locales": self.request.event.locales,
            **kwargs,
        }
