import csv
import secrets

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .. import finance, forms, initial_import
from ..models import Role
from .common import membership

AMBLUEO_IMPORT_SESSION = "amblueo_import_initial"


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def initial(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, (Role.OWNER,))
    if AMBLUEO_UI_REQUETE.method == "GET" and "modele" in AMBLUEO_UI_REQUETE.GET:
        AMBLUEO_UI_REPONSE = HttpResponse(content_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": 'attachment; filename="import-initial-amblueo.csv"',
        })
        AMBLUEO_UI_REPONSE.write("\ufeff")
        csv.writer(AMBLUEO_UI_REPONSE, delimiter=";").writerow(initial_import.AMBLUEO_IMPORT_COLONNES)
        return AMBLUEO_UI_REPONSE

    AMBLUEO_UI_CTX = {"member": AMBLUEO_UI_MEMBRE, "form": forms.InitialImportForm()}
    if AMBLUEO_UI_REQUETE.method == "POST":
        try:
            if "confirm" in AMBLUEO_UI_REQUETE.POST:
                confirmer(AMBLUEO_UI_REQUETE, AMBLUEO_UI_MEMBRE, AMBLUEO_UI_CTX)
            else:
                previsualiser(AMBLUEO_UI_REQUETE, AMBLUEO_UI_MEMBRE, AMBLUEO_UI_CTX)
        except ValidationError as AMBLUEO_UI_ERREUR:
            AMBLUEO_UI_CTX["errors"] = AMBLUEO_UI_ERREUR.messages
        except UnicodeDecodeError:
            AMBLUEO_UI_CTX["errors"] = ["Enregistrez le fichier CSV au format UTF-8."]
        except IntegrityError:
            AMBLUEO_UI_CTX["errors"] = ["Les données ont changé. Rechargez le fichier pour vérifier un nouvel aperçu."]
    return render(AMBLUEO_UI_REQUETE, "pilot/initial_import.html", AMBLUEO_UI_CTX)


def previsualiser(AMBLUEO_UI_REQUETE, AMBLUEO_UI_MEMBRE, AMBLUEO_UI_CTX):
    AMBLUEO_UI_REQUETE.session.pop(AMBLUEO_IMPORT_SESSION, None)
    AMBLUEO_UI_FORM = forms.InitialImportForm(AMBLUEO_UI_REQUETE.POST, AMBLUEO_UI_REQUETE.FILES)
    AMBLUEO_UI_CTX["form"] = AMBLUEO_UI_FORM
    if not AMBLUEO_UI_FORM.is_valid():
        return
    AMBLUEO_UI_TEXTE = AMBLUEO_UI_FORM.cleaned_data["file"].read().decode("utf-8-sig")
    AMBLUEO_UI_LIGNES, AMBLUEO_UI_ERREURS = initial_import.preparer(AMBLUEO_UI_MEMBRE, AMBLUEO_UI_TEXTE)
    AMBLUEO_UI_CTX["rows"] = [(AMBLUEO_UI_LIGNE, AMBLUEO_UI_ERREURS.get(AMBLUEO_UI_LIGNE.line))
                            for AMBLUEO_UI_LIGNE in AMBLUEO_UI_LIGNES]
    if not AMBLUEO_UI_ERREURS and any(not AMBLUEO_UI_LIGNE.skipped for AMBLUEO_UI_LIGNE in AMBLUEO_UI_LIGNES):
        AMBLUEO_UI_TOTAUX = dict.fromkeys(("budget", "recette", "depense"), finance.AMBLUEO_FINANCE_ZERO)
        for AMBLUEO_UI_LIGNE in AMBLUEO_UI_LIGNES:
            if not AMBLUEO_UI_LIGNE.skipped and AMBLUEO_UI_LIGNE.kind in AMBLUEO_UI_TOTAUX:
                AMBLUEO_UI_TOTAUX[AMBLUEO_UI_LIGNE.kind] += AMBLUEO_UI_LIGNE.instance.amount
        AMBLUEO_UI_CTX["totals"] = AMBLUEO_UI_TOTAUX
        AMBLUEO_UI_JETON = secrets.token_urlsafe(24)
        AMBLUEO_UI_REQUETE.session[AMBLUEO_IMPORT_SESSION] = {
            "company": AMBLUEO_UI_MEMBRE.company_id, "text": AMBLUEO_UI_TEXTE, "token": AMBLUEO_UI_JETON,
        }
        AMBLUEO_UI_CTX["token"] = AMBLUEO_UI_JETON


def confirmer(AMBLUEO_UI_REQUETE, AMBLUEO_UI_MEMBRE, AMBLUEO_UI_CTX):
    AMBLUEO_UI_APERCU = AMBLUEO_UI_REQUETE.session.get(AMBLUEO_IMPORT_SESSION)
    if (not AMBLUEO_UI_APERCU or AMBLUEO_UI_APERCU["company"] != AMBLUEO_UI_MEMBRE.company_id
            or AMBLUEO_UI_APERCU["token"] != AMBLUEO_UI_REQUETE.POST["confirm"]):
        raise ValidationError("Cet aperçu n’est plus disponible. Rechargez le fichier avant de confirmer.")
    AMBLUEO_UI_REQUETE.session.pop(AMBLUEO_IMPORT_SESSION, None)
    AMBLUEO_UI_LIGNES, AMBLUEO_UI_ERREURS = initial_import.confirmer(AMBLUEO_UI_MEMBRE, AMBLUEO_UI_APERCU["text"])
    if AMBLUEO_UI_ERREURS:
        AMBLUEO_UI_CTX["rows"] = [(AMBLUEO_UI_LIGNE, AMBLUEO_UI_ERREURS.get(AMBLUEO_UI_LIGNE.line))
                                for AMBLUEO_UI_LIGNE in AMBLUEO_UI_LIGNES]
        AMBLUEO_UI_CTX["errors"] = ["L’import a été interrompu. Vérifiez les lignes signalées et rechargez le fichier."]
    else:
        AMBLUEO_UI_CTX["imported"] = sum(not AMBLUEO_UI_LIGNE.skipped for AMBLUEO_UI_LIGNE in AMBLUEO_UI_LIGNES)
        AMBLUEO_UI_CTX["skipped"] = len(AMBLUEO_UI_LIGNES) - AMBLUEO_UI_CTX["imported"]
