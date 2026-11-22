from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render

from ..models import Membership, Role


AMBLUEO_SECURITE_GESTION = (Role.OWNER, Role.MANAGER)
AMBLUEO_SECURITE_FINANCE = (Role.OWNER, Role.FINANCE)
AMBLUEO_SECURITE_SUIVI = (*AMBLUEO_SECURITE_GESTION, Role.FINANCE)


def membership(AMBLUEO_SECURITE_REQUETE, AMBLUEO_SECURITE_ENTREPRISE, AMBLUEO_SECURITE_ROLES=None):
    """Établit le périmètre de chaque action à partir d'une adhésion active."""
    AMBLUEO_SECURITE_MEMBRE = get_object_or_404(Membership.objects.select_related("company"),
        user=AMBLUEO_SECURITE_REQUETE.user, company_id=AMBLUEO_SECURITE_ENTREPRISE, active=True)
    if AMBLUEO_SECURITE_ROLES and AMBLUEO_SECURITE_MEMBRE.role not in AMBLUEO_SECURITE_ROLES:
        raise PermissionDenied
    return AMBLUEO_SECURITE_MEMBRE


def edit(AMBLUEO_UI_REQUETE, AMBLUEO_UI_TITRE, AMBLUEO_UI_FORMULAIRE, AMBLUEO_UI_ACTION):
    """Valide un formulaire avec CSRF et restitue les erreurs métier à l'écran."""
    if AMBLUEO_UI_REQUETE.method == "POST" and AMBLUEO_UI_FORMULAIRE.is_valid():
        try:
            with transaction.atomic():
                return AMBLUEO_UI_ACTION(AMBLUEO_UI_FORMULAIRE)
        except ValidationError as AMBLUEO_UI_ERREUR:
            AMBLUEO_UI_FORMULAIRE.add_error(None, AMBLUEO_UI_ERREUR)
        except IntegrityError:
            AMBLUEO_UI_FORMULAIRE.add_error(None, "Enregistrement en conflit. Rechargez la page puis réessayez.")
    return render(AMBLUEO_UI_REQUETE, "pilot/form.html", {
        "title": AMBLUEO_UI_TITRE, "form": AMBLUEO_UI_FORMULAIRE,
    })


def form_data(AMBLUEO_UI_REQUETE):
    return AMBLUEO_UI_REQUETE.POST if AMBLUEO_UI_REQUETE.method == "POST" else None
