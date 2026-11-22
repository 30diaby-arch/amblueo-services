import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms import Form
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import finance, forms
from ..models import Budget, CashOpening, Operation, Posting, Project
from .common import AMBLUEO_SECURITE_FINANCE, AMBLUEO_SECURITE_SUIVI, edit, form_data, membership


@login_required
def budget_edit(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_SUIVI)
    AMBLUEO_UI_PROJET = get_object_or_404(Project, company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    AMBLUEO_UI_BUDGET = Budget.objects.filter(project=AMBLUEO_UI_PROJET).first() or Budget(project=AMBLUEO_UI_PROJET)
    if AMBLUEO_UI_BUDGET.approved:
        raise PermissionDenied
    def save(AMBLUEO_UI_FORMULAIRE):
        Project.objects.select_for_update().get(pk=AMBLUEO_UI_OBJET_ID)
        if Budget.objects.filter(project_id=AMBLUEO_UI_OBJET_ID, approved=True).exists():
            raise ValidationError("Ce budget est déjà approuvé.")
        finance.money(AMBLUEO_UI_FORMULAIRE.cleaned_data["amount"], AMBLUEO_UI_MEMBRE.company.currency)
        AMBLUEO_UI_FORMULAIRE.save()
        return redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, "Budget du projet", forms.BudgetForm(
        form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_BUDGET), save)


@login_required
@require_POST
@transaction.atomic
def budget_approve(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    AMBLUEO_UI_PROJET = get_object_or_404(Project.objects.select_for_update(), company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    AMBLUEO_UI_BUDGET = get_object_or_404(Budget, project=AMBLUEO_UI_PROJET)
    if not AMBLUEO_UI_BUDGET.approved:
        AMBLUEO_UI_BUDGET.approved = True
        AMBLUEO_UI_BUDGET.save(update_fields=["approved"])
        finance.audit(AMBLUEO_UI_MEMBRE, "Approbation budget", f"Projet {AMBLUEO_UI_OBJET_ID}")
    return redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)


@login_required
def operation_new(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_TYPE):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID,
        AMBLUEO_SECURITE_FINANCE if AMBLUEO_UI_TYPE == "income" else AMBLUEO_SECURITE_SUIVI)
    if AMBLUEO_UI_TYPE not in Operation.Kind.values:
        raise PermissionDenied
    AMBLUEO_UI_PROJET = get_object_or_404(Project, company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    AMBLUEO_UI_OPERATION = Operation(project=AMBLUEO_UI_PROJET, kind=AMBLUEO_UI_TYPE, author=AMBLUEO_UI_MEMBRE)
    def save(AMBLUEO_UI_FORMULAIRE):
        finance.money(AMBLUEO_UI_FORMULAIRE.cleaned_data["amount"], AMBLUEO_UI_MEMBRE.company.currency)
        return redirect("operation", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_FORMULAIRE.save().pk)
    return edit(AMBLUEO_UI_REQUETE, "Nouvelle opération",
                forms.OperationForm(form_data(AMBLUEO_UI_REQUETE), AMBLUEO_UI_REQUETE.FILES,
                                    instance=AMBLUEO_UI_OPERATION), save)


@login_required
def operation(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_SUIVI)
    AMBLUEO_UI_OP = get_object_or_404(Operation, project__company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    return render(AMBLUEO_UI_REQUETE, "pilot/operation.html", dict(
        member=AMBLUEO_UI_MEMBRE, op=AMBLUEO_UI_OP, balances=finance.balances(AMBLUEO_UI_OP),
        postings=AMBLUEO_UI_OP.postings.order_by("date", "pk"),
        can_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE,
        can_submit=AMBLUEO_UI_MEMBRE.pk == AMBLUEO_UI_OP.author_id or AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE))


@login_required
def change_state(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_DECISION):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID,
        AMBLUEO_SECURITE_SUIVI if AMBLUEO_UI_DECISION == "submit" else AMBLUEO_SECURITE_FINANCE)
    AMBLUEO_UI_OP = get_object_or_404(Operation, project__company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    if AMBLUEO_UI_DECISION == "submit" and AMBLUEO_UI_OP.author_id != AMBLUEO_UI_MEMBRE.pk and AMBLUEO_UI_MEMBRE.role not in AMBLUEO_SECURITE_FINANCE:
        raise PermissionDenied
    AMBLUEO_UI_FORM = (forms.ReasonForm if AMBLUEO_UI_DECISION in ("cancel", "reject") else Form)(form_data(AMBLUEO_UI_REQUETE))

    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_CIBLE = Operation.objects.select_for_update().get(pk=AMBLUEO_UI_OP.pk)
        AMBLUEO_UI_TRANSITIONS = {
            ("draft", "submit"): "submitted", ("submitted", "approve"): "approved",
            ("submitted", "reject"): "rejected", ("approved", "cancel"): "cancelled",
        }
        AMBLUEO_UI_ETAT = AMBLUEO_UI_TRANSITIONS.get((AMBLUEO_UI_CIBLE.state, AMBLUEO_UI_DECISION))
        if not AMBLUEO_UI_ETAT:
            raise ValidationError("Cette action est indisponible dans l’état actuel.")
        if AMBLUEO_UI_DECISION == "approve" and AMBLUEO_UI_CIBLE.kind == "expense" and not Budget.objects.filter(
            project=AMBLUEO_UI_CIBLE.project, approved=True
        ).exists():
            raise ValidationError("Approuvez le budget avant d’engager cette dépense.")
        if AMBLUEO_UI_DECISION == "cancel" and AMBLUEO_UI_CIBLE.postings.filter(void=False).exists():
            raise ValidationError("Annulez d’abord les règlements puis les réalisations associés.")
        AMBLUEO_UI_CIBLE.state = AMBLUEO_UI_ETAT
        AMBLUEO_UI_CIBLE.save(update_fields=["state"])
        finance.audit(AMBLUEO_UI_MEMBRE, dict(submit="Soumission", approve="Approbation",
            reject="Rejet", cancel="Annulation")[AMBLUEO_UI_DECISION], f"Opération {AMBLUEO_UI_OBJET_ID}", AMBLUEO_UI_FORMULAIRE.cleaned_data.get("reason", ""))
        return redirect("operation", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, "Confirmer la décision", AMBLUEO_UI_FORM, save)


@login_required
def posting_new(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_TYPE):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    get_object_or_404(Operation, project__company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    if AMBLUEO_UI_TYPE not in Posting.Kind.values:
        raise PermissionDenied
    AMBLUEO_UI_FORM = forms.PostingForm(form_data(AMBLUEO_UI_REQUETE),
                                       initial={"key": uuid.uuid4(), "date": timezone.localdate()})
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_DONNEES = AMBLUEO_UI_FORMULAIRE.cleaned_data
        finance.post(AMBLUEO_UI_MEMBRE, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_TYPE, AMBLUEO_UI_DONNEES["amount"],
                     AMBLUEO_UI_DONNEES["date"], AMBLUEO_UI_DONNEES["key"])
        return redirect("operation", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, dict(payment="Enregistrer un règlement",
                realization="Enregistrer un coût réalisé")[AMBLUEO_UI_TYPE], AMBLUEO_UI_FORM, save)


@login_required
def posting_void(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_ECRITURE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    get_object_or_404(Operation, project__company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_OP = Operation.objects.select_for_update().get(pk=AMBLUEO_UI_OBJET_ID)
        AMBLUEO_UI_ECRITURE = get_object_or_404(Posting, operation=AMBLUEO_UI_OP, pk=AMBLUEO_UI_ECRITURE_ID, void=False)
        AMBLUEO_UI_REALISE, AMBLUEO_UI_REGLE, AMBLUEO_UI_RESTE = finance.balances(AMBLUEO_UI_OP)
        if AMBLUEO_UI_ECRITURE.kind == "realization" and AMBLUEO_UI_ECRITURE.amount > AMBLUEO_UI_RESTE:
            raise ValidationError("Annulez d’abord les règlements qui dépasseraient le réalisé corrigé.")
        AMBLUEO_UI_ECRITURE.void = True
        AMBLUEO_UI_ECRITURE.save(update_fields=["void"])
        finance.audit(AMBLUEO_UI_MEMBRE, "Correction d’écriture", f"Écriture {AMBLUEO_UI_ECRITURE_ID}",
                      AMBLUEO_UI_FORMULAIRE.cleaned_data["reason"])
        return redirect("operation", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, "Annuler une écriture", forms.ReasonForm(form_data(AMBLUEO_UI_REQUETE)), save)


@login_required
def attachment(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_SUIVI)
    AMBLUEO_UI_OP = get_object_or_404(Operation.objects.exclude(evidence=""), project__company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    try:
        AMBLUEO_UI_FICHIER = AMBLUEO_UI_OP.evidence.open("rb")
    except FileNotFoundError as AMBLUEO_UI_ERREUR:
        raise Http404 from AMBLUEO_UI_ERREUR
    AMBLUEO_UI_REPONSE = FileResponse(AMBLUEO_UI_FICHIER, as_attachment=True, filename=f"justificatif-{AMBLUEO_UI_OBJET_ID}",
                                     content_type="application/octet-stream")
    AMBLUEO_UI_REPONSE["Cache-Control"] = "private, no-store"
    return AMBLUEO_UI_REPONSE


@login_required
def opening(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    if CashOpening.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).exists():
        raise PermissionDenied
    def save(AMBLUEO_UI_FORMULAIRE):
        finance.money(AMBLUEO_UI_FORMULAIRE.cleaned_data["amount"], AMBLUEO_UI_MEMBRE.company.currency)
        if AMBLUEO_UI_FORMULAIRE.cleaned_data["date"] > timezone.localdate():
            raise ValidationError("La date de référence doit être au plus tard aujourd’hui.")
        AMBLUEO_UI_FORMULAIRE.save()
        finance.audit(AMBLUEO_UI_MEMBRE, "Ouverture trésorerie", f"Entreprise {AMBLUEO_UI_ENTREPRISE_ID}")
        return redirect("company", AMBLUEO_UI_ENTREPRISE_ID)
    return edit(AMBLUEO_UI_REQUETE, "Initialiser la trésorerie",
                forms.OpeningForm(form_data(AMBLUEO_UI_REQUETE),
                                  instance=CashOpening(company=AMBLUEO_UI_MEMBRE.company),
                                  initial={"date": timezone.localdate()}), save)
