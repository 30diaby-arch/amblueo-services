import csv
import io
import sys
from pathlib import Path
from tempfile import mkdtemp

from playwright.sync_api import expect, sync_playwright


def verifier_affichage(AMBLUEO_TEST_PAGE, AMBLUEO_TEST_URL):
    AMBLUEO_TEST_PAGE.goto(f"{AMBLUEO_TEST_URL}/connexion/")
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Connexion")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.locator(".brand img")).to_have_js_property("complete", True)
    expect(AMBLUEO_TEST_PAGE.locator(".brand img")).not_to_have_js_property("naturalWidth", 0)
    expect(AMBLUEO_TEST_PAGE.locator("body")).to_have_css("background-color", "rgb(246, 245, 251)")
    AMBLUEO_TEST_PAGE.locator('input[name="username"]').fill("demo_dirigeant")
    AMBLUEO_TEST_PAGE.locator('input[name="password"]').fill("Amblueo-demo-local-42!")
    AMBLUEO_TEST_PAGE.get_by_role("button", name="Se connecter").click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Mes entreprises")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Atelier Horizon").click()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Tableau de bord", exact=True).click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Tableau de bord")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Avancement des projets")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_label("Période des flux").select_option("1")
    AMBLUEO_TEST_PAGE.get_by_role("button", name="Appliquer").click()
    expect(AMBLUEO_TEST_PAGE.get_by_label("Période des flux")).to_have_value("1")
    expect(AMBLUEO_TEST_PAGE.locator("#dashboard-budget-chart canvas")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.locator("#dashboard-echeances-chart canvas")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="À encaisser, En retard", exact=False).click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Échéancier clients et fournisseurs")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.get_by_role("link", name="Acompte client attendu", exact=True)).to_be_visible()
    if AMBLUEO_TEST_PAGE.viewport_size["width"] == 1280:
        AMBLUEO_TEST_DASHBOARD = AMBLUEO_TEST_PAGE.get_by_role("navigation", name="Fil d’Ariane").get_by_role(
            "link", name="Atelier Horizon",
        ).get_attribute("href")
        AMBLUEO_TEST_PAGE.get_by_role("link", name="Acompte client attendu", exact=True).click()
        AMBLUEO_TEST_PAGE.get_by_role("link", name="Enregistrer un règlement").click()
        AMBLUEO_TEST_PAGE.get_by_label("Montant").fill("100")
        AMBLUEO_TEST_PAGE.get_by_role("button", name="Enregistrer").click()
        AMBLUEO_TEST_PAGE.goto(f"{AMBLUEO_TEST_URL}{AMBLUEO_TEST_DASHBOARD}")
        AMBLUEO_TEST_PAGE.get_by_role("link", name="Tableau de bord", exact=True).click()
    else:
        AMBLUEO_TEST_PAGE.go_back()
    expect(AMBLUEO_TEST_PAGE.locator("#dashboard-flux-chart canvas")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.locator("#dashboard-flux-chart")).to_have_css("height", "256px")
    expect(AMBLUEO_TEST_PAGE.locator(".dashboard-kpis")).to_have_css("display", "grid")
    AMBLUEO_TEST_PAGE.get_by_text("Voir les montants par période").click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("region", name="Montants des flux")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("navigation", name="Fil d’Ariane").get_by_role(
        "link", name="Atelier Horizon",
    ).click()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Échéancier", exact=True).click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Échéancier clients et fournisseurs")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("navigation", name="Fil d’Ariane").get_by_role(
        "link", name="Atelier Horizon",
    ).click()
    if AMBLUEO_TEST_PAGE.viewport_size["width"] == 1280:
        verifier_import(AMBLUEO_TEST_PAGE)
    AMBLUEO_TEST_PAGE.get_by_role("region", name="Projets").get_by_role(
        "link", name="Refonte du site client",
    ).click()
    expect(AMBLUEO_TEST_PAGE.get_by_text("Valider les maquettes", exact=True)).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Mot de passe", exact=True).click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Changer le mot de passe")).to_be_visible()


def verifier_import(AMBLUEO_TEST_PAGE):
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Importer des données").click()
    with AMBLUEO_TEST_PAGE.expect_download() as AMBLUEO_TEST_TELECHARGEMENT:
        AMBLUEO_TEST_PAGE.get_by_role("link", name="Télécharger le modèle CSV").click()
    AMBLUEO_TEST_ENTETE = AMBLUEO_TEST_TELECHARGEMENT.value.path().read_text(encoding="utf-8-sig").strip()
    AMBLUEO_TEST_CSV = io.StringIO()
    AMBLUEO_TEST_REDAC = csv.DictWriter(AMBLUEO_TEST_CSV, fieldnames=AMBLUEO_TEST_ENTETE.split(";"), delimiter=";")
    AMBLUEO_TEST_REDAC.writeheader()
    AMBLUEO_TEST_REDAC.writerow({
        "type": "recette", "identifiant": "RECETTE-NAV-001", "projet": "Refonte du site client",
        "montant": "45000", "libelle": "Facture navigateur", "categorie": "Services",
        "tiers": "Client navigateur", "reference": "FAC-NAV-001", "echeance": "2027-01-15",
    })
    AMBLUEO_TEST_PAGE.get_by_label("Fichier CSV").set_input_files({
        "name": "reprise.csv", "mimeType": "text/csv", "buffer": AMBLUEO_TEST_CSV.getvalue().encode(),
    })
    AMBLUEO_TEST_PAGE.get_by_role("button", name="Prévisualiser le fichier").click()
    expect(AMBLUEO_TEST_PAGE.get_by_text("Prête à importer")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("button", name="Confirmer l’import").click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("status")).to_contain_text("1 ligne importée")
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Ouvrir l’échéancier").click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("link", name="Facture navigateur")).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("navigation", name="Fil d’Ariane").get_by_role(
        "link", name="Atelier Horizon",
    ).click()


def verifier_courriel(AMBLUEO_TEST_PAGE, AMBLUEO_TEST_HTML, AMBLUEO_TEST_URL):
    AMBLUEO_TEST_PAGE.set_content(AMBLUEO_TEST_HTML)
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Une tâche vous a été attribuée")).to_be_visible()
    expect(AMBLUEO_TEST_PAGE.locator("img")).not_to_have_js_property("naturalWidth", 0)
    expect(AMBLUEO_TEST_PAGE.get_by_role("link", name="Voir la tâche dans le projet")).to_have_attribute(
        "href", AMBLUEO_TEST_URL,
    )


if __name__ == "__main__":
    AMBLUEO_TEST_HTML = sys.stdin.read()
    with sync_playwright() as AMBLUEO_TEST_PLAYWRIGHT:
        AMBLUEO_TEST_NAVIGATEUR = AMBLUEO_TEST_PLAYWRIGHT.chromium.launch()
        for AMBLUEO_TEST_LARGEUR in (1280, 390):
            AMBLUEO_TEST_PAGE = AMBLUEO_TEST_NAVIGATEUR.new_page(
                viewport={"width": AMBLUEO_TEST_LARGEUR, "height": 850},
            )
            try:
                verifier_affichage(AMBLUEO_TEST_PAGE, sys.argv[1])
                verifier_courriel(AMBLUEO_TEST_PAGE, AMBLUEO_TEST_HTML, sys.argv[1])
            except Exception:
                AMBLUEO_TEST_CAPTURE = Path(mkdtemp(prefix="amblueo-affichage-")) / "echec.png"
                AMBLUEO_TEST_PAGE.screenshot(path=AMBLUEO_TEST_CAPTURE, full_page=True)
                print(f"Capture du test en échec : {AMBLUEO_TEST_CAPTURE}", file=sys.stderr)
                raise
            finally:
                AMBLUEO_TEST_PAGE.close()
