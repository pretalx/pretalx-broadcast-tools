from django.urls import include, path

from .views.event_info import BroadcastToolsEventInfoView
from .views.orga import BroadcastToolsOrgaView
from .views.qr import BroadcastToolsFeedbackQrCodeSvg, BroadcastToolsPublicQrCodeSvg
from .views.schedule import BroadcastToolsScheduleView
from .views.static_html import (
    BroadcastToolsLowerThirdsView,
    BroadcastToolsRoomInfoView,
    BroadcastToolsRoomTimerView,
)
from .views.voctomix_export import BroadcastToolsLowerThirdsVoctomixDownloadView

urlpatterns = [
    path(
        "<slug:event>/p/broadcast-tools/",
        include(
            [
                path(
                    "event.json",
                    BroadcastToolsEventInfoView.as_view(),
                    name="event_info",
                ),
                path(
                    "schedule.json",
                    BroadcastToolsScheduleView.as_view(),
                    name="schedule",
                ),
                path(
                    "lower-thirds/",
                    BroadcastToolsLowerThirdsView.as_view(),
                    name="lowerthirds",
                ),
                path(
                    "lower-thirds.voctomix.tar.gz",
                    BroadcastToolsLowerThirdsVoctomixDownloadView.as_view(),
                    name="lowerthirds_voctomix_download",
                ),
                path(
                    "feedback-qr/<talk>.svg",
                    BroadcastToolsFeedbackQrCodeSvg.as_view(),
                    name="feedback_qr_id",
                ),
                path(
                    "public-qr/<talk>.svg",
                    BroadcastToolsPublicQrCodeSvg.as_view(),
                    name="public_qr_id",
                ),
                path(
                    "room-info/", BroadcastToolsRoomInfoView.as_view(), name="room_info"
                ),
                path(
                    "room-timer/",
                    BroadcastToolsRoomTimerView.as_view(),
                    name="room_timer",
                ),
            ]
        ),
    ),
    path(
        "orga/event/<slug:event>/settings/p/broadcast-tools/",
        BroadcastToolsOrgaView.as_view(),
        name="orga",
    ),
]
