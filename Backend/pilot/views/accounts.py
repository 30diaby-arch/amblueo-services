from django.contrib.auth import views as auth
from django.urls import reverse
from django.utils import timezone

from ..email import envoyer_apres_validation


def notifier_mot_de_passe(AMBLUEO_UI_REQUETE, AMBLUEO_UI_COMPTE):
    envoyer_apres_validation(
        AMBLUEO_UI_REQUETE,
        "Votre mot de passe Amblueo Services a changé",
        "Bonjour,\n\nLe mot de passe de votre compte Amblueo Services a été modifié. "
        "Si vous êtes à l’origine de ce changement, vous n’avez rien à faire.\n\n"
        "Si ce changement vous paraît inhabituel, réinitialisez votre mot de passe immédiatement "
        "et prévenez le dirigeant de votre entreprise si vous ne parvenez plus à accéder à votre compte. "
        "Choisissez une phrase de passe longue et unique et gardez-la confidentielle.",
        AMBLUEO_UI_COMPTE.email,
        AMBLUEO_MAIL_LIEN=AMBLUEO_UI_REQUETE.build_absolute_uri(reverse("password_reset")),
        AMBLUEO_MAIL_ACTION="Réinitialiser mon mot de passe",
    )


class LoginView(auth.LoginView):
    def form_valid(self, form):
        AMBLUEO_UI_REPONSE = super().form_valid(form)
        AMBLUEO_MAIL_HEURE = timezone.localtime().strftime("%d/%m/%Y à %H:%M (%Z)")
        envoyer_apres_validation(
            self.request,
            "Nouvelle connexion à votre compte Amblueo Services",
            f"Bonjour,\n\nUne connexion à votre compte Amblueo Services a réussi le {AMBLUEO_MAIL_HEURE}. "
            "Si vous reconnaissez cette connexion, vous n’avez rien à faire.\n\n"
            "Si elle vous paraît inhabituelle, réinitialisez votre mot de passe immédiatement "
            "et prévenez le dirigeant de votre entreprise si vous ne parvenez plus à accéder à votre compte.",
            self.request.user.email,
            AMBLUEO_MAIL_LIEN=self.request.build_absolute_uri(reverse("password_reset")),
            AMBLUEO_MAIL_ACTION="Réinitialiser mon mot de passe",
        )
        return AMBLUEO_UI_REPONSE


class PasswordChangeView(auth.PasswordChangeView):
    def form_valid(self, form):
        AMBLUEO_UI_REPONSE = super().form_valid(form)
        notifier_mot_de_passe(self.request, self.request.user)
        return AMBLUEO_UI_REPONSE


class PasswordResetConfirmView(auth.PasswordResetConfirmView):
    def form_valid(self, form):
        AMBLUEO_UI_REPONSE = super().form_valid(form)
        notifier_mot_de_passe(self.request, self.user)
        return AMBLUEO_UI_REPONSE
