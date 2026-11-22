from django.contrib.auth import views as auth
from django.urls import path

from pilot import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path("connexion/", auth.LoginView.as_view(), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe/envoye/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("mot-de-passe/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("mot-de-passe/termine/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("e/nouvelle/", views.company_new, name="company_new"),
    path("invitation/<str:AMBLUEO_SECURITE_JETON>/", views.accept, name="accept"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/", views.company, name="company"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/inviter/", views.invite, name="invite"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/membre/<int:AMBLUEO_UI_OBJET_ID>/desactiver/", views.deactivate, name="deactivate"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/nouveau/", views.project_edit, name="project_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/", views.project, name="project"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/modifier/", views.project_edit, name="project_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/tache/nouvelle/", views.task_edit, name="task_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/tache/<int:AMBLUEO_UI_TACHE_ID>/", views.task_edit, name="task_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/budget/", views.budget_edit, name="budget_edit"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/budget/approuver/", views.budget_approve, name="budget_approve"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/projet/<int:AMBLUEO_UI_OBJET_ID>/operation/<str:AMBLUEO_UI_TYPE>/", views.operation_new, name="operation_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/", views.operation, name="operation"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/decision/<str:AMBLUEO_UI_DECISION>/", views.change_state, name="change_state"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/ecriture/<str:AMBLUEO_UI_TYPE>/", views.posting_new, name="posting_new"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/correction/<int:AMBLUEO_UI_ECRITURE_ID>/", views.posting_void, name="posting_void"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/operation/<int:AMBLUEO_UI_OBJET_ID>/document/", views.attachment, name="attachment"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/tresorerie/", views.opening, name="opening"),
    path("e/<int:AMBLUEO_UI_ENTREPRISE_ID>/export/", views.export, name="export"),
]
