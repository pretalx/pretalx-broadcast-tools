import logging
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_scopes import scope, scopes_disabled
from PIL import Image, ImageDraw, ImageFont
from pretalx.agenda.html_export import delete_directory
from pretalx.event.models import Event

from pretalx_broadcast_tools.utils.placeholders import placeholders

IMG_WIDTH = 1920  # px
IMG_HEIGHT = 1080  # px

FONT_SIZE_TITLE = 30  # px
FONT_SIZE_SPEAKER = 25  # px
FONT_SIZE_INFOLINE = 18  # px
FONT_FILE = Path(__file__).resolve().parent.parent.parent / "assets" / "titilium-web-regular.ttf"

BOX_PADDING = 10  # px

BOX_WIDTH = int(IMG_WIDTH * 0.8)
BOX_BOTTOM = int(IMG_HEIGHT - (IMG_HEIGHT * 0.1))
BOX_LEFT = int((IMG_WIDTH - BOX_WIDTH) / 2)


def get_export_path(event):
    return settings.HTMLEXPORT_ROOT / event.slug / "broadcast-tools"


def get_export_targz_path(event):
    return get_export_path(event).with_suffix(".voctomix.tar.gz")


def make_targz(generated_files, targz_path):
    tmp_name = targz_path.with_suffix(".tmp")
    tmp_name.unlink(missing_ok=True)
    with tarfile.open(tmp_name, "w:gz") as tar:
        for file in generated_files:
            tar.add(file, arcname=file.name)
    tmp_name.rename(targz_path)


class VoctomixLowerThirdsExporter:
    def __init__(self, event, tmp_dir):
        self.log = logging.getLogger(event.slug)
        self.event = event
        self.tmp_dir = tmp_dir
        self.exported = set()

        if event.primary_color:
            self.primary_colour = self._hex2rgb(event.primary_color)
        else:
            # pretalx.settings.DEFAULT_EVENT_PRIMARY_COLOR
            self.primary_colour = (58, 165, 124)

        self.infoline = event.settings.broadcast_tools_lower_thirds_info_string or ""

        self.font_title = ImageFont.truetype(
            FONT_FILE,
            size=FONT_SIZE_TITLE,
            encoding="unic",
        )
        self.font_speaker = ImageFont.truetype(
            FONT_FILE,
            size=FONT_SIZE_SPEAKER,
            encoding="unic",
        )
        self.font_infoline = ImageFont.truetype(
            FONT_FILE,
            size=FONT_SIZE_INFOLINE,
            encoding="unic",
        )

    @staticmethod
    def _hex2rgb(hex_value):
        hex_value = hex_value.lstrip("#")
        # black insists this should have spaces around the :, but flake8
        # complains about spaces around the :, soooooo ....
        return tuple(int(hex_value[i : i + 2], 16) for i in (0, 2, 4))  # NOQA

    @staticmethod
    def _fit_text(input_text, font, max_width):
        words = [i.strip() for i in input_text.split()]
        lines = []
        line = []
        for word in words:
            new_line = " ".join([*line, word])
            _, _, w, _ = font.getbbox(new_line)
            if w > max_width:
                # append old line to list of lines, then start new line with
                # current word
                lines.append(" ".join(line))
                line = [word]
            elif word.endswith(":"):
                lines.append(new_line)
                line = []
            else:
                line.append(word)

        if line:
            lines.append(" ".join(line))
        return lines

    def _get_infoline(self, talk):
        infoline = self.infoline
        if not isinstance(self.infoline, str):
            infoline = self.infoline.localize(self.event.locale)

        infoline = infoline.format(
            **placeholders(
                self.event,
                talk,
            )
        )
        _, _, w, _ = self.font_infoline.getbbox(infoline)
        return w, infoline

    def export_speaker(self, talk, speaker):
        img = Image.new(
            mode="RGBA",
            size=(IMG_WIDTH, IMG_HEIGHT),
            color=(0, 0, 0, 0),
        )

        speaker_text = self._fit_text(
            speaker.get_display_name(),
            self.font_speaker,
            BOX_WIDTH,
        )
        infoline_width, infoline_text = self._get_infoline(talk)

        y_pos = BOX_BOTTOM - BOX_PADDING
        if speaker_text:
            y_pos -= len(speaker_text) * FONT_SIZE_SPEAKER
        if infoline_text:
            y_pos -= FONT_SIZE_INFOLINE

        draw = ImageDraw.Draw(img)
        draw.rectangle(
            [
                (BOX_LEFT - BOX_PADDING, y_pos),
                (BOX_LEFT + BOX_WIDTH + BOX_PADDING, BOX_BOTTOM + BOX_PADDING),
            ],
            fill=self.primary_colour,
        )
        if talk.submission.track and talk.submission.track.color:
            draw.rectangle(
                [
                    (BOX_LEFT - BOX_PADDING, BOX_BOTTOM + BOX_PADDING),
                    (
                        BOX_LEFT + BOX_WIDTH + BOX_PADDING,
                        BOX_BOTTOM + (BOX_PADDING * 2),
                    ),
                ],
                fill=self._hex2rgb(talk.submission.track.color),
            )

        for line in speaker_text:
            draw.text(
                (BOX_LEFT, y_pos),
                line,
                font=self.font_speaker,
                fill=(255, 255, 255),
            )
            y_pos += FONT_SIZE_SPEAKER

        if infoline_text:
            draw.text(
                (BOX_LEFT + BOX_WIDTH - infoline_width, y_pos),
                infoline_text,
                font=self.font_infoline,
                fill=(255, 255, 255),
            )

        filename = self.tmp_dir / f"event_{talk.submission_id}_person_{speaker.id}.png"
        img.save(filename)
        self.log.debug(
            f"Generated single-speaker image for {speaker.get_display_name()!r} "
            f"of talk {talk.submission.title!r}, saved as {filename}"
        )
        return filename

    def export_talk(self, talk):
        img = Image.new(
            mode="RGBA",
            size=(IMG_WIDTH, IMG_HEIGHT),
            color=(0, 0, 0, 0),
        )

        title_text = self._fit_text(talk.submission.title, self.font_title, BOX_WIDTH)
        speaker_text = self._fit_text(
            ", ".join([person.get_display_name() for person in talk.submission.speakers.all()]),
            self.font_speaker,
            BOX_WIDTH,
        )
        infoline_width, infoline_text = self._get_infoline(talk)

        y_pos = BOX_BOTTOM - BOX_PADDING
        if title_text:
            y_pos -= len(title_text) * FONT_SIZE_TITLE
        if speaker_text:
            y_pos -= len(speaker_text) * FONT_SIZE_SPEAKER
        if title_text and speaker_text:
            y_pos -= BOX_PADDING
        if infoline_text:
            y_pos -= FONT_SIZE_INFOLINE

        draw = ImageDraw.Draw(img)
        draw.rectangle(
            [
                (BOX_LEFT - BOX_PADDING, y_pos),
                (BOX_LEFT + BOX_WIDTH + BOX_PADDING, BOX_BOTTOM + BOX_PADDING),
            ],
            fill=self.primary_colour,
        )
        if talk.submission.track and talk.submission.track.color:
            draw.rectangle(
                [
                    (BOX_LEFT - BOX_PADDING, BOX_BOTTOM + BOX_PADDING),
                    (
                        BOX_LEFT + BOX_WIDTH + BOX_PADDING,
                        BOX_BOTTOM + (BOX_PADDING * 2),
                    ),
                ],
                fill=self._hex2rgb(talk.submission.track.color),
            )

        for line in title_text:
            draw.text(
                (BOX_LEFT, y_pos),
                line,
                font=self.font_title,
                fill=(255, 255, 255),
            )
            y_pos += FONT_SIZE_TITLE

        if title_text and speaker_text:
            y_pos += BOX_PADDING

        for line in speaker_text:
            draw.text(
                (BOX_LEFT, y_pos),
                line,
                font=self.font_speaker,
                fill=(255, 255, 255),
            )
            y_pos += FONT_SIZE_SPEAKER

        if infoline_text:
            draw.text(
                (BOX_LEFT + BOX_WIDTH - infoline_width, y_pos),
                infoline_text,
                font=self.font_infoline,
                fill=(255, 255, 255),
            )

        filename = self.tmp_dir / f"event_{talk.submission_id}_persons.png"
        img.save(filename)
        self.log.debug(f"Generated image for talk {talk.submission.title!r}, saved as {filename}")
        return filename

    def export(self):
        generated_files = set()
        if not self.event.current_schedule:
            raise CommandError(f"event {self.event.slug} ({self.event.name}) does not have a schedule to be exported!")

        self.log.info(f"Generating voctomix-compatible lower thirds for event {self.event.name}")

        for talk in self.event.current_schedule.talks.filter(is_visible=True).select_related("submission"):
            if talk.id in self.exported:
                # account for talks that are scheduled multiple times
                self.log.warning(
                    f"Talk {talk.submission.title!r} was already generated, skipping. "
                    "(Possibly scheduled multiple times?)"
                )
                continue

            if talk.submission is None:
                self.log.info(f"Talk {talk.id} has no associated submission, this is a break. Skipping.")
                continue

            self.log.info(f"Generating image(s) for talk {talk.submission.title!r}")
            generated_files.add(self.export_talk(talk))
            for speaker in talk.submission.speakers.all():
                generated_files.add(self.export_speaker(talk, speaker))
            self.exported.add(talk.id)

        return generated_files


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("event", type=str)
        parser.add_argument("--no-delete-source-files", action="store_true")

    def handle(self, *args, **options):
        event_slug = options.get("event")

        with scopes_disabled():
            try:
                event = Event.objects.get(slug__iexact=event_slug)
            except Event.DoesNotExist:
                raise CommandError(f"could not find event with slug {event_slug!r}")

        with scope(event=event):
            logging.info(f"Exporting {event.name}")

            export_dir = get_export_path(event)
            targz_path = get_export_targz_path(event)

            delete_directory(export_dir)
            # for the first export of the conference, the "broadcast-tools"
            # directory does not exist
            export_dir.mkdir(parents=True)

            try:
                exporter = VoctomixLowerThirdsExporter(event, export_dir)
                generated_files = exporter.export()
                make_targz(generated_files, targz_path)
            except Exception:
                logging.exception(f"Export of {event.name} failed")
            else:
                logging.info(f"Export of {event.name} succeeded, export available at {targz_path}")
            finally:
                if not options.get("no_delete_source_files"):
                    delete_directory(export_dir)
