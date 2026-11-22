import csv
import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.forms import Form
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import finance, forms
from .models import Audit, Budget, CashOpening, Company, Invitation, Membership, Operation, Posting, Project, Role, Task

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


def health(AMBLUEO_INFRA_REQUETE):
    with connection.cursor() as AMBLUEO_INFRA_CURSEUR:
        AMBLUEO_INFRA_CURSEUR.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


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
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).order_by("end", "pk")
    AMBLUEO_UI_RETARDS = Task.objects.filter(project__company_id=AMBLUEO_UI_ENTREPRISE_ID, end__lt=timezone.localdate()).exclude(status="done").select_related("project")
    AMBLUEO_UI_CTX = dict(member=AMBLUEO_UI_MEMBRE, projects=AMBLUEO_UI_PROJETS,
                          late=AMBLUEO_UI_RETARDS, active_count=AMBLUEO_UI_PROJETS.filter(status="active").count(), can_manage=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION,
                          can_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE,
                          can_view_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI)
    if AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI:
        AMBLUEO_UI_CTX["budgets"] = [(AMBLUEO_UI_PROJET, finance.budget_summary(AMBLUEO_UI_PROJET))
                                    for AMBLUEO_UI_PROJET in AMBLUEO_UI_PROJETS]
        AMBLUEO_UI_CTX["due"] = [(AMBLUEO_UI_OP, finance.balances(AMBLUEO_UI_OP)[2])
                                for AMBLUEO_UI_OP in Operation.objects.filter(
                                    project__company_id=AMBLUEO_UI_ENTREPRISE_ID, state="approved",
                                    due__lte=timezone.localdate() + timedelta(days=30)
                                ).order_by("due")]
        AMBLUEO_UI_CTX["due"] = [(AMBLUEO_UI_OP, AMBLUEO_UI_RESTE)
                                for AMBLUEO_UI_OP, AMBLUEO_UI_RESTE in AMBLUEO_UI_CTX["due"]
                                if AMBLUEO_UI_RESTE > 0]
    if AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE:
        AMBLUEO_UI_CTX["cash"] = finance.cash_summary(AMBLUEO_UI_MEMBRE.company)
        AMBLUEO_UI_CTX["audit_log"] = Audit.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).select_related("actor")[:20]
    if AMBLUEO_UI_MEMBRE.role == Role.OWNER:
        AMBLUEO_UI_CTX["team"] = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID).select_related("user")
    return render(AMBLUEO_UI_REQUETE, "pilot/company.html", AMBLUEO_UI_CTX)


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
        return render(AMBLUEO_UI_REQUETE, "pilot/link.html", {"link": AMBLUEO_UI_REQUETE.build_absolute_uri(
            reverse("accept", args=[AMBLUEO_SECURITE_JETON]))})
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


@login_required
def project_edit(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID=None):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_GESTION)
    AMBLUEO_UI_PROJET = get_object_or_404(Project, pk=AMBLUEO_UI_OBJET_ID, company_id=AMBLUEO_UI_ENTREPRISE_ID) if AMBLUEO_UI_OBJET_ID else Project(company=AMBLUEO_UI_MEMBRE.company)
    AMBLUEO_UI_FORM = forms.ProjectForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_PROJET)
    AMBLUEO_UI_FORM.fields["owner"].queryset = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID, active=True)
    def save(AMBLUEO_UI_FORMULAIRE):
        return redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_FORMULAIRE.save().pk)
    return edit(AMBLUEO_UI_REQUETE, "Fiche projet", AMBLUEO_UI_FORM, save)


@login_required
def project(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID)
    AMBLUEO_UI_PROJET = get_object_or_404(Project, company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    AMBLUEO_UI_CTX = dict(member=AMBLUEO_UI_MEMBRE, project=AMBLUEO_UI_PROJET,
        tasks=AMBLUEO_UI_PROJET.task_set.select_related("assignee__user").order_by("end"),
        can_manage=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION,
        can_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_FINANCE,
        can_view_finance=AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI)
    if AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_SUIVI:
        AMBLUEO_UI_CTX.update(budget=Budget.objects.filter(project=AMBLUEO_UI_PROJET).first(),
                              summary=finance.budget_summary(AMBLUEO_UI_PROJET),
                              operations=AMBLUEO_UI_PROJET.operation_set.order_by("due"))
    return render(AMBLUEO_UI_REQUETE, "pilot/project.html", AMBLUEO_UI_CTX)


@login_required
@transaction.atomic
def task_edit(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID, AMBLUEO_UI_TACHE_ID=None):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID)
    AMBLUEO_UI_PROJET = get_object_or_404(Project, company_id=AMBLUEO_UI_ENTREPRISE_ID, pk=AMBLUEO_UI_OBJET_ID)
    AMBLUEO_UI_TACHES = Task.objects.filter(project=AMBLUEO_UI_PROJET)
    if AMBLUEO_UI_REQUETE.method == "POST":
        AMBLUEO_UI_TACHES = AMBLUEO_UI_TACHES.select_for_update()
    AMBLUEO_UI_TACHE = (
        get_object_or_404(AMBLUEO_UI_TACHES, pk=AMBLUEO_UI_TACHE_ID)
        if AMBLUEO_UI_TACHE_ID else Task(project=AMBLUEO_UI_PROJET)
    )
    if AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION:
        AMBLUEO_UI_FORM = forms.TaskForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_TACHE)
        AMBLUEO_UI_FORM.fields["assignee"].queryset = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID, active=True)
    elif AMBLUEO_UI_TACHE_ID and AMBLUEO_UI_TACHE.assignee_id == AMBLUEO_UI_MEMBRE.pk:
        AMBLUEO_UI_FORM = forms.ProgressForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_TACHE)
    else:
        raise PermissionDenied
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_FORMULAIRE.save()
        return redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, "Fiche tâche", AMBLUEO_UI_FORM, save)


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


def csv_text(AMBLUEO_UI_TEXTE):
    """Force le traitement des libellés comme texte par les tableurs."""
    if AMBLUEO_UI_TEXTE.lstrip().startswith(("=", "+", "-", "@")) or AMBLUEO_UI_TEXTE.startswith(("\t", "\r", "\n")):
        return "'" + AMBLUEO_UI_TEXTE
    return AMBLUEO_UI_TEXTE


@login_required
def export(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_SUIVI)
    AMBLUEO_UI_FORM = forms.ExportForm(AMBLUEO_UI_REQUETE.GET if "download" in AMBLUEO_UI_REQUETE.GET else None)
    AMBLUEO_UI_FORM.fields["project"].queryset = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID)
    if not AMBLUEO_UI_FORM.is_valid():
        return render(AMBLUEO_UI_REQUETE, "pilot/export.html", {"form": AMBLUEO_UI_FORM})
    AMBLUEO_UI_DONNEES = AMBLUEO_UI_FORM.cleaned_data
    AMBLUEO_UI_DEBUT, AMBLUEO_UI_FIN = AMBLUEO_UI_DONNEES["start"], AMBLUEO_UI_DONNEES["end"]
    if AMBLUEO_UI_DEBUT and AMBLUEO_UI_FIN and AMBLUEO_UI_DEBUT > AMBLUEO_UI_FIN:
        AMBLUEO_UI_FORM.add_error("end", "La date de fin doit suivre la date de début.")
        return render(AMBLUEO_UI_REQUETE, "pilot/export.html", {"form": AMBLUEO_UI_FORM})
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID)
    if AMBLUEO_UI_DONNEES["project"]:
        AMBLUEO_UI_PROJETS = AMBLUEO_UI_PROJETS.filter(pk=AMBLUEO_UI_DONNEES["project"].pk)
    AMBLUEO_UI_OPERATIONS = Operation.objects.filter(project__in=AMBLUEO_UI_PROJETS).order_by("due", "pk")
    if AMBLUEO_UI_DEBUT:
        AMBLUEO_UI_OPERATIONS = AMBLUEO_UI_OPERATIONS.filter(due__gte=AMBLUEO_UI_DEBUT)
    if AMBLUEO_UI_FIN:
        AMBLUEO_UI_OPERATIONS = AMBLUEO_UI_OPERATIONS.filter(due__lte=AMBLUEO_UI_FIN)
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
