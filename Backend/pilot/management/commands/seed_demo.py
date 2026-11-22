from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from pilot.models import Budget, Company, Membership, Operation, Project, Role, Task, User


class Command(BaseCommand):
    help = "Crée deux entreprises fictives et cinq comptes pour la recette locale."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("La démonstration est réservée à l'environnement local.")
        if User.objects.filter(username="demo_dirigeant").exists():
            self.stdout.write("Démonstration déjà installée.")
            return
        AMBLUEO_DEMO_MOT_DE_PASSE = "Amblueo-demo-local-42!"
        AMBLUEO_DEMO_COMPAGNIE = Company.objects.create(name="Atelier Horizon", currency="XOF")
        AMBLUEO_DEMO_AUTRE = Company.objects.create(name="Studio Latitude", currency="EUR")
        for AMBLUEO_DEMO_NOM, AMBLUEO_DEMO_ROLE, AMBLUEO_DEMO_CIBLE in [
            ("demo_dirigeant", Role.OWNER, AMBLUEO_DEMO_COMPAGNIE),
            ("demo_projet", Role.MANAGER, AMBLUEO_DEMO_COMPAGNIE),
            ("demo_finance", Role.FINANCE, AMBLUEO_DEMO_COMPAGNIE),
            ("demo_collab", Role.MEMBER, AMBLUEO_DEMO_COMPAGNIE),
            ("demo_second", Role.OWNER, AMBLUEO_DEMO_AUTRE),
        ]:
            AMBLUEO_DEMO_COMPTE = User.objects.create_user(AMBLUEO_DEMO_NOM, f"{AMBLUEO_DEMO_NOM}@example.test",
                                                          AMBLUEO_DEMO_MOT_DE_PASSE)
            Membership.objects.create(company=AMBLUEO_DEMO_CIBLE, user=AMBLUEO_DEMO_COMPTE, role=AMBLUEO_DEMO_ROLE)
        AMBLUEO_DEMO_DATE = timezone.localdate()
        AMBLUEO_DEMO_PROJET = Project.objects.create(company=AMBLUEO_DEMO_COMPAGNIE, name="Refonte du site client",
            owner=Membership.objects.get(company=AMBLUEO_DEMO_COMPAGNIE, role=Role.MANAGER),
            status="active", start=AMBLUEO_DEMO_DATE - timedelta(days=5), end=AMBLUEO_DEMO_DATE + timedelta(days=15))
        Task.objects.create(project=AMBLUEO_DEMO_PROJET, title="Valider les maquettes",
            assignee=Membership.objects.get(company=AMBLUEO_DEMO_COMPAGNIE, role=Role.MEMBER),
            start=AMBLUEO_DEMO_DATE - timedelta(days=3), end=AMBLUEO_DEMO_DATE - timedelta(days=1), estimated=8)
        Budget.objects.create(project=AMBLUEO_DEMO_PROJET, amount=200000, approved=True)
        Operation.objects.create(
            project=AMBLUEO_DEMO_PROJET, author=AMBLUEO_DEMO_PROJET.owner,
            title="Prestation d’intégration", category="Sous-traitance", amount=230000,
            kind=Operation.Kind.EXPENSE, state=Operation.State.SUBMITTED,
            due=AMBLUEO_DEMO_DATE + timedelta(days=3),
        )
        Operation.objects.create(
            project=AMBLUEO_DEMO_PROJET, author=Membership.objects.get(company=AMBLUEO_DEMO_COMPAGNIE, role=Role.FINANCE),
            title="Acompte client attendu", category="Prestation", amount=125000,
            kind=Operation.Kind.INCOME, state=Operation.State.APPROVED,
            due=AMBLUEO_DEMO_DATE - timedelta(days=2),
        )
        Project.objects.create(company=AMBLUEO_DEMO_AUTRE, name="Identité visuelle",
            owner=Membership.objects.get(company=AMBLUEO_DEMO_AUTRE, role=Role.OWNER),
            start=AMBLUEO_DEMO_DATE, end=AMBLUEO_DEMO_DATE + timedelta(days=10))
        self.stdout.write("Démonstration créée. Les identifiants figurent dans le README.")
