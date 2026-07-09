from django.conf import settings


def placeholders(event, talk, supports_html_colour=False):
    track_name = str(talk.submission.track.name) if talk.submission.track else ""

    result = {
        "CODE": talk.submission.code,
        "EVENT_SLUG": str(event.slug),
        "FEEDBACK_URL": f"{event.custom_domain or settings.SITE_URL}{talk.submission.urls.feedback}",
        "TALK_SLUG": talk.frab_slug,
        "TALK_URL": f"{event.custom_domain or settings.SITE_URL}{talk.submission.urls.public}",
        "TRACK_NAME": track_name,
    }

    if talk.submission.track and supports_html_colour:
        result["TRACK_NAME_COLOURED"] = (
            f'<span style="color: {talk.submission.track.color}">{track_name}</span>'
        )
    else:
        result["TRACK_NAME_COLOURED"] = track_name

    # for the americans
    result["TRACK_NAME_COLORED"] = result["TRACK_NAME_COLOURED"]

    return result
