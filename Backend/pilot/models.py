import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
from django.core.validators import MinValueValidator
from django.db import models

AMBLUEO_FINANCE_POSITIF = [MinValueValidator(Decimal("0.01"))]


class User(AbstractUser):
    """Compte pilote avec une seule identité par adresse de récupération."""

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), condition=~models.Q(email=""), name="user_email_unique")]


class Company(models.Model):
    name = models.CharField("Nom", max_length=120)
    currency = models.CharField("Devise", max_length=3, choices=[("XOF", "FCFA (XOF)"), ("EUR", "Euro")])

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    OWNER = "owner", "Dirigeant"
    MANAGER = "manager", "Chef de projet"
    FINANCE = "finance", "Financier"
    MEMBER = "member", "Collaborateur"


class Membership(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField("Rôle", max_length=12, choices=Role.choices)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "user"], name="unique_membership")]

    def __str__(self):
        return self.user.get_username()


class Invitation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    email = models.EmailField("Courriel")
    role = models.CharField("Rôle", max_length=12, choices=Role.choices)
    digest = models.CharField(max_length=64, unique=True)
    expires = models.DateTimeField()
    used = models.BooleanField(default=False)


class Project(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField("Nom du projet", max_length=150)
    owner = models.ForeignKey(Membership, on_delete=models.PROTECT, verbose_name="Responsable")
    status = models.CharField("Statut", max_length=12, choices=[
        ("planned", "Planifié"), ("active", "En cours"), ("closed", "Terminé"),
    ], default="planned")
    start = models.DateField("Début")
    end = models.DateField("Fin")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(end__gte=models.F("start")), name="project_dates")]

    def __str__(self):
        return self.name


class Task(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    title = models.CharField("Intitulé", max_length=150)
    assignee = models.ForeignKey(Membership, on_delete=models.PROTECT, verbose_name="Affectation")
    status = models.CharField("Statut", max_length=12, choices=[
        ("todo", "À faire"), ("doing", "En cours"), ("done", "Terminée"),
    ], default="todo")
    start = models.DateField("Début")
    end = models.DateField("Échéance")
    estimated = models.DecimalField("Charge estimée (h)", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    actual = models.DecimalField("Charge réelle (h)", max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end__gte=models.F("start")), name="task_dates"),
            models.CheckConstraint(condition=models.Q(estimated__gte=0, actual__gte=0), name="task_hours"),
        ]


class Budget(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    amount = models.DecimalField("Budget", max_digits=16, decimal_places=2, validators=AMBLUEO_FINANCE_POSITIF)
    approved = models.BooleanField(default=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="budget_positive")]


def attachment_path(AMBLUEO_FINANCE_OPERATION, AMBLUEO_FINANCE_NOM_ORIGINE):
    """Crée un nom opaque indépendant du nom d'origine."""
    return f"{AMBLUEO_FINANCE_OPERATION.project.company_id}/{uuid.uuid4().hex}"


class Operation(models.Model):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Dépense"
        INCOME = "income", "Recette"

    class State(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SUBMITTED = "submitted", "Soumise"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Rejetée"
        CANCELLED = "cancelled", "Annulée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    title = models.CharField("Libellé", max_length=150)
    category = models.CharField("Catégorie", max_length=80)
    amount = models.DecimalField("Montant", max_digits=16, decimal_places=2, validators=AMBLUEO_FINANCE_POSITIF)
    due = models.DateField("Échéance")
    created_on = models.DateField(auto_now_add=True)
    evidence = models.FileField("Justificatif (PDF, PNG, JPEG)", blank=True, upload_to=attachment_path)
    author = models.ForeignKey(Membership, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="operation_positive")]


class Posting(models.Model):
    class Kind(models.TextChoices):
        REALIZATION = "realization", "Réalisation"
        PAYMENT = "payment", "Règlement"

    operation = models.ForeignKey(Operation, related_name="postings", on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField("Montant", max_digits=16, decimal_places=2, validators=AMBLUEO_FINANCE_POSITIF)
    date = models.DateField("Date")
    key = models.UUIDField(unique=True)
    void = models.BooleanField(default=False)
    author = models.ForeignKey(Membership, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="posting_positive")]


class CashOpening(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    amount = models.DecimalField("Solde d’ouverture", max_digits=16, decimal_places=2)
    date = models.DateField("Date de référence")


class Audit(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=40)
    target = models.CharField(max_length=80)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
