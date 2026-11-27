from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import FileExtensionValidator

from .models import Budget, CashOpening, Company, Invitation, Operation, Project, Task, User


class InviteAccountForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "currency"]


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["email", "role"]


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "owner", "status", "start", "end"]


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "assignee", "status", "start", "end", "estimated", "actual"]


class ProgressForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["status", "actual"]


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["amount"]


class OpeningForm(forms.ModelForm):
    class Meta:
        model = CashOpening
        fields = ["amount", "date"]


class OperationForm(forms.ModelForm):
    class Meta:
        model = Operation
        fields = ["title", "category", "counterparty", "external_reference", "amount", "due", "evidence"]

    def clean_evidence(self):
        AMBLUEO_FINANCE_DOCUMENT = self.cleaned_data["evidence"]
        if AMBLUEO_FINANCE_DOCUMENT:
            FileExtensionValidator(["pdf", "png", "jpg", "jpeg"])(AMBLUEO_FINANCE_DOCUMENT)
            if AMBLUEO_FINANCE_DOCUMENT.size > 8 * 1024 * 1024:
                raise forms.ValidationError("Le justificatif doit peser au maximum 8 Mio.")
        return AMBLUEO_FINANCE_DOCUMENT


class PostingForm(forms.Form):
    amount = forms.DecimalField(label="Montant", max_digits=16, decimal_places=2)
    date = forms.DateField(label="Date")
    key = forms.UUIDField(widget=forms.HiddenInput)


class ReasonForm(forms.Form):
    reason = forms.CharField(label="Motif", max_length=500, widget=forms.Textarea(attrs={"rows": 3}))


class ExportForm(forms.Form):
    start = forms.DateField(label="Du", required=False)
    end = forms.DateField(label="Au", required=False)
    project = forms.ModelChoiceField(
        label="Projet", queryset=Project.objects.none(), required=False, empty_label="Tous les projets",
    )

    def clean(self):
        AMBLUEO_EXPORT_DONNEES = super().clean()
        AMBLUEO_EXPORT_DEBUT = AMBLUEO_EXPORT_DONNEES.get("start")
        AMBLUEO_EXPORT_FIN = AMBLUEO_EXPORT_DONNEES.get("end")
        if AMBLUEO_EXPORT_DEBUT and AMBLUEO_EXPORT_FIN and AMBLUEO_EXPORT_DEBUT > AMBLUEO_EXPORT_FIN:
            self.add_error("end", "La date de fin doit suivre la date de début.")
        return AMBLUEO_EXPORT_DONNEES


class OperationReferenceForm(forms.ModelForm):
    class Meta:
        model = Operation
        fields = ["counterparty", "external_reference"]


class ScheduleForm(ExportForm):
    kind = forms.ChoiceField(label="Type", choices=[("", "Tous les types"), *Operation.Kind.choices], required=False)
    counterparty = forms.CharField(label="Client ou fournisseur", max_length=150, required=False)


class InitialImportForm(forms.Form):
    file = forms.FileField(label="Fichier CSV", widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))

    def clean_file(self):
        AMBLUEO_IMPORT_FICHIER = self.cleaned_data["file"]
        if AMBLUEO_IMPORT_FICHIER.size > 256 * 1024:
            raise forms.ValidationError("Le fichier doit peser au maximum 256 Kio.")
        return AMBLUEO_IMPORT_FICHIER
