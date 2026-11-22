import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .. import finance, forms
from ..models import Budget, Operation, Project
from .common import AMBLUEO_SECURITE_SUIVI, membership


def csv_text(AMBLUEO_UI_TEXTE):
    """Force le traitement des libellés comme texte par les tableurs."""
    if AMBLUEO_UI_TEXTE.lstrip().startswith(("=", "+", "-", "@")) or AMBLUEO_UI_TEXTE.startswith(("\t", "\r", "\n")):
        return "'" + AMBLUEO_UI_TEXTE
    return AMBLUEO_UI_TEXTE


@login_required
@never_cache
def export(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_SUIVI)
    AMBLUEO_UI_FORM = forms.ExportForm(AMBLUEO_UI_REQUETE.GET)
    AMBLUEO_UI_FORM.fields["project"].queryset = Project.objects.filter(
        company_id=AMBLUEO_UI_ENTREPRISE_ID,
    ).order_by("name", "pk")
    AMBLUEO_EXPORT_CONTEXTE = dict(form=AMBLUEO_UI_FORM, member=AMBLUEO_UI_MEMBRE)
    if not AMBLUEO_UI_FORM.is_valid():
        return render(AMBLUEO_UI_REQUETE, "pilot/export.html", AMBLUEO_EXPORT_CONTEXTE)
    AMBLUEO_UI_DONNEES = AMBLUEO_UI_FORM.cleaned_data
    AMBLUEO_UI_DEBUT, AMBLUEO_UI_FIN = AMBLUEO_UI_DONNEES["start"], AMBLUEO_UI_DONNEES["end"]
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID)
    if AMBLUEO_UI_DONNEES["project"]:
        AMBLUEO_UI_PROJETS = AMBLUEO_UI_PROJETS.filter(pk=AMBLUEO_UI_DONNEES["project"].pk)
    AMBLUEO_UI_OPERATIONS = Operation.objects.filter(project__in=AMBLUEO_UI_PROJETS).order_by("due", "pk")
    if AMBLUEO_UI_DEBUT:
        AMBLUEO_UI_OPERATIONS = AMBLUEO_UI_OPERATIONS.filter(due__gte=AMBLUEO_UI_DEBUT)
    if AMBLUEO_UI_FIN:
        AMBLUEO_UI_OPERATIONS = AMBLUEO_UI_OPERATIONS.filter(due__lte=AMBLUEO_UI_FIN)
    if "download" not in AMBLUEO_UI_REQUETE.GET:
        AMBLUEO_EXPORT_TOTAUX = AMBLUEO_UI_OPERATIONS.aggregate(
            count=Count("pk"),
            expenses=Sum("amount", filter=Q(kind=Operation.Kind.EXPENSE), default=finance.AMBLUEO_FINANCE_ZERO),
            income=Sum("amount", filter=Q(kind=Operation.Kind.INCOME), default=finance.AMBLUEO_FINANCE_ZERO),
        )
        AMBLUEO_EXPORT_TOTAUX["approved_budget"] = finance.total(
            Budget.objects.filter(project__in=AMBLUEO_UI_PROJETS, approved=True),
        )
        AMBLUEO_EXPORT_CONTEXTE.update(
            preview=AMBLUEO_EXPORT_TOTAUX, filters=AMBLUEO_UI_DONNEES,
        )
        return render(AMBLUEO_UI_REQUETE, "pilot/export.html", AMBLUEO_EXPORT_CONTEXTE)
    AMBLUEO_UI_REPONSE = HttpResponse(content_type="text/csv; charset=utf-8",
                                    headers={"Content-Disposition": 'attachment; filename="suivi-amblueo.csv"',
                                             "Cache-Control": "private, no-store"})
    AMBLUEO_UI_REPONSE.write("\ufeff")
    AMBLUEO_UI_CSV = csv.writer(AMBLUEO_UI_REPONSE, delimiter=";")
    AMBLUEO_UI_CSV.writerow(["Type", "Projet", "Libellé", "Échéance", "État", "Devise", "Montant",
                            "Réalisé", "Réglé", "Restant exigible", "Engagé ouvert", "Disponible"])
    for AMBLUEO_UI_PROJET in AMBLUEO_UI_PROJETS:
        AMBLUEO_UI_STATS = finance.budget_summary(AMBLUEO_UI_PROJET)
        AMBLUEO_UI_CSV.writerow(["Budget courant", csv_text(AMBLUEO_UI_PROJET.name), "", "", "",
             AMBLUEO_UI_MEMBRE.company.currency, AMBLUEO_UI_STATS["approved"], AMBLUEO_UI_STATS["realized"],
             "", "", AMBLUEO_UI_STATS["open"], AMBLUEO_UI_STATS["available"]])
    for AMBLUEO_UI_OP in AMBLUEO_UI_OPERATIONS.select_related("project"):
        AMBLUEO_UI_REALISE, AMBLUEO_UI_REGLE, AMBLUEO_UI_RESTE = finance.balances(AMBLUEO_UI_OP)
        AMBLUEO_UI_CSV.writerow([AMBLUEO_UI_OP.get_kind_display(), csv_text(AMBLUEO_UI_OP.project.name),
            csv_text(AMBLUEO_UI_OP.title), AMBLUEO_UI_OP.due, AMBLUEO_UI_OP.get_state_display(),
            AMBLUEO_UI_MEMBRE.company.currency, AMBLUEO_UI_OP.amount, AMBLUEO_UI_REALISE, AMBLUEO_UI_REGLE,
            AMBLUEO_UI_RESTE if AMBLUEO_UI_OP.state == "approved" else "", "", ""])
    return AMBLUEO_UI_REPONSE
