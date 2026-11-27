from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .. import finance
from ..models import Operation, Posting, Project
from .common import AMBLUEO_SECURITE_FINANCE, membership


AMBLUEO_DASHBOARD_PERIODES = (
    ("1", "Ce mois"), ("3", "3 derniers mois"), ("12", "12 derniers mois"),
)


def flux(AMBLUEO_DASHBOARD_ENTREPRISE, AMBLUEO_DASHBOARD_JOUR, AMBLUEO_DASHBOARD_MOIS):
    AMBLUEO_DASHBOARD_DEBUT = AMBLUEO_DASHBOARD_JOUR.replace(day=1)
    for AMBLUEO_DASHBOARD_INDEX in range(AMBLUEO_DASHBOARD_MOIS - 1):
        AMBLUEO_DASHBOARD_DEBUT = (AMBLUEO_DASHBOARD_DEBUT - timedelta(days=1)).replace(day=1)
    AMBLUEO_DASHBOARD_GROUPES = {}
    AMBLUEO_DASHBOARD_DATE = AMBLUEO_DASHBOARD_DEBUT
    while AMBLUEO_DASHBOARD_DATE <= AMBLUEO_DASHBOARD_JOUR:
        AMBLUEO_DASHBOARD_CLE = (
            (AMBLUEO_DASHBOARD_DATE.day - 1) // 7 if AMBLUEO_DASHBOARD_MOIS == 1
            else AMBLUEO_DASHBOARD_DATE.replace(day=1)
        )
        if AMBLUEO_DASHBOARD_CLE not in AMBLUEO_DASHBOARD_GROUPES:
            AMBLUEO_DASHBOARD_GROUPES[AMBLUEO_DASHBOARD_CLE] = {
                "label": date_format(AMBLUEO_DASHBOARD_DATE, "j M" if AMBLUEO_DASHBOARD_MOIS == 1 else "M y"),
                "income": finance.AMBLUEO_FINANCE_ZERO, "expense": finance.AMBLUEO_FINANCE_ZERO,
            }
        AMBLUEO_DASHBOARD_DATE += timedelta(days=1)

    for AMBLUEO_DASHBOARD_ECRITURE in Posting.objects.filter(
        operation__project__company=AMBLUEO_DASHBOARD_ENTREPRISE,
        operation__state=Operation.State.APPROVED, kind=Posting.Kind.PAYMENT, void=False,
        date__range=(AMBLUEO_DASHBOARD_DEBUT, AMBLUEO_DASHBOARD_JOUR),
    ).order_by().values("date", "operation__kind").annotate(amount=Sum("amount")):
        AMBLUEO_DASHBOARD_DATE = AMBLUEO_DASHBOARD_ECRITURE["date"]
        AMBLUEO_DASHBOARD_CLE = (
            (AMBLUEO_DASHBOARD_DATE.day - 1) // 7 if AMBLUEO_DASHBOARD_MOIS == 1
            else AMBLUEO_DASHBOARD_DATE.replace(day=1)
        )
        AMBLUEO_DASHBOARD_GROUPES[AMBLUEO_DASHBOARD_CLE][AMBLUEO_DASHBOARD_ECRITURE["operation__kind"]] += (
            AMBLUEO_DASHBOARD_ECRITURE["amount"]
        )
    AMBLUEO_DASHBOARD_POINTS = list(AMBLUEO_DASHBOARD_GROUPES.values())
    AMBLUEO_DASHBOARD_MAX = max(
        max(AMBLUEO_DASHBOARD_POINT["income"], AMBLUEO_DASHBOARD_POINT["expense"])
        for AMBLUEO_DASHBOARD_POINT in AMBLUEO_DASHBOARD_POINTS
    )
    AMBLUEO_DASHBOARD_TOTAUX = dict.fromkeys(Operation.Kind.values, finance.AMBLUEO_FINANCE_ZERO)
    for AMBLUEO_DASHBOARD_POINT in AMBLUEO_DASHBOARD_POINTS:
        for AMBLUEO_DASHBOARD_TYPE in Operation.Kind.values:
            AMBLUEO_DASHBOARD_MONTANT = AMBLUEO_DASHBOARD_POINT[AMBLUEO_DASHBOARD_TYPE]
            AMBLUEO_DASHBOARD_TOTAUX[AMBLUEO_DASHBOARD_TYPE] += AMBLUEO_DASHBOARD_MONTANT
            AMBLUEO_DASHBOARD_POINT[f"{AMBLUEO_DASHBOARD_TYPE}_height"] = (
                round(100 * AMBLUEO_DASHBOARD_MONTANT / AMBLUEO_DASHBOARD_MAX) if AMBLUEO_DASHBOARD_MAX else 0
            )
    return AMBLUEO_DASHBOARD_DEBUT, AMBLUEO_DASHBOARD_POINTS, AMBLUEO_DASHBOARD_TOTAUX


def echeances(AMBLUEO_DASHBOARD_ENTREPRISE, AMBLUEO_DASHBOARD_JOUR):
    AMBLUEO_DASHBOARD_SEMAINE = AMBLUEO_DASHBOARD_JOUR + timedelta(days=7)
    AMBLUEO_DASHBOARD_HORIZON = AMBLUEO_DASHBOARD_JOUR + timedelta(days=30)
    AMBLUEO_DASHBOARD_RETARDS = []
    AMBLUEO_DASHBOARD_TRANCHES = [
        {"label": "En retard", "end": AMBLUEO_DASHBOARD_JOUR - timedelta(days=1)},
        {"label": "De J à J+7", "start": AMBLUEO_DASHBOARD_JOUR, "end": AMBLUEO_DASHBOARD_SEMAINE},
        {"label": "De J+8 à J+30", "start": AMBLUEO_DASHBOARD_SEMAINE + timedelta(days=1),
         "end": AMBLUEO_DASHBOARD_HORIZON},
    ]
    for AMBLUEO_DASHBOARD_TRANCHE in AMBLUEO_DASHBOARD_TRANCHES:
        AMBLUEO_DASHBOARD_TRANCHE.update(dict.fromkeys(Operation.Kind.values, finance.AMBLUEO_FINANCE_ZERO))
    for AMBLUEO_DASHBOARD_OPERATION, AMBLUEO_DASHBOARD_RESTE in finance.payment_schedule(Operation.objects.filter(
        project__company=AMBLUEO_DASHBOARD_ENTREPRISE, due__lte=AMBLUEO_DASHBOARD_HORIZON,
    ).select_related("project").order_by("due", "pk")):
        if AMBLUEO_DASHBOARD_OPERATION.due < AMBLUEO_DASHBOARD_JOUR:
            AMBLUEO_DASHBOARD_RETARDS.append((AMBLUEO_DASHBOARD_OPERATION, AMBLUEO_DASHBOARD_RESTE))
        for AMBLUEO_DASHBOARD_TRANCHE in AMBLUEO_DASHBOARD_TRANCHES:
            if AMBLUEO_DASHBOARD_OPERATION.due <= AMBLUEO_DASHBOARD_TRANCHE["end"]:
                AMBLUEO_DASHBOARD_TRANCHE[AMBLUEO_DASHBOARD_OPERATION.kind] += AMBLUEO_DASHBOARD_RESTE
                break
    return AMBLUEO_DASHBOARD_TRANCHES, AMBLUEO_DASHBOARD_RETARDS


def graphique_budget(AMBLUEO_DASHBOARD_BUDGETS):
    AMBLUEO_DASHBOARD_POSTES = sorted(
        ({"label": AMBLUEO_DASHBOARD_PROJET.name, "amount": AMBLUEO_DASHBOARD_STATS["approved"]}
         for AMBLUEO_DASHBOARD_PROJET, AMBLUEO_DASHBOARD_STATS in AMBLUEO_DASHBOARD_BUDGETS
         if AMBLUEO_DASHBOARD_STATS["approved"]),
        key=lambda AMBLUEO_DASHBOARD_POSTE: AMBLUEO_DASHBOARD_POSTE["amount"], reverse=True,
    )
    if len(AMBLUEO_DASHBOARD_POSTES) <= 6:
        return AMBLUEO_DASHBOARD_POSTES
    return [*AMBLUEO_DASHBOARD_POSTES[:6], {
        "label": "Autres projets",
        "amount": sum(AMBLUEO_DASHBOARD_POSTE["amount"] for AMBLUEO_DASHBOARD_POSTE in AMBLUEO_DASHBOARD_POSTES[6:]),
    }]


@login_required
@never_cache
@require_safe
def overview(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    AMBLUEO_UI_PERIODE = AMBLUEO_UI_REQUETE.GET.get("periode", "3")
    if AMBLUEO_UI_PERIODE not in dict(AMBLUEO_DASHBOARD_PERIODES):
        AMBLUEO_UI_PERIODE = "3"
    AMBLUEO_UI_JOUR = timezone.localdate()
    AMBLUEO_UI_DEBUT, AMBLUEO_UI_FLUX, AMBLUEO_UI_TOTAUX = flux(
        AMBLUEO_UI_MEMBRE.company, AMBLUEO_UI_JOUR, int(AMBLUEO_UI_PERIODE),
    )
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).annotate(
        tasks_total=Count("task"),
        tasks_done=Count("task", filter=Q(task__status="done")),
    ).order_by("end", "pk")
    AMBLUEO_UI_BUDGETS = [(AMBLUEO_UI_PROJET, finance.budget_summary(AMBLUEO_UI_PROJET))
                          for AMBLUEO_UI_PROJET in AMBLUEO_UI_PROJETS]
    AMBLUEO_UI_RISQUES = [(AMBLUEO_UI_PROJET, AMBLUEO_UI_STATS)
                         for AMBLUEO_UI_PROJET, AMBLUEO_UI_STATS in AMBLUEO_UI_BUDGETS
                         if AMBLUEO_UI_STATS["forecast"] < 0]
    AMBLUEO_UI_TOTAL_BUDGET = sum(
        (AMBLUEO_UI_STATS["approved"] for _, AMBLUEO_UI_STATS in AMBLUEO_UI_BUDGETS), finance.AMBLUEO_FINANCE_ZERO,
    )
    AMBLUEO_UI_TRANCHES, AMBLUEO_UI_RETARDS = echeances(AMBLUEO_UI_MEMBRE.company, AMBLUEO_UI_JOUR)
    AMBLUEO_UI_DEPENSES = Operation.objects.filter(
        project__company_id=AMBLUEO_UI_ENTREPRISE_ID, kind=Operation.Kind.EXPENSE, state=Operation.State.SUBMITTED,
    ).select_related("project").order_by("due", "pk")
    return render(AMBLUEO_UI_REQUETE, "pilot/dashboard.html", {
        "member": AMBLUEO_UI_MEMBRE, "today": AMBLUEO_UI_JOUR, "period_start": AMBLUEO_UI_DEBUT,
        "period": AMBLUEO_UI_PERIODE, "periods": AMBLUEO_DASHBOARD_PERIODES,
        "flow": AMBLUEO_UI_FLUX, "totals": AMBLUEO_UI_TOTAUX,
        "cash": finance.cash_summary(AMBLUEO_UI_MEMBRE.company),
        "projects": AMBLUEO_UI_PROJETS, "project_count": len(AMBLUEO_UI_PROJETS),
        "budgets": AMBLUEO_UI_BUDGETS, "budget_total": AMBLUEO_UI_TOTAL_BUDGET,
        "risks": AMBLUEO_UI_RISQUES, "overdue": AMBLUEO_UI_RETARDS, "pending": AMBLUEO_UI_DEPENSES[:5],
        "deadlines": AMBLUEO_UI_TRANCHES,
        "has_deadlines": any(
            AMBLUEO_UI_TRANCHE["income"] or AMBLUEO_UI_TRANCHE["expense"] for AMBLUEO_UI_TRANCHE in AMBLUEO_UI_TRANCHES
        ),
        "chart_data": {"currency": AMBLUEO_UI_MEMBRE.company.currency, "flow": AMBLUEO_UI_FLUX,
                       "budgets": graphique_budget(AMBLUEO_UI_BUDGETS), "deadlines": AMBLUEO_UI_TRANCHES},
    })
