import csv
import io
import re
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
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
        AMBLUEO_TEST_INVITATION = self.client.post(reverse("invite", args=[self.AMBLUEO_TEST_A.pk]),
                                                  {"email": "invite@example.test", "role": "member"})
        AMBLUEO_TEST_URL = re.search(r'/invitation/[^/"]+/', AMBLUEO_TEST_INVITATION.content.decode()).group()
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
        self.assertIn("/mot-de-passe/", mail.outbox[0].body)

    def test_projects_tasks_and_access(self):
        self.client.force_login(self.AMBLUEO_TEST_MANAGER.user)
        AMBLUEO_TEST_A = self.AMBLUEO_TEST_A.pk
        AMBLUEO_TEST_NEW = reverse("project_new", args=[AMBLUEO_TEST_A])
        AMBLUEO_TEST_DATA = dict(name="Migration", owner=self.AMBLUEO_TEST_OTHER.pk, status="active",
                                start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE)
        self.assertEqual(self.client.post(AMBLUEO_TEST_NEW, AMBLUEO_TEST_DATA).status_code, 200)
        self.assertFalse(Project.objects.filter(name="Migration").exists())
        AMBLUEO_TEST_DATA["owner"] = self.AMBLUEO_TEST_MANAGER.pk
        self.assertEqual(self.client.post(AMBLUEO_TEST_NEW, AMBLUEO_TEST_DATA).status_code, 302)
        AMBLUEO_TEST_PROJET = Project.objects.get(name="Migration")
        self.assertEqual(self.client.post(reverse("task_new", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_PROJET.pk]), dict(
            title="Recette", assignee=self.AMBLUEO_TEST_MEMBER.pk, status="todo",
            start=self.AMBLUEO_TEST_DATE, end=self.AMBLUEO_TEST_DATE, estimated=8, actual=0)).status_code, 302)
        AMBLUEO_TEST_TASK = Task.objects.get()
        self.client.force_login(self.AMBLUEO_TEST_MEMBER.user)
        self.assertEqual(self.client.post(reverse("task_edit", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_PROJET.pk,
            AMBLUEO_TEST_TASK.pk]), dict(status="done", actual=7, title="Interdit")).status_code, 302)
        AMBLUEO_TEST_TASK.refresh_from_db()
        self.assertEqual((AMBLUEO_TEST_TASK.title, AMBLUEO_TEST_TASK.status, AMBLUEO_TEST_TASK.actual), ("Recette", "done", 7))
        AMBLUEO_TEST_OTHER_PROJET = self.project(self.AMBLUEO_TEST_OTHER, "Confidentiel")
        self.assertEqual(self.client.get(reverse("project", args=[AMBLUEO_TEST_A, AMBLUEO_TEST_OTHER_PROJET.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("project_edit", args=[self.AMBLUEO_TEST_B.pk,
            AMBLUEO_TEST_OTHER_PROJET.pk]), AMBLUEO_TEST_DATA).status_code, 404)

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
