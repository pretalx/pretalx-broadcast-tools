from django.forms import BooleanField, CharField, ChoiceField, Textarea
from django.utils.translation import gettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormField, I18nFormMixin, I18nTextInput


class BroadcastToolsSettingsForm(I18nFormMixin, HierarkeyForm):
    broadcast_tools_lower_thirds_no_talk_info = I18nFormField(
        help_text=_(
            "Will be shown as talk title if there's currently no talk running."
        ),
        label=_('"No talk running" information'),
        widget=I18nTextInput,
        required=True,
    )
    broadcast_tools_lower_thirds_info_string = I18nFormField(
        help_text=_(
            "Will only be shown if there's a talk running. You may use "
            "the place holders mentioned below. The info line will be shown "
            "on the bottom right side of the lower third. Setting this to an "
            "empty string will hide the line entirely."
        ),
        label=_("Info line"),
        required=False,
        widget=I18nTextInput,
    )
    broadcast_tools_lower_thirds_export_voctomix = BooleanField(
        help_text=_(
            "If checked, pretalx will periodically generate voctomix-compatible "
            "lower thirds images and make them available as <code>.tar.gz</code>."
        ),
        label=_("Generate voctomix lower thirds"),
        required=False,
    )

    broadcast_tools_room_info_lower_content = ChoiceField(
        choices=(
            ("", _("No lower content")),
            ("public_qr", _("QR code linking to the 'talk detail' page")),
            (
                "feedback_qr",
                _("QR code linking to the feedback page of the currently running talk"),
            ),
            ("talk_image", _("session image uploaded by the speaker(s)")),
        ),
        help_text=_(
            "If a talk is running, the room info page will always show "
            "the talk title and the list of speakers. The content below "
            "is configurable here."
        ),
        label=_("lower content"),
        required=False,
    )
    broadcast_tools_room_info_show_next_talk = BooleanField(
        help_text=_(
            "If no talk is running in the room, show the time and title of the next talk in the room."
        ),
        label=_("Show next talk"),
        required=False,
    )

    broadcast_tools_pdf_show_internal_notes = BooleanField(
        help_text=_(
            "If checked, the value of the 'internal notes' field in a submission will get added to the pdf export."
        ),
        label=_("Show internal notes in pdf export"),
        required=False,
    )
    broadcast_tools_pdf_ignore_do_not_record = BooleanField(
        help_text=_(
            "If checked, 'do not record' talks will not generate a page in the pdf export."
        ),
        label=_("Ignore 'do not record' talks when generating pdf"),
        required=False,
    )
    broadcast_tools_pdf_questions_to_include = CharField(
        help_text=_(
            "Comma-Separated list of question ids to include in pdf export. If empty, no questions will get added."
        ),
        label=_("Questions to include"),
        required=False,
    )
    broadcast_tools_pdf_additional_content = CharField(
        help_text=_(
            "Additional content to print onto the PDF export. "
            "Will get printed as-is. You may use the place holders "
            "mentioned below."
        ),
        label=_("Additional text"),
        required=False,
        widget=Textarea,
    )
