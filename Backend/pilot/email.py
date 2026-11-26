import logging

from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string


AMBLUEO_MAIL_JOURNAL = logging.getLogger(__name__)


def envoyer_apres_validation(
    AMBLUEO_MAIL_REQUETE, AMBLUEO_MAIL_SUJET, AMBLUEO_MAIL_TEXTE,
    AMBLUEO_MAIL_DESTINATAIRE, *, AMBLUEO_MAIL_LIEN, AMBLUEO_MAIL_ACTION,
):
    if not AMBLUEO_MAIL_DESTINATAIRE:
        AMBLUEO_MAIL_JOURNAL.warning("Notification ignorée : compte sans adresse e-mail.")
        return
    AMBLUEO_MAIL_CONTEXTE = {
        "origin": AMBLUEO_MAIL_REQUETE.build_absolute_uri("/").rstrip("/"),
        "subject": AMBLUEO_MAIL_SUJET,
        "body": AMBLUEO_MAIL_TEXTE,
        "link": AMBLUEO_MAIL_LIEN,
        "action": AMBLUEO_MAIL_ACTION,
    }

    def envoyer():
        send_mail(
            AMBLUEO_MAIL_SUJET, f"{AMBLUEO_MAIL_TEXTE}\n\n{AMBLUEO_MAIL_ACTION} : {AMBLUEO_MAIL_LIEN}",
            None, [AMBLUEO_MAIL_DESTINATAIRE],
            html_message=render_to_string("pilot/email/base.html", AMBLUEO_MAIL_CONTEXTE),
        )

    transaction.on_commit(envoyer, robust=True)
