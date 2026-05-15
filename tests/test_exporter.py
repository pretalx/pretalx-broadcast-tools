import datetime as dt

import pytest
from django_scopes import scope, scopes_disabled
from pretalx.schedule.domain.release import freeze_schedule
from pretalx.schedule.models import TalkSlot
from pretalx.submission.domain.submission import add_speaker
from pretalx.submission.models import Answer, Question, Submission, Track
from pretalx.submission.models.question import QuestionTarget

from pretalx_broadcast_tools.exporter import PDFExporter, PDFInfoPage


@pytest.fixture
def rich_schedule(event, submission_type, room):
    with scopes_disabled():
        track = Track.objects.create(event=event, name="Coloured Track", color="#123456")
        from pretalx.person.models import User

        spk = User.objects.create_user(password="x", email="spk@example.org", name="Spk Name")

        sub_a = Submission.objects.create(
            title="Full Talk: with a colon and a very longwordthatdoesnotfiteasily here",
            event=event,
            submission_type=submission_type,
            track=track,
            content_locale="en",
            abstract="An abstract.",
            notes="A note\n\n   \nAnother note",
            internal_notes="Internal one\n\n  \nInternal two",
        )
        add_speaker(sub_a, user=spk)
        sub_a.accept()
        sub_a.confirm()

        sub_b = Submission.objects.create(
            title="Bare Talk",
            event=event,
            submission_type=submission_type,
            content_locale="en",
            do_not_record=True,
        )
        sub_b.accept()
        sub_b.confirm()

        q_included = Question.objects.create(
            event=event,
            question="Included?",
            variant="string",
            target=QuestionTarget.SUBMISSION,
            position=0,
        )
        q_excluded = Question.objects.create(
            event=event,
            question="Excluded?",
            variant="string",
            target=QuestionTarget.SUBMISSION,
            position=1,
        )
        q_spk_included = Question.objects.create(
            event=event,
            question="Speaker included?",
            variant="string",
            target=QuestionTarget.SPEAKER,
            position=2,
        )
        q_spk_excluded = Question.objects.create(
            event=event,
            question="Speaker excluded?",
            variant="string",
            target=QuestionTarget.SPEAKER,
            position=3,
        )
        Answer.objects.create(question=q_included, submission=sub_a, answer="included answer")
        Answer.objects.create(question=q_excluded, submission=sub_a, answer="excluded answer")
        profile = sub_a.speakers.first()
        Answer.objects.create(question=q_spk_included, speaker=profile, answer="spk included")
        Answer.objects.create(question=q_spk_excluded, speaker=profile, answer="spk excluded")

        for sub in (sub_a, sub_b):
            TalkSlot.objects.create(
                submission=sub,
                schedule=event.wip_schedule,
                room=room,
                start=event.datetime_from,
                end=event.datetime_from + dt.timedelta(minutes=60),
                is_visible=True,
            )
        freeze_schedule(event.wip_schedule, name="v1")

        event.settings.broadcast_tools_pdf_questions_to_include = f"{q_included.id},{q_spk_included.id}"
        event.settings.broadcast_tools_pdf_show_internal_notes = True
        event.settings.broadcast_tools_pdf_additional_content = "{CODE} - {TALK_SLUG}"
    return event


@pytest.mark.django_db
def test_pdf_exporter_render(rich_schedule):
    event = rich_schedule
    with scope(event=event):
        exporter = PDFExporter(event, schedule=event.current_schedule)
        name, content_type, content = exporter.render()
    assert content_type == "application/pdf"
    assert name.endswith(".pdf")
    assert content.startswith(b"%PDF")


@pytest.mark.django_db
def test_pdf_exporter_render_minimal(event, submission, schedule):
    with scope(event=event):
        exporter = PDFExporter(event, schedule=event.current_schedule)
        name, content_type, content = exporter.render()
    assert content.startswith(b"%PDF")


@pytest.mark.django_db
def test_pdf_exporter_questions_setting_robustness(rich_schedule):
    event = rich_schedule
    with scope(event=event):
        # empty entries and non-numeric junk must not break the export
        event.settings.broadcast_tools_pdf_questions_to_include = "1,, abc , 2 "
        exporter = PDFExporter(event, schedule=event.current_schedule)
        page = next(p for p in exporter._add_pages() if isinstance(p, PDFInfoPage))
        assert page._questions == {1, 2}
        name, content_type, content = exporter.render()
    assert content.startswith(b"%PDF")


@pytest.mark.django_db
def test_pdf_exporter_ignore_do_not_record(rich_schedule):
    event = rich_schedule
    with scope(event=event):
        event.settings.broadcast_tools_pdf_ignore_do_not_record = True
        exporter = PDFExporter(event, schedule=event.current_schedule)
        pages = exporter._add_pages()
    # Two talks, one of which (do_not_record) is skipped -> one page + break
    assert len([p for p in pages if isinstance(p, PDFInfoPage)]) == 1


class _NoLocalTalk:
    """A talk proxy that lacks local_start / local_end to exercise the
    fallback branches in PDFInfoPage.draw()."""

    def __init__(self, talk):
        object.__setattr__(self, "_talk", talk)

    def __getattr__(self, name):
        if name in ("local_start", "local_end"):
            raise AttributeError(name)
        return getattr(self._talk, name)


@pytest.mark.django_db
def test_pdf_info_page_without_local_start(rich_schedule):
    from tempfile import NamedTemporaryFile

    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import PageBreak, SimpleDocTemplate

    event = rich_schedule
    with scope(event=event):
        exporter = PDFExporter(event, schedule=event.current_schedule)
        story = []
        for day in exporter.data:
            for room in day["rooms"]:
                for talk in room["talks"]:
                    story.append(
                        PDFInfoPage(
                            exporter.event,
                            exporter.schedule,
                            day,
                            room,
                            _NoLocalTalk(talk),
                            exporter._style,
                        )
                    )
                    story.append(PageBreak())
        with NamedTemporaryFile(suffix=".pdf") as f:
            doc = SimpleDocTemplate(f.name, pagesize=A4)
            doc.build(story)
            f.seek(0)
            assert f.read().startswith(b"%PDF")
