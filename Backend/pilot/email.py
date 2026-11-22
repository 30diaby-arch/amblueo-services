import logging

from django.core.mail import send_mail
from django.db import transaction


AMBLUEO_MAIL_JOURNAL = logging.getLogger(__name__)


def envoyer_apres_validation(AMBLUEO_MAIL_SUJET, AMBLUEO_MAIL_TEXTE, AMBLUEO_MAIL_DESTINATAIRE):
    if not AMBLUEO_MAIL_DESTINATAIRE:
        AMBLUEO_MAIL_JOURNAL.warning("Notification ignorée : compte sans adresse e-mail.")
        return
    def envoyer():
        send_mail(AMBLUEO_MAIL_SUJET, AMBLUEO_MAIL_TEXTE, None, [AMBLUEO_MAIL_DESTINATAIRE])

    transaction.on_commit(envoyer, robust=True)
