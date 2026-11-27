"""Prépare et applique une reprise initiale sans écraser les données existantes."""
import csv
import hashlib
import io
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django import forms as django_forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import finance, forms
from .models import Budget, Company, ImportLine, Membership, Operation, Posting, Project, Role

AMBLUEO_IMPORT_COLONNES = (
    "type", "identifiant", "projet", "responsable", "statut", "debut", "fin",
    "montant", "libelle", "categorie", "tiers", "reference", "echeance", "date_realisation",
)
AMBLUEO_IMPORT_CHAMPS = {
    "projet": ("responsable", "statut", "debut", "fin"),
    "budget": ("montant",),
    "recette": ("montant", "libelle", "categorie", "tiers", "reference", "echeance"),
    "depense": ("montant", "libelle", "categorie", "tiers", "reference", "echeance", "date_realisation"),
}
AMBLUEO_IMPORT_LIMITE = 500


@dataclass
class ImportRow:
    line: int
    values: dict
    digest: str
    instance: Project | Budget | Operation | None = None
    realization_date: date | None = None
    skipped: bool = False

    @property
    def kind(self):
        return self.values["type"]


def lire(AMBLUEO_IMPORT_TEXTE):
    AMBLUEO_IMPORT_CSV = csv.reader(io.StringIO(AMBLUEO_IMPORT_TEXTE, newline=""), delimiter=";", strict=True)
    AMBLUEO_IMPORT_LIGNES = []
    if "\x00" in AMBLUEO_IMPORT_TEXTE:
        raise ValidationError("Le fichier contient des caractères non valides.")
    try:
        AMBLUEO_IMPORT_ENTETE = next(AMBLUEO_IMPORT_CSV, [])
        if tuple(AMBLUEO_IMPORT_ENTETE) != AMBLUEO_IMPORT_COLONNES:
            raise ValidationError("L’en-tête doit correspondre au modèle CSV, avec le séparateur point-virgule.")
        while True:
            AMBLUEO_IMPORT_NUMERO = AMBLUEO_IMPORT_CSV.line_num + 1
            AMBLUEO_IMPORT_VALEURS = next(AMBLUEO_IMPORT_CSV, None)
            if AMBLUEO_IMPORT_VALEURS is None:
                break
            if not any(AMBLUEO_IMPORT_VALEURS):
                continue
            if len(AMBLUEO_IMPORT_LIGNES) >= AMBLUEO_IMPORT_LIMITE:
                raise ValidationError("Le fichier peut contenir au maximum 500 lignes de données.")
            if len(AMBLUEO_IMPORT_VALEURS) != len(AMBLUEO_IMPORT_COLONNES):
                raise ValidationError(f"Ligne {AMBLUEO_IMPORT_NUMERO} : nombre de colonnes incorrect.")
            AMBLUEO_IMPORT_VALEURS = [AMBLUEO_IMPORT_VALEUR.strip() for AMBLUEO_IMPORT_VALEUR in AMBLUEO_IMPORT_VALEURS]
            AMBLUEO_IMPORT_EMPREINTE = hashlib.sha256(json.dumps(AMBLUEO_IMPORT_VALEURS).encode()).hexdigest()
            AMBLUEO_IMPORT_LIGNES.append(ImportRow(
                AMBLUEO_IMPORT_NUMERO, dict(zip(AMBLUEO_IMPORT_COLONNES, AMBLUEO_IMPORT_VALEURS)),
                AMBLUEO_IMPORT_EMPREINTE,
            ))
    except csv.Error as AMBLUEO_IMPORT_ERREUR:
        raise ValidationError(f"CSV illisible vers la ligne {AMBLUEO_IMPORT_CSV.line_num}.") from AMBLUEO_IMPORT_ERREUR
    if not AMBLUEO_IMPORT_LIGNES:
        raise ValidationError("Le fichier ne contient aucune ligne de données.")
    return AMBLUEO_IMPORT_LIGNES


def preparer(AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_TEXTE, *, AMBLUEO_IMPORT_VERROU=False):
    AMBLUEO_IMPORT_LIGNES = lire(AMBLUEO_IMPORT_TEXTE)
    AMBLUEO_IMPORT_ENTREPRISE = AMBLUEO_IMPORT_MEMBRE.company
    AMBLUEO_IMPORT_INSCRITS = dict(ImportLine.objects.filter(
        company=AMBLUEO_IMPORT_ENTREPRISE,
        reference__in=[AMBLUEO_IMPORT_LIGNE.values["identifiant"] for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES],
    ).values_list("reference", "digest"))
    AMBLUEO_IMPORT_PROJETS = Project.objects.filter(company=AMBLUEO_IMPORT_ENTREPRISE, name__in={
        AMBLUEO_IMPORT_LIGNE.values["projet"] for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES
    }).order_by("pk")
    if AMBLUEO_IMPORT_VERROU:
        AMBLUEO_IMPORT_PROJETS = AMBLUEO_IMPORT_PROJETS.select_for_update()
    AMBLUEO_IMPORT_PAR_NOM = defaultdict(list)
    for AMBLUEO_IMPORT_PROJET in AMBLUEO_IMPORT_PROJETS:
        AMBLUEO_IMPORT_PAR_NOM[AMBLUEO_IMPORT_PROJET.name].append(AMBLUEO_IMPORT_PROJET)
    AMBLUEO_IMPORT_RESPONSABLES = Membership.objects.filter(
        company=AMBLUEO_IMPORT_ENTREPRISE, active=True, user__username__in={
            AMBLUEO_IMPORT_LIGNE.values["responsable"] for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES
        },
    ).select_related("user").order_by("pk")
    if AMBLUEO_IMPORT_VERROU:
        AMBLUEO_IMPORT_RESPONSABLES = AMBLUEO_IMPORT_RESPONSABLES.select_for_update(of=("self",))
    AMBLUEO_IMPORT_PAR_COMPTE = {
        AMBLUEO_IMPORT_RESP.user.username: AMBLUEO_IMPORT_RESP
        for AMBLUEO_IMPORT_RESP in AMBLUEO_IMPORT_RESPONSABLES
    }
    AMBLUEO_IMPORT_BUDGETS = dict(Budget.objects.filter(
        project_id__in=[AMBLUEO_IMPORT_PROJET.pk for AMBLUEO_IMPORT_PROJET in AMBLUEO_IMPORT_PROJETS],
    ).values_list("project_id", "approved"))
    AMBLUEO_IMPORT_BUDGETS_PREVUS = set()
    AMBLUEO_IMPORT_ERREURS = defaultdict(list)
    AMBLUEO_IMPORT_IDENTIFIANTS = set()

    for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES:
        AMBLUEO_IMPORT_DONNEES = AMBLUEO_IMPORT_LIGNE.values
        AMBLUEO_IMPORT_ID = AMBLUEO_IMPORT_DONNEES["identifiant"]
        AMBLUEO_IMPORT_ERREURS_LIGNE = AMBLUEO_IMPORT_ERREURS[AMBLUEO_IMPORT_LIGNE.line]
        if not AMBLUEO_IMPORT_ID or len(AMBLUEO_IMPORT_ID) > 100:
            AMBLUEO_IMPORT_ERREURS_LIGNE.append("L’identifiant doit contenir de 1 à 100 caractères.")
        if AMBLUEO_IMPORT_ID in AMBLUEO_IMPORT_IDENTIFIANTS:
            AMBLUEO_IMPORT_ERREURS_LIGNE.append("Identifiant répété dans le fichier.")
        AMBLUEO_IMPORT_IDENTIFIANTS.add(AMBLUEO_IMPORT_ID)
        if AMBLUEO_IMPORT_ID in AMBLUEO_IMPORT_INSCRITS:
            if AMBLUEO_IMPORT_INSCRITS[AMBLUEO_IMPORT_ID] == AMBLUEO_IMPORT_LIGNE.digest:
                AMBLUEO_IMPORT_LIGNE.skipped = True
            else:
                AMBLUEO_IMPORT_ERREURS_LIGNE.append("Identifiant déjà importé avec un contenu différent.")
        if AMBLUEO_IMPORT_LIGNE.kind not in AMBLUEO_IMPORT_CHAMPS:
            AMBLUEO_IMPORT_ERREURS_LIGNE.append("Type inconnu. Utilisez projet, budget, recette ou depense.")
            continue
        AMBLUEO_IMPORT_AUTORISES = AMBLUEO_IMPORT_CHAMPS[AMBLUEO_IMPORT_LIGNE.kind]
        for AMBLUEO_IMPORT_CHAMP in ("projet", *AMBLUEO_IMPORT_AUTORISES):
            if not AMBLUEO_IMPORT_DONNEES[AMBLUEO_IMPORT_CHAMP]:
                AMBLUEO_IMPORT_ERREURS_LIGNE.append(f"Colonne obligatoire : {AMBLUEO_IMPORT_CHAMP}.")
        for AMBLUEO_IMPORT_CHAMP in AMBLUEO_IMPORT_COLONNES[3:]:
            if AMBLUEO_IMPORT_DONNEES[AMBLUEO_IMPORT_CHAMP] and AMBLUEO_IMPORT_CHAMP not in AMBLUEO_IMPORT_AUTORISES:
                AMBLUEO_IMPORT_ERREURS_LIGNE.append(f"Colonne à laisser vide : {AMBLUEO_IMPORT_CHAMP}.")

    for AMBLUEO_IMPORT_TYPE in AMBLUEO_IMPORT_CHAMPS:
        for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES:
            if (AMBLUEO_IMPORT_LIGNE.kind != AMBLUEO_IMPORT_TYPE or AMBLUEO_IMPORT_LIGNE.skipped
                    or AMBLUEO_IMPORT_ERREURS[AMBLUEO_IMPORT_LIGNE.line]):
                continue
            try:
                valider_ligne(
                    AMBLUEO_IMPORT_LIGNE, AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_PAR_NOM,
                    AMBLUEO_IMPORT_PAR_COMPTE, AMBLUEO_IMPORT_BUDGETS, AMBLUEO_IMPORT_BUDGETS_PREVUS,
                )
            except ValidationError as AMBLUEO_IMPORT_ERREUR:
                AMBLUEO_IMPORT_ERREURS[AMBLUEO_IMPORT_LIGNE.line].extend(AMBLUEO_IMPORT_ERREUR.messages)

    return AMBLUEO_IMPORT_LIGNES, {
        AMBLUEO_IMPORT_NUMERO: AMBLUEO_IMPORT_MESSAGES
        for AMBLUEO_IMPORT_NUMERO, AMBLUEO_IMPORT_MESSAGES in AMBLUEO_IMPORT_ERREURS.items()
        if AMBLUEO_IMPORT_MESSAGES
    }


def valider_ligne(AMBLUEO_IMPORT_LIGNE, AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_PAR_NOM,
                  AMBLUEO_IMPORT_COMPTE, AMBLUEO_IMPORT_BUDGETS, AMBLUEO_IMPORT_PREVUS):
    AMBLUEO_IMPORT_VALEURS = AMBLUEO_IMPORT_LIGNE.values
    AMBLUEO_IMPORT_NOM = AMBLUEO_IMPORT_VALEURS["projet"]
    AMBLUEO_IMPORT_CIBLES = AMBLUEO_IMPORT_PAR_NOM[AMBLUEO_IMPORT_NOM]
    if AMBLUEO_IMPORT_LIGNE.kind == "projet":
        if AMBLUEO_IMPORT_CIBLES:
            raise ValidationError("Un projet porte déjà ce nom dans l’entreprise.")
        AMBLUEO_IMPORT_RESP = AMBLUEO_IMPORT_COMPTE.get(AMBLUEO_IMPORT_VALEURS["responsable"])
        if not AMBLUEO_IMPORT_RESP:
            raise ValidationError("Le responsable doit être un membre actif de l’entreprise.")
        AMBLUEO_IMPORT_FORM = forms.ProjectForm({
            "name": AMBLUEO_IMPORT_NOM, "owner": AMBLUEO_IMPORT_RESP.pk,
            "status": AMBLUEO_IMPORT_VALEURS["statut"],
            "start": AMBLUEO_IMPORT_VALEURS["debut"], "end": AMBLUEO_IMPORT_VALEURS["fin"],
        }, instance=Project(company=AMBLUEO_IMPORT_MEMBRE.company))
        AMBLUEO_IMPORT_FORM.fields["owner"].queryset = Membership.objects.filter(
            pk=AMBLUEO_IMPORT_RESP.pk, company=AMBLUEO_IMPORT_MEMBRE.company, active=True,
        )
        for AMBLUEO_IMPORT_CHAMP in ("start", "end"):
            AMBLUEO_IMPORT_FORM.fields[AMBLUEO_IMPORT_CHAMP].input_formats = ["%Y-%m-%d"]
        valider_formulaire(AMBLUEO_IMPORT_FORM)
        AMBLUEO_IMPORT_LIGNE.instance = AMBLUEO_IMPORT_FORM.save(commit=False)
        AMBLUEO_IMPORT_PAR_NOM[AMBLUEO_IMPORT_NOM].append(AMBLUEO_IMPORT_LIGNE.instance)
        return

    if len(AMBLUEO_IMPORT_CIBLES) != 1:
        raise ValidationError("Le nom doit désigner un seul projet de cette entreprise ou du fichier.")
    AMBLUEO_IMPORT_PROJET = AMBLUEO_IMPORT_CIBLES[0]
    AMBLUEO_IMPORT_MONTANT = AMBLUEO_IMPORT_VALEURS["montant"].replace(",", ".")
    if AMBLUEO_IMPORT_LIGNE.kind == "budget":
        if AMBLUEO_IMPORT_PROJET.pk in AMBLUEO_IMPORT_BUDGETS or AMBLUEO_IMPORT_NOM in AMBLUEO_IMPORT_PREVUS:
            raise ValidationError("Ce projet a déjà un budget dans Amblueo ou dans ce fichier.")
        AMBLUEO_IMPORT_FORM = forms.BudgetForm(
            {"amount": AMBLUEO_IMPORT_MONTANT}, instance=Budget(project=AMBLUEO_IMPORT_PROJET, approved=True),
        )
    else:
        AMBLUEO_IMPORT_DEPENSE = AMBLUEO_IMPORT_LIGNE.kind == "depense"
        if AMBLUEO_IMPORT_DEPENSE:
            if not (AMBLUEO_IMPORT_BUDGETS.get(AMBLUEO_IMPORT_PROJET.pk) or AMBLUEO_IMPORT_NOM in AMBLUEO_IMPORT_PREVUS):
                raise ValidationError("Une dépense à reprendre nécessite un budget approuvé pour le projet.")
            AMBLUEO_IMPORT_LIGNE.realization_date = django_forms.DateField(input_formats=["%Y-%m-%d"]).clean(
                AMBLUEO_IMPORT_VALEURS["date_realisation"]
            )
            if AMBLUEO_IMPORT_LIGNE.realization_date > timezone.localdate():
                raise ValidationError("La date de réalisation doit être au plus tard aujourd’hui.")
        AMBLUEO_IMPORT_FORM = forms.OperationForm({
            "title": AMBLUEO_IMPORT_VALEURS["libelle"], "category": AMBLUEO_IMPORT_VALEURS["categorie"],
            "amount": AMBLUEO_IMPORT_MONTANT, "due": AMBLUEO_IMPORT_VALEURS["echeance"],
            "counterparty": AMBLUEO_IMPORT_VALEURS["tiers"], "external_reference": AMBLUEO_IMPORT_VALEURS["reference"],
        }, instance=Operation(
            project=AMBLUEO_IMPORT_PROJET, author=AMBLUEO_IMPORT_MEMBRE, state=Operation.State.APPROVED,
            kind=Operation.Kind.EXPENSE if AMBLUEO_IMPORT_DEPENSE else Operation.Kind.INCOME,
        ))
        AMBLUEO_IMPORT_FORM.fields["due"].input_formats = ["%Y-%m-%d"]
    valider_formulaire(AMBLUEO_IMPORT_FORM)
    finance.money(AMBLUEO_IMPORT_FORM.cleaned_data["amount"], AMBLUEO_IMPORT_MEMBRE.company.currency)
    AMBLUEO_IMPORT_LIGNE.instance = AMBLUEO_IMPORT_FORM.save(commit=False)
    if AMBLUEO_IMPORT_LIGNE.kind == "budget":
        AMBLUEO_IMPORT_PREVUS.add(AMBLUEO_IMPORT_NOM)


def valider_formulaire(AMBLUEO_IMPORT_FORM):
    if not AMBLUEO_IMPORT_FORM.is_valid():
        raise ValidationError([
            f"{AMBLUEO_IMPORT_FORM.fields[AMBLUEO_IMPORT_CHAMP].label} : {AMBLUEO_IMPORT_MESSAGE}"
            if AMBLUEO_IMPORT_CHAMP in AMBLUEO_IMPORT_FORM.fields else str(AMBLUEO_IMPORT_MESSAGE)
            for AMBLUEO_IMPORT_CHAMP, AMBLUEO_IMPORT_MESSAGES in AMBLUEO_IMPORT_FORM.errors.items()
            for AMBLUEO_IMPORT_MESSAGE in AMBLUEO_IMPORT_MESSAGES
        ])


@transaction.atomic
def confirmer(AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_TEXTE):
    Company.objects.select_for_update().get(pk=AMBLUEO_IMPORT_MEMBRE.company_id)
    if not Membership.objects.select_for_update().filter(
        pk=AMBLUEO_IMPORT_MEMBRE.pk, company_id=AMBLUEO_IMPORT_MEMBRE.company_id, active=True, role=Role.OWNER,
    ).exists():
        raise PermissionDenied
    AMBLUEO_IMPORT_LIGNES, AMBLUEO_IMPORT_ERREURS = preparer(
        AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_TEXTE, AMBLUEO_IMPORT_VERROU=True,
    )
    if AMBLUEO_IMPORT_ERREURS:
        return AMBLUEO_IMPORT_LIGNES, AMBLUEO_IMPORT_ERREURS
    AMBLUEO_IMPORT_NOMBRE = 0
    for AMBLUEO_IMPORT_TYPE in AMBLUEO_IMPORT_CHAMPS:
        for AMBLUEO_IMPORT_LIGNE in AMBLUEO_IMPORT_LIGNES:
            if AMBLUEO_IMPORT_LIGNE.kind != AMBLUEO_IMPORT_TYPE or AMBLUEO_IMPORT_LIGNE.skipped:
                continue
            AMBLUEO_IMPORT_LIGNE.instance.save()
            if AMBLUEO_IMPORT_LIGNE.realization_date:
                finance.post(
                    AMBLUEO_IMPORT_MEMBRE, AMBLUEO_IMPORT_LIGNE.instance.pk, Posting.Kind.REALIZATION,
                    AMBLUEO_IMPORT_LIGNE.instance.amount, AMBLUEO_IMPORT_LIGNE.realization_date, uuid.uuid4(),
                )
            ImportLine.objects.create(
                company=AMBLUEO_IMPORT_MEMBRE.company, reference=AMBLUEO_IMPORT_LIGNE.values["identifiant"],
                digest=AMBLUEO_IMPORT_LIGNE.digest,
            )
            AMBLUEO_IMPORT_NOMBRE += 1
    if AMBLUEO_IMPORT_NOMBRE:
        finance.audit(
            AMBLUEO_IMPORT_MEMBRE, "Import initial CSV", f"Entreprise {AMBLUEO_IMPORT_MEMBRE.company_id}",
            f"{AMBLUEO_IMPORT_NOMBRE} lignes importées.",
        )
    return AMBLUEO_IMPORT_LIGNES, {}
