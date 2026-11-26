from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .. import finance, forms
from ..email import envoyer_apres_validation
from ..models import Budget, Membership, Project, Task
from .common import (
    AMBLUEO_SECURITE_FINANCE, AMBLUEO_SECURITE_GESTION, AMBLUEO_SECURITE_SUIVI,
    edit, form_data, membership,
)


@login_required
@transaction.atomic
def project_edit(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID=None):
    AMBLUEO_UI_MEMBRE = membership(AMBLUEO_UI_REQUETE, AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_SECURITE_GESTION)
    AMBLUEO_UI_PROJETS = Project.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID)
    if AMBLUEO_UI_REQUETE.method == "POST":
        AMBLUEO_UI_PROJETS = AMBLUEO_UI_PROJETS.select_for_update()
    AMBLUEO_UI_PROJET = get_object_or_404(AMBLUEO_UI_PROJETS, pk=AMBLUEO_UI_OBJET_ID) if AMBLUEO_UI_OBJET_ID else Project(company=AMBLUEO_UI_MEMBRE.company)
    AMBLUEO_MAIL_ANCIEN_RESPONSABLE = AMBLUEO_UI_PROJET.owner_id
    AMBLUEO_UI_FORM = forms.ProjectForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_PROJET)
    AMBLUEO_UI_FORM.fields["owner"].queryset = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID, active=True)
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_PROJET_ENREGISTRE = AMBLUEO_UI_FORMULAIRE.save()
        AMBLUEO_UI_REPONSE = redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_PROJET_ENREGISTRE.pk)
        if AMBLUEO_UI_PROJET_ENREGISTRE.owner_id != AMBLUEO_MAIL_ANCIEN_RESPONSABLE:
            AMBLUEO_MAIL_LIEN = AMBLUEO_UI_REQUETE.build_absolute_uri(AMBLUEO_UI_REPONSE.url)
            envoyer_apres_validation(
                AMBLUEO_UI_REQUETE,
                "Un projet vous a été confié",
                f"Bonjour,\n\nVous êtes désormais responsable du projet « {AMBLUEO_UI_PROJET_ENREGISTRE.name} ».\n\n"
                "Ouvrez le projet pour consulter son échéance et les tâches associées.",
                AMBLUEO_UI_PROJET_ENREGISTRE.owner.user.email,
                AMBLUEO_MAIL_LIEN=AMBLUEO_MAIL_LIEN, AMBLUEO_MAIL_ACTION="Ouvrir le projet",
            )
        return AMBLUEO_UI_REPONSE
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
    AMBLUEO_MAIL_ANCIEN_MEMBRE = AMBLUEO_UI_TACHE.assignee_id
    if AMBLUEO_UI_MEMBRE.role in AMBLUEO_SECURITE_GESTION:
        AMBLUEO_UI_FORM = forms.TaskForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_TACHE)
        AMBLUEO_UI_FORM.fields["assignee"].queryset = Membership.objects.filter(company_id=AMBLUEO_UI_ENTREPRISE_ID, active=True)
    elif AMBLUEO_UI_TACHE_ID and AMBLUEO_UI_TACHE.assignee_id == AMBLUEO_UI_MEMBRE.pk:
        AMBLUEO_UI_FORM = forms.ProgressForm(form_data(AMBLUEO_UI_REQUETE), instance=AMBLUEO_UI_TACHE)
    else:
        raise PermissionDenied
    def save(AMBLUEO_UI_FORMULAIRE):
        AMBLUEO_UI_TACHE_ENREGISTREE = AMBLUEO_UI_FORMULAIRE.save()
        if AMBLUEO_UI_TACHE_ENREGISTREE.assignee_id != AMBLUEO_MAIL_ANCIEN_MEMBRE:
            AMBLUEO_MAIL_LIEN = AMBLUEO_UI_REQUETE.build_absolute_uri(reverse(
                "project", args=[AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID],
            ))
            envoyer_apres_validation(
                AMBLUEO_UI_REQUETE,
                "Une tâche vous a été attribuée",
                f"Bonjour,\n\nLa tâche « {AMBLUEO_UI_TACHE_ENREGISTREE.title} » du projet « {AMBLUEO_UI_PROJET.name} » "
                f"vous a été attribuée. Son échéance est le {AMBLUEO_UI_TACHE_ENREGISTREE.end:%d/%m/%Y}.\n\n"
                "Ouvrez le projet pour consulter la tâche et mettre à jour son avancement.",
                AMBLUEO_UI_TACHE_ENREGISTREE.assignee.user.email,
                AMBLUEO_MAIL_LIEN=AMBLUEO_MAIL_LIEN, AMBLUEO_MAIL_ACTION="Voir la tâche dans le projet",
            )
        return redirect("project", AMBLUEO_UI_ENTREPRISE_ID, AMBLUEO_UI_OBJET_ID)
    return edit(AMBLUEO_UI_REQUETE, "Fiche tâche", AMBLUEO_UI_FORM, save)
