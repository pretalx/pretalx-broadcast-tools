from tempfile import NamedTemporaryFile

from django.utils.translation import gettext_noop
from i18nfield.strings import LazyI18nString
from pretalx.schedule.interfaces.exporters import ScheduleData
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pretalx_broadcast_tools.utils.placeholders import placeholders

A4_WIDTH, A4_HEIGHT = A4
PAGE_PADDING = 10 * mm


def _(text):
    return LazyI18nString.from_gettext(gettext_noop(text))


class PDFInfoPage(Flowable):
    def __init__(self, event, schedule, fahrplan_day, room_details, talk, style):
        super().__init__()
        self.event = event
        self.schedule = schedule
        self.day = fahrplan_day
        self.room = room_details
        self.talk = talk
        self.style = style
        self.y_position = PAGE_PADDING

    @property
    def _questions(self):
        result = set()
        for i in (self.event.settings.broadcast_tools_pdf_questions_to_include or "").split(","):
            i = i.strip()
            if not i:
                continue
            try:
                result.add(int(i))
            except ValueError:
                # Ignore non-numeric entries instead of breaking the export.
                continue
        return result

    def _add(self, item, gap=2):
        _, height = item.wrapOn(self.canv, A4_WIDTH - 2 * PAGE_PADDING, A4_HEIGHT - 2 * PAGE_PADDING)
        self.y_position += height + gap * mm
        item.drawOn(self.canv, PAGE_PADDING, -self.y_position)

    def _checkbox_text(self, text, **kwargs):
        item = Paragraph(text, **kwargs)
        _, height = item.wrapOn(self.canv, A4_WIDTH - 2 * PAGE_PADDING, A4_HEIGHT - 2 * PAGE_PADDING)
        self.y_position += height + 2 * mm
        item.drawOn(self.canv, PAGE_PADDING + 1.3 * height, -self.y_position)
        self.canv.rect(PAGE_PADDING, -self.y_position, height * 0.8, height * 0.8)

    def _question_text(self, question, answer, **kwargs):
        item = Paragraph(question, **kwargs)
        _, height = item.wrapOn(self.canv, A4_WIDTH - 2 * PAGE_PADDING, A4_HEIGHT - 2 * PAGE_PADDING)
        self.y_position += height + 2 * mm
        item.drawOn(self.canv, PAGE_PADDING, -self.y_position)

        item = Paragraph(answer, **kwargs)
        _, height = item.wrapOn(self.canv, A4_WIDTH - 3 * PAGE_PADDING, A4_HEIGHT - 2 * PAGE_PADDING)
        self.y_position += height + 2 * mm
        item.drawOn(self.canv, 2 * PAGE_PADDING, -self.y_position)

    def _space(self):
        self._add(Spacer(1, PAGE_PADDING / 2))

    def _localize(self, translation):
        return translation.localize(self.event.locale)

    def draw(self):
        if hasattr(self.talk, "local_start"):
            talk_start = self.talk.local_start
        else:
            talk_start = self.talk.start.astimezone(self.event.tz)
        if hasattr(self.talk, "local_end"):
            talk_end = self.talk.local_end
        else:
            talk_end = self.talk.end.astimezone(self.event.tz)
        # add some information horizontally to the side of the page
        self.canv.saveState()
        self.canv.rotate(90)
        self.canv.setFont("Helvetica", 12)
        self.canv.drawString(
            -(A4_HEIGHT - (PAGE_PADDING / 3)),
            -(PAGE_PADDING / 3),
            " | ".join(
                [
                    self.talk.submission.code,
                    self.talk.submission.submission_type.name.localize(self.event.locale),
                    self.event.name.localize(self.event.locale),
                    talk_start.isoformat(),
                    f"Day {self.day['index']}",
                    self.room["name"].localize(self.event.locale),
                    f"Schedule {self.schedule.version}",
                ],
            ),
        )
        self.canv.restoreState()

        if self.talk.submission.do_not_record:
            self._add(
                Paragraph(
                    self._localize(_("DO NOT RECORD - DO NOT STREAM")),
                    style=self.style["Warning"],
                ),
                gap=0,
            )
            self._space()

        self._add(
            Paragraph(
                " | ".join(
                    [
                        self._localize(self.event.name),
                        self._localize(self.room["name"]),
                        talk_start.strftime("%F"),
                        f"{talk_start.strftime('%T')} - {talk_end.strftime('%T')}",
                    ],
                ),
                style=self.style["Meta"],
            )
        )
        self._add(Paragraph(self.talk.submission.title, style=self.style["Title"]), gap=0)
        self._space()

        for spk in self.talk.submission.speakers.all():
            self._checkbox_text(
                spk.get_display_name(),
                style=self.style["Speaker"],
            )
        self._space()

        if self.talk.submission.track:
            self._add(
                Paragraph(
                    f"{self._localize(_('Track:'))} {self._localize(self.talk.submission.track.name)}",
                    style=self.style["Meta"],
                )
            )
        self._add(
            Table(
                [
                    (
                        self._localize(_("Duration")),
                        self._localize(_("Language")),
                        self._localize(_("Type")),
                        self._localize(_("Code")),
                    ),
                    (
                        self.talk.export_duration,
                        self.talk.submission.content_locale,
                        self.talk.submission.submission_type.name,
                        self.talk.submission.code,
                    ),
                ],
                colWidths=30 * mm,
                style=TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
                    ]
                ),
            )
        )

        if self.talk.submission.abstract:
            self._add(
                Paragraph(
                    self.talk.submission.abstract,
                    style=self.style["Abstract"],
                )
            )

        if self.event.settings.broadcast_tools_pdf_additional_content:
            self._space()
            self._add(
                Paragraph(
                    self.event.settings.broadcast_tools_pdf_additional_content.format(
                        **placeholders(self.schedule.event, self.talk)
                    ),
                    style=self.style["Meta"],
                )
            )

        if self.talk.submission.answers and self._questions:
            self._space()
            self._add(
                Paragraph(
                    self._localize(_("Questions")),
                    style=self.style["Heading"],
                )
            )

            for answer in self.talk.submission.answers.order_by("question__position"):
                if answer.question.id not in self._questions:
                    continue
                self._question_text(
                    self._localize(answer.question.question),
                    answer.answer,
                    style=self.style["Question"],
                )

            for spk in self.talk.submission.speakers.all():
                for answer in spk.answers.order_by("question__position"):
                    if answer.question.id not in self._questions:
                        continue
                    self._question_text(
                        f"{self._localize(answer.question.question)} ({spk.get_display_name()})",
                        answer.answer,
                        style=self.style["Question"],
                    )

        if self.talk.submission.notes:
            self._space()
            self._add(
                Paragraph(
                    self._localize(_("Notes")),
                    style=self.style["Heading"],
                )
            )
            for line in self.talk.submission.notes.splitlines():
                line = line.strip()
                if not line:
                    continue
                self._add(
                    Paragraph(
                        line,
                        style=self.style["Notes"],
                    )
                )

        if self.talk.submission.internal_notes and self.event.settings.broadcast_tools_pdf_show_internal_notes:
            self._space()
            self._add(
                Paragraph(
                    self._localize(_("Internal Notes")),
                    style=self.style["Heading"],
                )
            )
            for line in self.talk.submission.internal_notes.splitlines():
                line = line.strip()
                if not line:
                    continue
                self._add(
                    Paragraph(
                        line,
                        style=self.style["Notes"],
                    )
                )


class PDFExporter(ScheduleData):
    identifier = "broadcast_pdf"
    verbose_name = "Broadcast Tools PDF"
    public = False
    show_qrcode = False
    icon = "fa-file-pdf"

    def _add_pages(self):
        pages = []
        for fahrplan_day in self.data:
            for room_details in fahrplan_day["rooms"]:
                for talk in room_details["talks"]:
                    if talk.submission.do_not_record and self.event.settings.broadcast_tools_pdf_ignore_do_not_record:
                        continue
                    pages.append(
                        PDFInfoPage(
                            self.event,
                            self.schedule,
                            fahrplan_day,
                            room_details,
                            talk,
                            self._style,
                        )
                    )
                    pages.append(PageBreak())
        return pages

    @property
    def _style(self):
        stylesheet = StyleSheet1()
        stylesheet.add(ParagraphStyle(name="Normal", fontName="Helvetica", fontSize=12, leading=14))
        stylesheet.add(ParagraphStyle(name="Title", fontName="Helvetica-Bold", fontSize=20, leading=24))
        stylesheet.add(ParagraphStyle(name="Speaker", fontName="Helvetica-Oblique", fontSize=12, leading=14))
        stylesheet.add(ParagraphStyle(name="Meta", fontName="Helvetica", fontSize=14, leading=16))
        stylesheet.add(ParagraphStyle(name="Heading", fontName="Helvetica-Bold", fontSize=14, leading=16))
        stylesheet.add(ParagraphStyle(name="Question", fontName="Helvetica", fontSize=12, leading=14))
        stylesheet.add(ParagraphStyle(name="Abstract", fontName="Helvetica-Oblique", fontSize=10, leading=12))
        stylesheet.add(ParagraphStyle(name="Notes", fontName="Helvetica", fontSize=12, leading=14))
        stylesheet.add(
            ParagraphStyle(
                name="Warning",
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                alignment=TA_CENTER,
                textColor=colors.red,
            )
        )
        return stylesheet

    def render(self, *args, **kwargs):
        with NamedTemporaryFile(suffix=".pdf") as f:
            doc = SimpleDocTemplate(
                f.name,
                pagesize=A4,
                rightMargin=0,
                leftMargin=0,
                topMargin=0,
                bottomMargin=0,
            )
            doc.build(self._add_pages())
            f.seek(0)

            return (
                f"{self.event.slug}_broadcast_tools_{self.schedule.version}.pdf",
                "application/pdf",
                f.read(),
            )
