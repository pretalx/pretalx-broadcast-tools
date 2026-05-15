import pytest
from django.urls import reverse
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString


@pytest.mark.django_db
def test_event_info(client, event, room):
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:event_info",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == event.slug
    assert data["color"] == "#abcdef"
    assert str(room.uuid) in data["rooms"]
    assert data["room-info"]["show_next_talk"] is False
    assert "static_hash" in data


@pytest.mark.django_db
def test_event_info_default_color_and_next_talk(client, event):
    with scopes_disabled():
        event.primary_color = None
        event.save()
        event.settings.broadcast_tools_room_info_show_next_talk = True
        event.settings.broadcast_tools_room_info_lower_content = "public_qr"
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:event_info",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    data = response.json()
    assert data["color"] == "#3aa57c"
    assert data["room-info"]["show_next_talk"] is True
    assert data["room-info"]["lower_info"] == "public_qr"


@pytest.mark.django_db
def test_schedule_json(client, event, schedule, submission):
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:schedule",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["talks"]) == 1
    talk = data["talks"][0]
    assert talk["id"] == submission.id
    assert talk["title"] == submission.title
    assert talk["track"]["name"] == "Test Track"
    assert "feedback_qr" in talk["urls"]


@pytest.mark.django_db
def test_schedule_json_with_infoline(client, event, schedule):
    with scopes_disabled():
        event.settings.broadcast_tools_lower_thirds_info_string = LazyI18nString("Code {CODE} / {TRACK_NAME_COLOURED}")
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:schedule",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    talk = response.json()["talks"][0]
    assert "Code " in talk["infoline"]
    assert "<span" in talk["infoline"]


@pytest.mark.django_db
def test_schedule_json_no_track(client, event, room, submission_type):
    from pretalx.schedule.domain.release import freeze_schedule
    from pretalx.schedule.models import TalkSlot
    from pretalx.submission.models import Submission

    with scopes_disabled():
        sub = Submission.objects.create(
            title="No track talk",
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
            end=event.datetime_from,
            is_visible=True,
        )
        freeze_schedule(event.wip_schedule, name="v1")
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:schedule",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    assert response.json()["talks"][0]["track"] is None


@pytest.mark.django_db
def test_schedule_json_keyerror(client, event, schedule):
    with scopes_disabled():
        event.settings.broadcast_tools_lower_thirds_info_string = "{DOESNOTEXIST}"
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:schedule",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    assert "DOESNOTEXIST" in response.json()["error"][0]


@pytest.mark.django_db
def test_schedule_json_generic_error(client, event, schedule):
    with scopes_disabled():
        event.settings.broadcast_tools_lower_thirds_info_string = "{0}"
    response = client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:schedule",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    assert "error" in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    ("lowerthirds", "room_info", "room_timer"),
)
def test_static_html_views(client, event, name):
    response = client.get(
        reverse(
            f"plugins:pretalx_broadcast_tools:{name}",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ("feedback_qr_id", "public_qr_id"))
def test_qr_views(client, event, submission, schedule, kind):
    response = client.get(
        reverse(
            f"plugins:pretalx_broadcast_tools:{kind}",
            kwargs={"event": event.slug, "talk": submission.id},
        )
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert b"svg" in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ("feedback_qr_id", "public_qr_id"))
def test_qr_views_unknown_talk(client, event, kind):
    response = client.get(
        reverse(
            f"plugins:pretalx_broadcast_tools:{kind}",
            kwargs={"event": event.slug, "talk": 999999},
        )
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_qr_view_custom_domain(rf, event, submission, schedule):
    from django_scopes import scope

    from pretalx_broadcast_tools.views.qr import (
        BroadcastToolsFeedbackQrCodeSvg,
        BroadcastToolsPublicQrCodeSvg,
    )

    with scopes_disabled():
        event.custom_domain = "https://talks.example.org"
        event.save()
    with scope(event=event):
        request = rf.get("/")
        request.event = event
        for view_class in (
            BroadcastToolsPublicQrCodeSvg,
            BroadcastToolsFeedbackQrCodeSvg,
        ):
            response = view_class.as_view()(request, event=event.slug, talk=submission.id)
            assert response.status_code == 200
            assert response["Content-Type"] == "image/svg+xml"


@pytest.mark.django_db
def test_orga_view_get(orga_client, event):
    response = orga_client.get(reverse("plugins:pretalx_broadcast_tools:orga", kwargs={"event": event.slug}))
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_view_forbidden_for_reviewer(review_client, event):
    response = review_client.get(reverse("plugins:pretalx_broadcast_tools:orga", kwargs={"event": event.slug}))
    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_orga_view_post(orga_client, event):
    response = orga_client.post(
        reverse("plugins:pretalx_broadcast_tools:orga", kwargs={"event": event.slug}),
        {
            "broadcast_tools_lower_thirds_no_talk_info_0": "Nothing here",
            "broadcast_tools_lower_thirds_info_string_0": "{CODE}",
            "broadcast_tools_lower_thirds_export_voctomix": "on",
            "broadcast_tools_room_info_lower_content": "public_qr",
            "broadcast_tools_room_info_show_next_talk": "on",
            "broadcast_tools_pdf_show_internal_notes": "on",
            "broadcast_tools_pdf_ignore_do_not_record": "",
            "broadcast_tools_pdf_questions_to_include": "1,2",
            "broadcast_tools_pdf_additional_content": "hello",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scopes_disabled():
        assert str(event.settings.broadcast_tools_lower_thirds_no_talk_info) == "Nothing here"
        assert event.settings.broadcast_tools_lower_thirds_export_voctomix is True


@pytest.mark.django_db
def test_voctomix_download_missing(orga_client, event, schedule):
    response = orga_client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:lowerthirds_voctomix_download",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_voctomix_download_present(orga_client, event, schedule):
    from pretalx_broadcast_tools.management.commands.export_voctomix_lower_thirds import (
        get_export_path,
        get_export_targz_path,
    )

    with scopes_disabled():
        targz_path = get_export_targz_path(event)
        get_export_path(event).parent.mkdir(parents=True, exist_ok=True)
        targz_path.write_bytes(b"dummy")
    response = orga_client.get(
        reverse(
            "plugins:pretalx_broadcast_tools:lowerthirds_voctomix_download",
            kwargs={"event": event.slug},
        )
    )
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"dummy"
