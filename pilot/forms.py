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
        fields = ["title", "category", "amount", "due", "evidence"]

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
    project = forms.ModelChoiceField(label="Projet", queryset=Project.objects.none(), required=False)
