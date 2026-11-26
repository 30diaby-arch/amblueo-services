import csv
import io
import re
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest import skipUnless

from . import finance
from .models import Audit, Budget, Company, Membership, Operation, Posting, Project, Role, Task, User


class PilotTest(TestCase):
    def setUp(self):
        AMBLUEO_TEST_TMP = tempfile.TemporaryDirectory()
        self.addCleanup(AMBLUEO_TEST_TMP.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=AMBLUEO_TEST_TMP.name))
        self.AMBLUEO_TEST_A = Company.objects.create(name="Alpha", currency="XOF")
        self.AMBLUEO_TEST_B = Company.objects.create(name="Beta privée", currency="EUR")
        self.AMBLUEO_TEST_OWNER = self.member(self.AMBLUEO_TEST_A, Role.OWNER, "dirigeant")
        self.AMBLUEO_TEST_MANAGER = self.member(self.AMBLUEO_TEST_A, Role.MANAGER, "projet")
        self.AMBLUEO_TEST_FIN = self.member(self.AMBLUEO_TEST_A, Role.FINANCE, "finance")
        self.AMBLUEO_TEST_MEMBER = self.member(self.AMBLUEO_TEST_A, Role.MEMBER, "collab")
        self.AMBLUEO_TEST_OTHER = self.member(self.AMBLUEO_TEST_B, Role.OWNER, "autre")
        self.AMBLUEO_TEST_DATE = timezone.localdate().isoformat()

    def member(self, AMBLUEO_TEST_COMPANY, AMBLUEO_TEST_ROLE, AMBLUEO_TEST_NOM):
        return Membership.objects.create(company=AMBLUEO_TEST_COMPANY, role=AMBLUEO_TEST_ROLE,
            user=User.objects.create_user(AMBLUEO_TEST_NOM, f"{AMBLUEO_TEST_NOM}@example.test", "Mot-de-passe-test-55"))

    def project(self, AMBLUEO_TEST_MEMBRE, AMBLUEO_TEST_NOM):
        return Project.objects.create(company=AMBLUEO_TEST_MEMBRE.company, owner=AMBLUEO_TEST_MEMBRE,
            name=AMBLUEO_TEST_NOM, start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE, status="active")

    def test_company_invitation_deactivation_and_reset(self):
        self.client.force_login(self.AMBLUEO_TEST_OWNER.user)
        self.assertEqual(self.client.post(reverse("company_new"), {"name": "Nouvelle", "currency": "EUR"}).status_code, 302)
        with self.captureOnCommitCallbacks(execute=True):
            AMBLUEO_TEST_INVITATION = self.client.post(reverse("invite", args=[self.AMBLUEO_TEST_A.pk]),
                                                      {"email": "invite@example.test", "role": "member"})
        AMBLUEO_TEST_URL = re.search(r'/invitation/[^/"]+/', AMBLUEO_TEST_INVITATION.content.decode()).group()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["invite@example.test"])
        self.assertIn(f"http://testserver{AMBLUEO_TEST_URL}", mail.outbox[0].body)
        self.client.logout()
        self.assertEqual(self.client.post(AMBLUEO_TEST_URL, dict(username="invite",
            password1="Nouveau-Soleil-42", password2="Nouveau-Soleil-42")).status_code, 302)
        AMBLUEO_TEST_MEMBRE = Membership.objects.get(user__username="invite")
        self.assertEqual(self.client.get(AMBLUEO_TEST_URL).status_code, 404)
        self.client.force_login(self.AMBLUEO_TEST_OWNER.user)
        self.assertEqual(self.client.post(reverse("deactivate", args=[self.AMBLUEO_TEST_A.pk, AMBLUEO_TEST_MEMBRE.pk])).status_code, 302)
        self.client.force_login(AMBLUEO_TEST_MEMBRE.user)
        self.assertEqual(self.client.get(reverse("company", args=[self.AMBLUEO_TEST_A.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("password_reset"), {"email": "invite@example.test"}).status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("/mot-de-passe/", mail.outbox[1].body)

    def test_account_security_notifications(self):
        AMBLUEO_TEST_USER = self.AMBLUEO_TEST_OWNER.user
        AMBLUEO_TEST_LOGIN = reverse("login")
        AMBLUEO_TEST_PASSWORD = "Mot-de-passe-test-55"
        AMBLUEO_TEST_NEW_PASSWORD = "Nouvelle-phrase-de-passe-2026!"
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(AMBLUEO_TEST_LOGIN, {"username": AMBLUEO_TEST_USER.username, "password": "incorrect"})
        self.assertEqual(len(mail.outbox), 0)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(AMBLUEO_TEST_LOGIN, {
                "username": AMBLUEO_TEST_USER.username, "password": AMBLUEO_TEST_PASSWORD,
            }).status_code, 302)
        self.assertEqual(mail.outbox[0].to, [AMBLUEO_TEST_USER.email])
        self.assertIn("Nouvelle connexion", mail.outbox[0].subject)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(reverse("password_change"), {
                "old_password": AMBLUEO_TEST_PASSWORD,
                "new_password1": AMBLUEO_TEST_NEW_PASSWORD, "new_password2": AMBLUEO_TEST_NEW_PASSWORD,
            }).status_code, 302)
        self.assertIn("a changé", mail.outbox[1].subject)
        self.assertNotIn(AMBLUEO_TEST_NEW_PASSWORD, mail.outbox[1].body)
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 200)

        self.client.logout()
        self.client.post(reverse("password_reset"), {"email": AMBLUEO_TEST_USER.email})
        AMBLUEO_TEST_LINK = re.search(r"http://testserver/mot-de-passe/[^\s]+", mail.outbox[2].body).group()
        self.assertIn(AMBLUEO_TEST_LINK, mail.outbox[2].alternatives[0].content)
        AMBLUEO_TEST_CONFIRM = self.client.get(AMBLUEO_TEST_LINK).url
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(AMBLUEO_TEST_CONFIRM, {
                "new_password1": AMBLUEO_TEST_PASSWORD, "new_password2": AMBLUEO_TEST_PASSWORD,
            }).status_code, 302)
        self.assertIn("a changé", mail.outbox[3].subject)
        for AMBLUEO_TEST_MESSAGE in mail.outbox:
            AMBLUEO_TEST_HTML = AMBLUEO_TEST_MESSAGE.alternatives[0]
            self.assertEqual(AMBLUEO_TEST_HTML.mimetype, "text/html")
            self.assertIn("http://testserver/static/marque/", AMBLUEO_TEST_HTML.content)

    def test_projects_tasks_and_access(self):
        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        AMBLUEO_TEST_A = self.AMBLUEO_TEST_A.pk
        AMBLUEO_TEST_NEW = reverse("project_new", args=[AMBLUEO_TEST_A])
        AMBLUEO_TEST_DATA = dict(name="Migration", owner=self.AMBLUEO_TEST_OTHER.pk, status="active",
                                start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE)
        self.assertEqual(self.client.post(AMBLUEO_TEST_NEW, AMBLUEO_TEST_DATA).status_code, 200)
        self.assertFalse(Project.objects.filter(name="Migration").exists())
        AMBLUEO_TEST_DATA["owner"] = self.AMBLUEO_TEST_MANAGER.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(AMBLUEO_TEST_NEW, AMBLUEO_TEST_DATA).status_code, 302)
        AMBLUEO_TEST_PROJET = Project.objects.get(name="Migration")
        AMBLUEO_TEST_TACHE_DATA = dict(
            title="Recette", assignee=self.AMBLUEO_TEST_MEMBER.pk, status="todo",
            start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE, estimated=8, actual=0)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(reverse("task_new", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_PROJET.pk]),
                                              AMBLUEO_TEST_TACHE_DATA).status_code, 302)
        AMBLUEO_TEST_TASK = Task.objects.get()
        AMBLUEO_TEST_TACHE_URL = reverse("task_edit", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_PROJET.pk, AMBLUEO_TEST_TASK.pk])
        self.client.force_login(self.AMBLUEO_TEST_MEMBER.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(AMBLUEO_TEST_TACHE_URL,
                dict(status="done", actual=7, title="Interdit")).status_code, 302)
        self.assertEqual([AMBLUEO_TEST_MAIL.to for AMBLUEO_TEST_MAIL in mail.outbox], [
            [self.AMBLUEO_TEST_MANAGER.user.email], [self.AMBLUEO_TEST_MEMBER.user.email],
        ])
        AMBLUEO_TEST_TASK.refresh_from_db()
        self.assertEqual((AMBLUEO_TEST_TASK.title, AMBLUEO_TEST_TASK.status, AMBLUEO_TEST_TASK.actual), ("Recette", "done", 7))
        AMBLUEO_TEST_OTHER_PROJET = self.project(self.AMBLUEO_TEST_OTHER, "Confidentiel")
        self.assertEqual(self.client.get(reverse("project", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_OTHER_PROJET.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("project_edit", args=[self.AMBLUEO_TEST_B.pk,
            AMBLUEO_TEST_OTHER_PROJET.pk]), AMBLUEO_TEST_DATA).status_code, 404)
        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        AMBLUEO_TEST_TACHE_DATA["assignee"] = self.AMBLUEO_TEST_MANAGER.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(AMBLUEO_TEST_TACHE_URL, AMBLUEO_TEST_TACHE_DATA).status_code, 302)
            self.assertEqual(self.client.post(AMBLUEO_TEST_TACHE_URL, AMBLUEO_TEST_TACHE_DATA).status_code, 302)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(mail.outbox[-1].to, [self.AMBLUEO_TEST_MANAGER.user.email])
        self.assertIn("Voir la tâche dans le projet", mail.outbox[-1].alternatives[0].content)
        self.assertIn("Échéance".lower(), mail.outbox[-1].body)

    def test_full_financial_recipe(self):
        AMBLUEO_TEST_PROJET = self.project(self.AMBLUEO_TEST_MANAGER, "Infrastructure")
        AMBLUEO_TEST_A = self.AMBLUEO_TEST_A.pk
        AMBLUEO_TEST_PROJECT_ARGS = [AMBLUEO_TEST_A, AMBLUEO_TEST_PROJET.pk]
        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        self.assertEqual(self.client.post(reverse("budget_edit", args=AMBLUEO_TEST_PROJECT_ARGS), {"amount": "1000000"}).status_code, 302)
        self.assertEqual(self.client.post(reverse("budget_approve", args=AMBLUEO_TEST_PROJECT_ARGS)).status_code, 403)
        self.client.force_login(self.AMBLUEO_TEST_FIN.user)
        self.assertEqual(self.client.post(reverse("budget_approve", args=AMBLUEO_TEST_PROJECT_ARGS)).status_code, 302)
        self.assertEqual(self.client.post(reverse("opening", args=[AMBLUEO_TEST_A]),
            {"amount": 500000, "date": self.AMBLUEO_TEST_DATE}).status_code, 302)
        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        self.assertEqual(self.client.post(reverse("operation_new", args=[*AMBLUEO_TEST_PROJECT_ARGS, "expense"]), dict(
            title="Matériel", category="Équipement", amount=300000, due=self.AMBLUEO_TEST_DATE,
            evidence=SimpleUploadedFile("preuve.pdf", b"%PDF-1.4 recette"))).status_code, 302)
        AMBLUEO_TEST_OPERATION = Operation.objects.get()
        AMBLUEO_TEST_OP_ARGS = [AMBLUEO_TEST_A, AMBLUEO_TEST_OPERATION.pk]
        self.assertEqual(self.client.post(reverse("change_state", args=[*AMBLUEO_TEST_OP_ARGS, "submit"])).status_code, 302)
        self.client.force_login(self.AMBLUEO_TEST_FIN.user)
        self.assertEqual(self.client.post(reverse("change_state", args=[*AMBLUEO_TEST_OP_ARGS, "approve"])).status_code, 302)
        self.assertEqual(self.client.post(reverse("posting_new", args=[*AMBLUEO_TEST_OP_ARGS, "realization"]),
            {"amount": 120000, "date": self.AMBLUEO_TEST_DATE, "key": uuid.uuid4()}).status_code, 302)
        AMBLUEO_TEST_FORM = {"amount": 50000, "date": self.AMBLUEO_TEST_DATE, "key": uuid.uuid4()}
        AMBLUEO_TEST_PATH = reverse("posting_new", args=[*AMBLUEO_TEST_OP_ARGS, "payment"])
        self.assertEqual(self.client.post(AMBLUEO_TEST_PATH, AMBLUEO_TEST_FORM).status_code, 302)
        self.assertEqual(self.client.post(AMBLUEO_TEST_PATH, AMBLUEO_TEST_FORM).status_code, 302)
        self.assertEqual(Posting.objects.filter(kind="payment").count(), 1)
        self.assertEqual(finance.balances(AMBLUEO_TEST_OPERATION), (120000, 50000, 70000))
        AMBLUEO_TEST_ECRAN = self.client.get(reverse("company", args=[AMBLUEO_TEST_A]))
        self.assertEqual(AMBLUEO_TEST_ECRAN.context["cash"]["current"], 450000)
        self.assertEqual(AMBLUEO_TEST_ECRAN.context["cash"]["forecast"], 200000)
        self.assertContains(self.client.get(reverse("project", args=AMBLUEO_TEST_PROJECT_ARGS)), "Infrastructure")
        AMBLUEO_TEST_EXPORT = self.client.get(reverse("export", args=[AMBLUEO_TEST_A]), {"download": 1})
        AMBLUEO_TEST_LIGNES = list(csv.DictReader(io.StringIO(AMBLUEO_TEST_EXPORT.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(Decimal(AMBLUEO_TEST_LIGNES[0]["Réalisé"]), 120000)
        self.assertEqual(Decimal(AMBLUEO_TEST_LIGNES[0]["Engagé ouvert"]), 180000)
        self.assertEqual(Decimal(AMBLUEO_TEST_LIGNES[0]["Disponible"]), 700000)
        self.assertEqual(Decimal(AMBLUEO_TEST_LIGNES[1]["Restant exigible"]), 70000)
        AMBLUEO_TEST_DOCUMENT = self.client.get(reverse("attachment", args=AMBLUEO_TEST_OP_ARGS))
        self.assertEqual(b"".join(AMBLUEO_TEST_DOCUMENT.streaming_content), b"%PDF-1.4 recette")
        self.client.force_login(self.AMBLUEO_TEST_OTHER.user)
        self.assertEqual(self.client.get(reverse("attachment", args=AMBLUEO_TEST_OP_ARGS)).status_code, 404)
        self.assertEqual(self.client.get(reverse("export", args=[AMBLUEO_TEST_A]), {"download": 1}).status_code, 404)
        self.client.force_login(self.AMBLUEO_TEST_FIN.user)
        AMBLUEO_TEST_REGLEMENT = Posting.objects.get(kind="payment")
        self.assertEqual(self.client.post(reverse("posting_void", args=[*AMBLUEO_TEST_OP_ARGS, AMBLUEO_TEST_REGLEMENT.pk]),
            {"reason": "Saisie en doublon constatée"}).status_code, 302)
        self.assertTrue(Audit.objects.filter(reason="Saisie en doublon constatée").exists())
        self.assertEqual(finance.cash_summary(self.AMBLUEO_TEST_A)["current"], 500000)


    def test_company_priorities_and_setup_respect_roles(self):
        AMBLUEO_TEST_COMPANY_ARGS = [self.AMBLUEO_TEST_A.pk]
        AMBLUEO_TEST_URL = reverse("company", args=AMBLUEO_TEST_COMPANY_ARGS)
        self.client.force_login(self.AMBLUEO_TEST_OWNER.user)
        self.assertContains(self.client.get(AMBLUEO_TEST_URL), reverse("project_new", args=AMBLUEO_TEST_COMPANY_ARGS))
        AMBLUEO_TEST_PROJET = self.project(self.AMBLUEO_TEST_MANAGER, "Pilotage")
        AMBLUEO_TEST_PRIVE = self.project(self.AMBLUEO_TEST_OTHER, "Projet privé")
        AMBLUEO_TEST_HIER = timezone.localdate() - timedelta(days=1)
        for AMBLUEO_TEST_PROJET_CIBLE in (AMBLUEO_TEST_PROJET, AMBLUEO_TEST_PRIVE):
            Operation.objects.create(
                project=AMBLUEO_TEST_PROJET_CIBLE, author=AMBLUEO_TEST_PROJET_CIBLE.owner, kind="expense",
                state="submitted", amount=100, title=f"Dépense {AMBLUEO_TEST_PROJET_CIBLE.name}", due=AMBLUEO_TEST_HIER,
            )
        Operation.objects.create(
            project=AMBLUEO_TEST_PROJET, author=self.AMBLUEO_TEST_FIN, kind="income",
            state="approved", amount=40, title="Recette en retard", due=AMBLUEO_TEST_HIER,
        )
        AMBLUEO_TEST_TACHE = Task.objects.create(
            project=AMBLUEO_TEST_PROJET, assignee=self.AMBLUEO_TEST_MEMBER,
            title="Tâche échue", start=AMBLUEO_TEST_HIER, end=AMBLUEO_TEST_HIER, estimated=1,
        )
        AMBLUEO_TEST_ECRAN = self.client.get(AMBLUEO_TEST_URL)
        self.assertContains(AMBLUEO_TEST_ECRAN, "Dépense Pilotage")
        self.assertContains(AMBLUEO_TEST_ECRAN, "Recette en retard")
        self.assertContains(AMBLUEO_TEST_ECRAN, "Risque de dépassement")
        self.assertNotContains(AMBLUEO_TEST_ECRAN, "Projet privé")
        self.assertTrue(AMBLUEO_TEST_ECRAN.context["setup"]["project"])
        Budget.objects.create(project=AMBLUEO_TEST_PROJET, amount=200, approved=True)
        self.client.post(reverse("opening", args=AMBLUEO_TEST_COMPANY_ARGS), {"amount": 0, "date": self.AMBLUEO_TEST_DATE})
        self.assertNotContains(self.client.get(AMBLUEO_TEST_URL), "Premiers pas")

        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        AMBLUEO_TEST_ECRAN = self.client.get(AMBLUEO_TEST_URL)
        self.assertNotContains(AMBLUEO_TEST_ECRAN, "Dépense Pilotage")
        self.assertContains(AMBLUEO_TEST_ECRAN, "Recette en retard")

        self.client.force_login(self.AMBLUEO_TEST_MEMBER.user)
        AMBLUEO_TEST_ECRAN = self.client.get(AMBLUEO_TEST_URL)
        self.assertNotContains(AMBLUEO_TEST_ECRAN, "Recette en retard")
        self.assertNotContains(AMBLUEO_TEST_ECRAN, "Projets à risque")
        self.assertContains(AMBLUEO_TEST_ECRAN, reverse("task_edit", args=[
            *AMBLUEO_TEST_COMPANY_ARGS, AMBLUEO_TEST_PROJET.pk, AMBLUEO_TEST_TACHE.pk,
        ]))

    def test_export_preview_matches_download_and_rejects_invalid_filters(self):
        AMBLUEO_TEST_PROJET = self.project(self.AMBLUEO_TEST_MANAGER, "Export")
        AMBLUEO_TEST_AUTRE = self.project(self.AMBLUEO_TEST_OTHER, "Export privé")
        Budget.objects.create(project=AMBLUEO_TEST_PROJET, approved=True, amount=400)
        for AMBLUEO_TEST_KIND, AMBLUEO_TEST_AMOUNT, AMBLUEO_TEST_DUE in [
            ("expense", 150, self.AMBLUEO_TEST_DATE),
            ("income", 50, self.AMBLUEO_TEST_DATE),
            ("expense", 80, timezone.localdate() - timedelta(days=1)),
        ]:
            Operation.objects.create(
                project=AMBLUEO_TEST_PROJET, author=self.AMBLUEO_TEST_MANAGER,
                kind=AMBLUEO_TEST_KIND, amount=AMBLUEO_TEST_AMOUNT, due=AMBLUEO_TEST_DUE, title="Opération",
            )
        AMBLUEO_TEST_URL = reverse("export", args=[self.AMBLUEO_TEST_A.pk])
        self.client.force_login(self.AMBLUEO_TEST_FIN.user)
        AMBLUEO_TEST_FILTRES = dict(project=AMBLUEO_TEST_PROJET.pk, start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE)
        AMBLUEO_TEST_APERCU = self.client.get(AMBLUEO_TEST_URL, AMBLUEO_TEST_FILTRES)
        self.assertDictEqual(AMBLUEO_TEST_APERCU.context["preview"], dict(
            count=2, expenses=Decimal(150), income=Decimal(50), approved_budget=Decimal(400),
        ))
        self.assertContains(AMBLUEO_TEST_APERCU, "Aperçu du CSV")
        AMBLUEO_TEST_CSV = self.client.get(AMBLUEO_TEST_URL, {**AMBLUEO_TEST_FILTRES, "download": 1})
        AMBLUEO_TEST_LIGNES = list(csv.DictReader(io.StringIO(AMBLUEO_TEST_CSV.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([Decimal(AMBLUEO_TEST_LIGNE["Montant"]) for AMBLUEO_TEST_LIGNE in AMBLUEO_TEST_LIGNES],
                         [Decimal(400), Decimal(150), Decimal(50)])
        self.assertNotContains(self.client.get(AMBLUEO_TEST_URL, {"project": AMBLUEO_TEST_AUTRE.pk}), "Aperçu du CSV")
        self.assertContains(self.client.get(AMBLUEO_TEST_URL, dict(start=self.AMBLUEO_TEST_DATE, end="2000-01-01")),
                            "La date de fin doit suivre la date de début.")
        self.client.force_login(self.AMBLUEO_TEST_MEMBER.user)
        self.assertEqual(self.client.get(AMBLUEO_TEST_URL).status_code, 403)


@skipUnless(connection.vendor == "postgresql", "Verrous PostgreSQL requis")
class ConcurrentPostingTest(TransactionTestCase):
    def test_concurrent_payments_never_exceed_remaining_amount(self):
        AMBLUEO_TEST_DATE = timezone.localdate()
        AMBLUEO_TEST_COMPANY = Company.objects.create(name="Concurrency", currency="EUR")
        AMBLUEO_TEST_MEMBER = Membership.objects.create(company=AMBLUEO_TEST_COMPANY, role=Role.FINANCE,
            user=User.objects.create_user("finance", "finance@example.test"))
        AMBLUEO_TEST_PROJECT = Project.objects.create(company=AMBLUEO_TEST_COMPANY, name="Essai",
            owner=AMBLUEO_TEST_MEMBER, start=AMBLUEO_TEST_DATE, end=AMBLUEO_TEST_DATE)
        AMBLUEO_TEST_OP = Operation.objects.create(project=AMBLUEO_TEST_PROJECT, kind="income", state="approved",
            amount=100, due=AMBLUEO_TEST_DATE, title="Recette", category="Service", author=AMBLUEO_TEST_MEMBER)
        AMBLUEO_TEST_BARRIERE = Barrier(2)

        def pay():
            close_old_connections()
            try:
                AMBLUEO_TEST_BARRIERE.wait(timeout=5)
                finance.post(AMBLUEO_TEST_MEMBER, AMBLUEO_TEST_OP.pk, "payment", Decimal(75), AMBLUEO_TEST_DATE, uuid.uuid4())
                return True
            except ValidationError:
                return False
            finally:
                connection.close()

        with ThreadPoolExecutor(2) as AMBLUEO_TEST_EXECUTEUR:
            AMBLUEO_TEST_PREMIER = AMBLUEO_TEST_EXECUTEUR.submit(pay)
            AMBLUEO_TEST_SECOND = AMBLUEO_TEST_EXECUTEUR.submit(pay)
            self.assertEqual(sorted([AMBLUEO_TEST_PREMIER.result(), AMBLUEO_TEST_SECOND.result()]), [False, True])
        self.assertEqual(finance.balances(AMBLUEO_TEST_OP), (0, 75, 25))
