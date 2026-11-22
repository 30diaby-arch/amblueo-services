from django.contrib.auth import views as auth
from django.urls import path

from pilot.views import companies, exports, financial, projects, system

urlpatterns = [
    path("health/", system.health, name="health"),
    path("", companies.home, name="home"),
    path("connexion/", auth.LoginView.as_view(), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe/envoye/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("mot-de-passe/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("mot-de-passe/termine/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("e/nouvelle/", companies.company_new, name="company_new"),
    path("invitation/<str:AMBLUEO_SECURITE_JETON>/", companies.accept, name="accept"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/", companies.company, name="company"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/inviter/", companies.invite, name="invite"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/membre/<int:AMBLUEO_UI_OBJET_ID>/desactiver/", companies.deactivate, name="deactivate"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/nouveau/", projects.project_edit, name="project_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/", projects.project, name="project"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/modifier/", projects.project_edit, name="project_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/tache/nouvelle/", projects.task_edit, name="task_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/tache/<int:AMBLUEO_UI_TACHE_ID>/", projects.task_edit, name="task_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/budget/", financial.budget_edit, name="budget_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/budget/approuver/", financial.budget_approve, name="budget_approve"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/operation/<str:AMBLUEO_UI_TYPE>/", financial.operation_new, name="operation_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/", financial.operation, name="operation"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/decision/<str:AMBLUEO_UI_DECISION>/", financial.change_state, name="change_state"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/ecriture/<str:AMBLUEO_UI_TYPE>/", financial.posting_new, name="posting_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/correction/<int:AMBLUEO_UI_ECRITURE_ID>/", financial.posting_void, name="posting_void"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/document/", financial.attachment, name="attachment"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/tresorerie/", financial.opening, name="opening"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/export/", exports.export, name="export"),
]
