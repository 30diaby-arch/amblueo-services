from django.db import connection
from django.http import HttpResponse


def health(AMBLUEO_INFRA_REQUETE):
    with connection.cursor() as AMBLUEO_INFRA_CURSEUR:
        AMBLUEO_INFRA_CURSEUR.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
