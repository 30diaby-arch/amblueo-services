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
    AMBLUEO_TEST_PAGE.get_by_role("region", name="Projets").get_by_role(
        "link", name="Refonte du site client",
    ).click()
    expect(AMBLUEO_TEST_PAGE.get_by_text("Valider les maquettes", exact=True)).to_be_visible()
    AMBLUEO_TEST_PAGE.get_by_role("link", name="Mot de passe", exact=True).click()
    expect(AMBLUEO_TEST_PAGE.get_by_role("heading", name="Changer le mot de passe")).to_be_visible()


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
