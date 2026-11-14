"""IndexNow : prévient Bing (et les moteurs qui partagent IndexNow : Yandex, Seznam, Naver…, et les recherches IA qui
s'appuient sur Bing) dès qu'une page change, au lieu d'attendre leur prochain passage. Gratuit, sans compte.
La clé est publique par conception : le fichier public/9e8733e28b100e322923a0f34b463207.txt prouve que le site en est propriétaire."""
import json
import urllib.request

from core.helpers import chart_path, url

CLE = "9e8733e28b100e322923a0f34b463207"


def soumettre(urls: list) -> str:
    """Envoie jusqu'à 10 000 adresses du site. Ne lève jamais : renvoie un compte rendu court."""
    urls = [u for u in dict.fromkeys(urls) if u][:10000]
    if not urls:
        return "rien à envoyer"
    hote = url("/").split("/")[2]
    corps = {"host": hote, "key": CLE, "keyLocation": url(CLE + ".txt"), "urlList": urls}
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"{len(urls)} adresse(s) envoyée(s) (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return f"refusé (HTTP {e.code})"
    except Exception as e:  # noqa: BLE001
        return f"échec : {e}"


def classements_de_la_semaine() -> list:
    """Accueil, Top Afrique de l'Ouest et Top de chaque pays : les pages qui changent à chaque publication."""
    from core import repos
    out = [url("/"), url("classements/afrique-de-l-ouest"), url("sitemap.xml")]
    for c in repos.countries():
        out.append(url(chart_path(c["code"], "prime", "week")))
    return out
