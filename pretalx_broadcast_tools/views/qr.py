from xml.etree import ElementTree as ET

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views import View


def _make_svg_response(url):
    # Deferred so that the plugin's URLconf import (which loads at app startup)
    # doesn't drag the qrcode package — and the PIL it pulls in — into every
    # web process. The cost (~65 ms in pretalx startup measurements) only
    # materialises when somebody actually hits the QR endpoint.
    import qrcode  # noqa: PLC0415
    import qrcode.image.svg  # noqa: PLC0415

    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgImage)
    svg_data = ET.tostring(image.get_image()).decode()
    return HttpResponse(svg_data, content_type="image/svg+xml")


class BroadcastToolsFeedbackQrCodeSvg(View):
    def get(self, request, *args, **kwargs):
        talk = self.request.event.submissions.filter(id=kwargs["talk"]).first()
        if not talk:
            raise Http404
        domain = request.event.custom_domain or settings.SITE_URL
        return _make_svg_response(f"{domain}{talk.urls.feedback}")


class BroadcastToolsPublicQrCodeSvg(View):
    def get(self, request, *args, **kwargs):
        talk = self.request.event.submissions.filter(id=kwargs["talk"]).first()
        if not talk:
            raise Http404
        domain = request.event.custom_domain or settings.SITE_URL
        return _make_svg_response(f"{domain}{talk.urls.public}")
