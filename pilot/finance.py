"""Calculs et écritures du pilote. Les écritures d'une opération sont sérialisées."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Audit, Budget, CashOpening, Operation, Posting, Project

AMBLUEO_FINANCE_ZERO = Decimal("0")


def audit(AMBLUEO_FINANCE_MEMBRE, AMBLUEO_FINANCE_ACTION, AMBLUEO_FINANCE_CIBLE, AMBLUEO_FINANCE_MOTIF=""):
    """Conserve une décision dans le même périmètre transactionnel que l'écriture."""
    Audit.objects.create(company=AMBLUEO_FINANCE_MEMBRE.company, actor=AMBLUEO_FINANCE_MEMBRE.user,
                         action=AMBLUEO_FINANCE_ACTION, target=AMBLUEO_FINANCE_CIBLE, reason=AMBLUEO_FINANCE_MOTIF)


def money(AMBLUEO_FINANCE_MONTANT, AMBLUEO_FINANCE_DEVISE):
    """Refuse les fractions de franc et laisse les centimes EUR intacts."""
    if AMBLUEO_FINANCE_DEVISE == "XOF" and AMBLUEO_FINANCE_MONTANT != AMBLUEO_FINANCE_MONTANT.to_integral_value():
        raise ValidationError("Le montant en FCFA doit être entier.")
    return AMBLUEO_FINANCE_MONTANT


def total(AMBLUEO_FINANCE_ECRITURES):
    return AMBLUEO_FINANCE_ECRITURES.aggregate(amount=Sum("amount", default=AMBLUEO_FINANCE_ZERO))["amount"]


def balances(AMBLUEO_FINANCE_OPERATION):
    """Calcule le réalisé, le réglé et le solde exigible de l'opération."""
    AMBLUEO_FINANCE_POSTINGS = AMBLUEO_FINANCE_OPERATION.postings.filter(void=False)
    AMBLUEO_FINANCE_REALISE = total(AMBLUEO_FINANCE_POSTINGS.filter(kind=Posting.Kind.REALIZATION))
    AMBLUEO_FINANCE_REGLE = total(AMBLUEO_FINANCE_POSTINGS.filter(kind=Posting.Kind.PAYMENT))
    AMBLUEO_FINANCE_EXIGIBLE = (
        AMBLUEO_FINANCE_REALISE if AMBLUEO_FINANCE_OPERATION.kind == Operation.Kind.EXPENSE
        else AMBLUEO_FINANCE_OPERATION.amount
    )
    return AMBLUEO_FINANCE_REALISE, AMBLUEO_FINANCE_REGLE, AMBLUEO_FINANCE_EXIGIBLE - AMBLUEO_FINANCE_REGLE


def budget_summary(AMBLUEO_BUDGET_PROJET):
    """Un coût réalisé remplace la même part de l'engagement ouvert."""
    AMBLUEO_BUDGET_BUDGET = Budget.objects.filter(project=AMBLUEO_BUDGET_PROJET, approved=True).first()
    AMBLUEO_BUDGET_APPROUVE = AMBLUEO_BUDGET_BUDGET.amount if AMBLUEO_BUDGET_BUDGET else AMBLUEO_FINANCE_ZERO
    AMBLUEO_BUDGET_DEPENSES = Operation.objects.filter(project=AMBLUEO_BUDGET_PROJET, kind="expense")
    AMBLUEO_BUDGET_ENGAGEMENTS = AMBLUEO_BUDGET_DEPENSES.filter(state="approved").aggregate(
        amount=Sum("amount", default=AMBLUEO_FINANCE_ZERO))["amount"]
    AMBLUEO_BUDGET_REALISE = total(Posting.objects.filter(
        operation__in=AMBLUEO_BUDGET_DEPENSES.filter(state="approved"), kind="realization", void=False))
    AMBLUEO_BUDGET_OUVERT = AMBLUEO_BUDGET_ENGAGEMENTS - AMBLUEO_BUDGET_REALISE
    AMBLUEO_BUDGET_DISPONIBLE = AMBLUEO_BUDGET_APPROUVE - AMBLUEO_BUDGET_ENGAGEMENTS
    AMBLUEO_BUDGET_A_VALIDER = AMBLUEO_BUDGET_DEPENSES.filter(state="submitted").aggregate(
        amount=Sum("amount", default=AMBLUEO_FINANCE_ZERO))["amount"]
    return dict(approved=AMBLUEO_BUDGET_APPROUVE, realized=AMBLUEO_BUDGET_REALISE,
                open=AMBLUEO_BUDGET_OUVERT, available=AMBLUEO_BUDGET_DISPONIBLE,
                pending=AMBLUEO_BUDGET_A_VALIDER,
                forecast=AMBLUEO_BUDGET_DISPONIBLE - AMBLUEO_BUDGET_A_VALIDER)


def cash_summary(AMBLUEO_FINANCE_ENTREPRISE):
    """Les échéances passées sont incluses dans l'horizon et signalées à part."""
    AMBLUEO_FINANCE_OUVERTURE = CashOpening.objects.filter(company=AMBLUEO_FINANCE_ENTREPRISE).first()
    if not AMBLUEO_FINANCE_OUVERTURE:
        return None
    AMBLUEO_FINANCE_AUJOURDHUI = timezone.localdate()
    AMBLUEO_FINANCE_HORIZON = AMBLUEO_FINANCE_AUJOURDHUI + timedelta(days=30)
    AMBLUEO_FINANCE_SOLDE = AMBLUEO_FINANCE_OUVERTURE.amount
    AMBLUEO_FINANCE_PREVISION = AMBLUEO_FINANCE_ZERO
    AMBLUEO_FINANCE_IMPAYES = []
    for AMBLUEO_FINANCE_OPERATION in Operation.objects.filter(
        project__company=AMBLUEO_FINANCE_ENTREPRISE, state="approved"
    ).select_related("project").order_by("due", "pk"):
        AMBLUEO_FINANCE_SIGNE = 1 if AMBLUEO_FINANCE_OPERATION.kind == "income" else -1
        AMBLUEO_FINANCE_SOLDE += AMBLUEO_FINANCE_SIGNE * total(AMBLUEO_FINANCE_OPERATION.postings.filter(
            kind="payment", void=False, date__gte=AMBLUEO_FINANCE_OUVERTURE.date,
            date__lte=AMBLUEO_FINANCE_AUJOURDHUI))
        AMBLUEO_FINANCE_REALISE, AMBLUEO_FINANCE_REGLE, AMBLUEO_FINANCE_RESTE = balances(AMBLUEO_FINANCE_OPERATION)
        AMBLUEO_FINANCE_PREVU = AMBLUEO_FINANCE_OPERATION.amount - AMBLUEO_FINANCE_REGLE
        if AMBLUEO_FINANCE_OPERATION.due <= AMBLUEO_FINANCE_HORIZON:
            AMBLUEO_FINANCE_PREVISION += AMBLUEO_FINANCE_SIGNE * AMBLUEO_FINANCE_PREVU
        if AMBLUEO_FINANCE_OPERATION.due < AMBLUEO_FINANCE_AUJOURDHUI and AMBLUEO_FINANCE_RESTE > 0:
            AMBLUEO_FINANCE_IMPAYES.append((AMBLUEO_FINANCE_OPERATION, AMBLUEO_FINANCE_RESTE))
    return dict(current=AMBLUEO_FINANCE_SOLDE, forecast=AMBLUEO_FINANCE_SOLDE + AMBLUEO_FINANCE_PREVISION,
                overdue=AMBLUEO_FINANCE_IMPAYES, horizon=AMBLUEO_FINANCE_HORIZON)


@transaction.atomic
def post(AMBLUEO_FINANCE_MEMBRE, AMBLUEO_FINANCE_OPERATION_ID, AMBLUEO_FINANCE_TYPE,
         AMBLUEO_FINANCE_MONTANT, AMBLUEO_FINANCE_DATE, AMBLUEO_FINANCE_CLE):
    """Enregistre une écriture une fois et vérifie le plafond sous verrou."""
    AMBLUEO_FINANCE_OPERATION = Operation.objects.select_for_update(of=("self",)).get(
        pk=AMBLUEO_FINANCE_OPERATION_ID, project__company=AMBLUEO_FINANCE_MEMBRE.company)
    AMBLUEO_FINANCE_PRECEDENT = Posting.objects.filter(key=AMBLUEO_FINANCE_CLE).first()
    if AMBLUEO_FINANCE_PRECEDENT:
        if (AMBLUEO_FINANCE_PRECEDENT.operation_id, AMBLUEO_FINANCE_PRECEDENT.kind,
            AMBLUEO_FINANCE_PRECEDENT.amount, AMBLUEO_FINANCE_PRECEDENT.date, AMBLUEO_FINANCE_PRECEDENT.author_id) == (
            AMBLUEO_FINANCE_OPERATION_ID, AMBLUEO_FINANCE_TYPE, AMBLUEO_FINANCE_MONTANT,
            AMBLUEO_FINANCE_DATE, AMBLUEO_FINANCE_MEMBRE.pk):
            return AMBLUEO_FINANCE_PRECEDENT
        raise ValidationError("Ce formulaire a déjà été utilisé.")
    if AMBLUEO_FINANCE_OPERATION.state != "approved":
        raise ValidationError("L’opération doit être approuvée.")
    if AMBLUEO_FINANCE_DATE > timezone.localdate():
        raise ValidationError("La date doit être au plus tard aujourd’hui.")
    money(AMBLUEO_FINANCE_MONTANT, AMBLUEO_FINANCE_MEMBRE.company.currency)
    AMBLUEO_FINANCE_REALISE, AMBLUEO_FINANCE_REGLE, AMBLUEO_FINANCE_RESTE = balances(AMBLUEO_FINANCE_OPERATION)
    if AMBLUEO_FINANCE_TYPE == "realization" and AMBLUEO_FINANCE_OPERATION.kind == "expense":
        AMBLUEO_FINANCE_MAXIMUM = AMBLUEO_FINANCE_OPERATION.amount - AMBLUEO_FINANCE_REALISE
    elif AMBLUEO_FINANCE_TYPE == "payment":
        AMBLUEO_FINANCE_MAXIMUM = AMBLUEO_FINANCE_RESTE
    else:
        raise ValidationError("Type d’écriture invalide.")
    if not AMBLUEO_FINANCE_ZERO < AMBLUEO_FINANCE_MONTANT <= AMBLUEO_FINANCE_MAXIMUM:
        raise ValidationError("Le montant dépasse le solde de l’opération ou est nul.")
    return Posting.objects.create(operation=AMBLUEO_FINANCE_OPERATION, amount=AMBLUEO_FINANCE_MONTANT,
                                  kind=AMBLUEO_FINANCE_TYPE, date=AMBLUEO_FINANCE_DATE,
                                  key=AMBLUEO_FINANCE_CLE, author=AMBLUEO_FINANCE_MEMBRE)
