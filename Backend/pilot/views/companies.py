import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.forms import Form
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .. import finance, forms
from ..email import envoyer_apres_validation
from ..models import Audit, Invitation, Membership, Operation, Project, Role, Task
from .common import (
    AMBLUEO_SECURITE_FINANCE, AMBLUEO_SECURITE_GESTION, AMBLUEO_SECURITE_SUIVI,
    edit, form_data, membership,
)


@login_required
def home(AMBLUEO_UI_REQUETE):
    return render(AMBLUEO_UI_REQUETE, "pilot/home.html", {"memberships":
        Membership.objects.filter(user=AMBLUEO_UI_REQUETE.user, active=True).select_related("company")})


@login_required
def company_new(AMBLUEO_UI_REQUETE):
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_ENTREPRISE = AMBLUEO_UI_FORMULAIRE.save()
        Membership.objects.create(company=AMBLUEO_UI_ENTREPRISE, user=AMBLUEO_UI_REQUETE.user, role=Role.OWNER)
        return redirect("company", AMBLUEO_UI_ENTREPRISE.pk)
    return edit(AMBLUEO_UI_REQUETE, "Créer une entreprise", forms.CompanyForm(form_data(AMBLUEO_UI_REQUETE)), save)


@login_required
def company(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID)
    AMBLUEO_UI_AUJOURDHUI = timezone.localdate()
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).order_by("end", "pk")
    AMBLUEO_UI_RETARDS = Task.objects.filter(
        project__company_id=AMBLUEO_UI_ENTREPRISE_ID, end__lt=AMBLUEO_UI_AUJOURDHUI,
    ).exclude(status="done").select_related("project").order_by("end", "pk")
    AMBLUEO_UI_CTX = dict(
        member=AMBLUEO_UI_MEMBRE,
        projects=AMBLUEO_UI_PROJETS,
        late=AMBLUEO_UI_RETARDS,
        active_count=AMBLUEO_UI_PROJETS.filter(status="active").count(),
        can_manage=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION,
        can_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE,
        can_view_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI,
    )
    if AMBLUEO_UI_CTX["can_view_finance"]:
        AMBLUEO_UI_BUDGETS = [
            (AMBLUEO_UI_PROJET, finance.budget_summary(AMBLUEO_UI_PROJET))
            for AMBLUEO_UI_PROJET in AMBLUEO_UI_PROJETS
        ]
        AMBLUEO_UI_CTX["budgets"] = AMBLUEO_UI_BUDGETS
        AMBLUEO_UI_CTX["risk_projects"] = [
            (AMBLUEO_UI_PROJET, AMBLUEO_UI_STATS)
            for AMBLUEO_UI_PROJET, AMBLUEO_UI_STATS in AMBLUEO_UI_BUDGETS
            if AMBLUEO_UI_STATS["forecast"] < 0
        ]
        AMBLUEO_UI_OPERATIONS = Operation.objects.filter(project__company_id=AMBLUEO_UI_ENTREPRISE_ID)
        AMBLUEO_UI_ECHEANCES = [
            (AMBLUEO_UI_OP, finance.balances(AMBLUEO_UI_OP)[2])
            for AMBLUEO_UI_OP in AMBLUEO_UI_OPERATIONS.filter(
                state=Operation.State.APPROVED, due__lte=AMBLUEO_UI_AUJOURDHUI + timedelta(days=30),
            ).order_by("due", "pk")
        ]
        AMBLUEO_UI_CTX["due"] = [
            (AMBLUEO_UI_OP, AMBLUEO_UI_RESTE) for AMBLUEO_UI_OP, AMBLUEO_UI_RESTE in AMBLUEO_UI_ECHEANCES
            if AMBLUEO_UI_RESTE > 0 and AMBLUEO_UI_OP.due >= AMBLUEO_UI_AUJOURDHUI
        ]
        AMBLUEO_UI_CTX["overdue"] = [
            (AMBLUEO_UI_OP, AMBLUEO_UI_RESTE) for AMBLUEO_UI_OP, AMBLUEO_UI_RESTE in AMBLUEO_UI_ECHEANCES
            if AMBLUEO_UI_RESTE > 0 and AMBLUEO_UI_OP.due < AMBLUEO_UI_AUJOURDHUI
        ]
    if AMBLUEO_UI_CTX["can_finance"]:
        AMBLUEO_UI_CTX["pending_expenses"] = AMBLUEO_UI_OPERATIONS.filter(
            kind=Operation.Kind.EXPENSE, state=Operation.State.SUBMITTED,
        ).select_related("project").order_by("due", "pk")
        AMBLUEO_UI_CTX["cash"] = finance.cash_summary(AMBLUEO_UI_MEMBRE.company)
    if AMBLUEO_UI_MEMBRE.role == Role.OWNER:
        AMBLUEO_UI_CTX["team"] = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).select_related("user")
        AMBLUEO_UI_PREMIER = next(iter(AMBLUEO_UI_PROJETS), None)
        AMBLUEO_UI_BUDGET_APPROUVE = AMBLUEO_UI_PROJETS.filter(budget__approved=True).exists()
        if not (AMBLUEO_UI_BUDGET_APPROUVE and AMBLUEO_UI_CTX["cash"]):
            AMBLUEO_UI_CTX["setup"] = dict(
                project=AMBLUEO_UI_PREMIER,
                budget_project=AMBLUEO_UI_PROJETS.filter(budget__isnull=False).first() or AMBLUEO_UI_PREMIER,
                budget_done=AMBLUEO_UI_BUDGET_APPROUVE,
                cash_done=AMBLUEO_UI_CTX["cash"] is not None,
            )
    return render(AMBLUEO_UI_REQUETE, "pilot/company.html", AMBLUEO_UI_CTX)


@login_required
def company_history(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_FINANCE)
    AMBLUEO_UI_CTX = dict(
        member=AMBLUEO_UI_MEMBRE,
        can_manage=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION,
        can_finance=True,
        can_view_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI,
    )
    AMBLUEO_UI_HISTORIQUE = Audit.objects.filter(
        company_id=AMBLUEO_UI_ENTREPRISE_ID,
    ).select_related("actor")
    AMBLUEO_UI_RECHERCHE = AMBLUEO_UI_REQUETE.GET.get("audit_q", "").strip()
    if AMBLUEO_UI_RECHERCHE:
        AMBLUEO_UI_HISTORIQUE = AMBLUEO_UI_HISTORIQUE.filter(
            Q(actor__username__icontains=AMBLUEO_UI_RECHERCHE)
            | Q(action__icontains=AMBLUEO_UI_RECHERCHE)
            | Q(target__icontains=AMBLUEO_UI_RECHERCHE)
            | Q(reason__icontains=AMBLUEO_UI_RECHERCHE)
        )
    AMBLUEO_UI_CTX["audit_query"] = AMBLUEO_UI_RECHERCHE
    AMBLUEO_UI_CTX["audit_log"] = Paginator(AMBLUEO_UI_HISTORIQUE, 20).get_page(
        AMBLUEO_UI_REQUETE.GET.get("audit_page"),
    )
    return render(AMBLUEO_UI_REQUETE, "pilot/company/history.html", AMBLUEO_UI_CTX)


@login_required
@never_cache
def invite(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, (Role.OWNER,))
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_SECURITE_JETON = secrets.token_urlsafe(32)
        AMBLUEO_UI_INVITATION = AMBLUEO_UI_FORMULAIRE.save(commit=False)
        AMBLUEO_UI_INVITATION.email = AMBLUEO_UI_INVITATION.email.lower()
        AMBLUEO_UI_INVITATION.company = AMBLUEO_UI_MEMBRE.company
        AMBLUEO_UI_INVITATION.digest = hashlib.sha256(AMBLUEO_SECURITE_JETON.encode()).hexdigest()
        AMBLUEO_UI_INVITATION.expires = timezone.now() + timedelta(days=2)
        AMBLUEO_UI_INVITATION.save()
        AMBLUEO_MAIL_LIEN = AMBLUEO_UI_REQUETE.build_absolute_uri(reverse("accept", args=[AMBLUEO_SECURITE_JETON]))
        envoyer_apres_validation(
            AMBLUEO_UI_REQUETE,
            "Votre invitation à Amblueo Services",
            f"Bonjour,\n\nVous avez été invité à rejoindre {AMBLUEO_UI_MEMBRE.company.name} sur Amblueo Services. "
            "Ouvrez le lien pour accepter l’invitation et créer votre compte si nécessaire.\n\n"
            "Ce lien personnel est valable 48 heures et utilisable une seule fois. "
            "Si vous n’attendiez pas cette invitation, vous pouvez ignorer ce message.",
            AMBLUEO_UI_INVITATION.email,
            AMBLUEO_MAIL_LIEN=AMBLUEO_MAIL_LIEN, AMBLUEO_MAIL_ACTION="Accepter l’invitation",
        )
        return render(AMBLUEO_UI_REQUETE, "pilot/link.html", {"link": AMBLUEO_MAIL_LIEN})
    return edit(AMBLUEO_UI_REQUETE, "Inviter un membre", forms.InvitationForm(form_data(AMBLUEO_UI_REQUETE)), save)


@never_cache
def accept(AMBLUEO_UI_REQUETE, AMBLUEO_SECURITE_JETON):
    AMBLUEO_SECURITE_EMPREF = hashlib.sha256(AMBLUEO_SECURITE_JETON.encode()).hexdigest()
    AMBLUEO_UI_INVITATION = get_object_or_404(Invitation, digest=AMBLUEO_SECURITE_EMPREF,
                                            used=False, expires__gt=timezone.now())
    AMBLUEO_UI_COMPTE = AMBLUEO_UI_REQUETE.user
    if AMBLUEO_UI_COMPTE.is_authenticated and AMBLUEO_UI_COMPTE.email.lower() != AMBLUEO_UI_INVITATION.email:
        raise PermissionDenied
    if not AMBLUEO_UI_COMPTE.is_authenticated and get_user_model().objects.filter(email__iexact=AMBLUEO_UI_INVITATION.email).exists():
        return redirect(reverse("login") + "?next=" + reverse("accept", args=[AMBLUEO_SECURITE_JETON]))
    AMBLUEO_UI_FORM = forms.InviteAccountForm(form_data(AMBLUEO_UI_REQUETE))
    if AMBLUEO_UI_COMPTE.is_authenticated:
            AMBLUEO_UI_FORM = Form(form_data(AMBLUEO_UI_REQUETE))

    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_VERROU = get_object_or_404(Invitation.objects.select_for_update(), pk=AMBLUEO_UI_INVITATION.pk,
                                              used=False, expires__gt=timezone.now())
        if AMBLUEO_UI_COMPTE.is_authenticated:
            AMBLUEO_UI_UTILISATEUR = AMBLUEO_UI_COMPTE
        else:
            if get_user_model().objects.filter(email__iexact=AMBLUEO_UI_VERROU.email).exists():
                raise ValidationError("Connectez-vous avec le compte déjà associé à ce courriel.")
            AMBLUEO_UI_UTILISATEUR = AMBLUEO_UI_FORMULAIRE.save(commit=False)
            AMBLUEO_UI_UTILISATEUR.email = AMBLUEO_UI_VERROU.email
            AMBLUEO_UI_UTILISATEUR.save()
        AMBLUEO_UI_ADHESION, AMBLUEO_UI_CREE = Membership.objects.get_or_create(company=AMBLUEO_UI_VERROU.company,
            user=AMBLUEO_UI_UTILISATEUR, defaults={"role": AMBLUEO_UI_VERROU.role})
        if not AMBLUEO_UI_CREE:
            raise ValidationError("Ce compte est déjà rattaché à l’entreprise. Contactez le dirigeant.")
        AMBLUEO_UI_VERROU.used = True
        AMBLUEO_UI_VERROU.save(update_fields=["used"])
        if not AMBLUEO_UI_COMPTE.is_authenticated:
            login(AMBLUEO_UI_REQUETE, AMBLUEO_UI_UTILISATEUR)
        return redirect("company", AMBLUEO_UI_VERROU.company_id)
    return edit(AMBLUEO_UI_REQUETE, "Accepter l’invitation", AMBLUEO_UI_FORM, save)


@login_required
@require_POST
@transaction.atomic
def deactivate(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, (Role.OWNER,))
    AMBLUEO_UI_CIBLE = get_object_or_404(Membership.objects.select_for_update(), company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    if AMBLUEO_UI_CIBLE.role == Role.OWNER:
        raise PermissionDenied
    AMBLUEO_UI_CIBLE.active = False
    AMBLUEO_UI_CIBLE.save(update_fields=["active"])
    finance.audit(AMBLUEO_UI_MEMBRE, "Désactivation", f"Membre {AMBLUEO_UI_OBJET_ID}")
    return redirect("company", AMBLUEO_UI_ENTREPRISE_ID)
