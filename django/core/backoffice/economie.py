"""Page « Économie » de l'admin (23/11/2026, demande du fondateur) : dépenses, transactions, factures et reçus,
échéances, dépense des IA payantes, partenaires, rapports hebdomadaires. Une « vue partenaire » (?vue=partenaire)
garde la synthèse et masque le détail des transactions, pour la montrer à un partenaire ou un investisseur.

Sources : config/couts.json (chaque dépense et son justificatif), config/recettes.json (recettes, vide tant qu'aucune
n'est déclarée), api_quota (coût estimé des IA, par jour), partenaires_acces / partenaires_editions, et les rapports
hebdomadaires archivés dans le Blob (rapports/hebdo/).
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from core import db, env
from core.backoffice.views import admin_render, admin_view

ROOT = Path(__file__).resolve().parents[3]
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
JUSTIFIE = re.compile(r"facture|reçu|recu|relevé|releve|e-mails?", re.I)


def _json(nom: str) -> list:
    try:
        return json.loads((ROOT / "config" / nom).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _taux() -> float:
    """Dollars pour un euro (réglable : EUR_USD) ; les montants convertis sont marqués « ≈ »."""
    try:
        return float(env.get("EUR_USD", "") or 1.08)
    except ValueError:
        return 1.08


def en_usd(montant, devise) -> float:
    try:
        m = float(montant or 0)
    except (TypeError, ValueError):
        return 0.0
    return m * _taux() if (devise or "").upper() == "EUR" else m


def _mensuel(c: dict) -> bool:
    return "mensuel" in str(c.get("periodicite") or "").lower()


def _date_fr(iso) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return ""
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def donnees(aujourdhui: date | None = None) -> dict:
    auj = aujourdhui or date.today()
    couts, recettes = _json("couts.json"), _json("recettes.json")
    mois = auj.strftime("%Y-%m")
    transactions = []
    for c in couts:
        transactions.append({**c, "usd": en_usd(c.get("montant"), c.get("devise")),
                             "justifie": bool(JUSTIFIE.search(str(c.get("source") or ""))) and "aucun" not in str(c.get("source") or "").lower(),
                             "date_fr": _date_fr(c.get("date_depense")), "echeance_fr": _date_fr(c.get("prochaine_echeance"))})
    transactions.sort(key=lambda x: str(x.get("date_depense") or ""), reverse=True)
    recurrent = sum(t["usd"] for t in transactions if _mensuel(t) and "fondateur" not in str(t.get("categorie") or ""))
    recurrent_fondateur = sum(t["usd"] for t in transactions if _mensuel(t) and "fondateur" in str(t.get("categorie") or ""))
    ce_mois = sum(t["usd"] for t in transactions if str(t.get("date_depense") or "").startswith(mois))
    recettes_mois = sum(en_usd(r.get("montant"), r.get("devise")) for r in recettes if str(r.get("date") or "").startswith(mois))
    recettes_total = sum(en_usd(r.get("montant"), r.get("devise")) for r in recettes)
    justificatifs = sum(1 for t in transactions if t["justifie"])
    a_confirmer = sum(1 for t in transactions if t.get("a_confirmer") or t.get("montant") in (None, ""))

    # postes de dépense (dépenses récurrentes mensuelles + crédits du mois)
    postes = {}
    for t in transactions:
        if _mensuel(t) or str(t.get("date_depense") or "").startswith(mois):
            k = str(t.get("categorie") or "autre").capitalize()
            postes[k] = postes.get(k, 0.0) + t["usd"]
    postes = sorted(postes.items(), key=lambda kv: -kv[1])

    echeances = sorted([t for t in transactions if t.get("prochaine_echeance")], key=lambda x: x["prochaine_echeance"])

    # IA payantes : coût estimé par jour (30 jours)
    debut = (auj - timedelta(days=29)).isoformat()
    ia = {}
    try:
        for r in db.all("SELECT api, day, units_used FROM api_quota WHERE api LIKE 'cout-%' AND day >= ? ORDER BY day", [debut]):
            j = str(r["day"])[:10]
            ia.setdefault(j, {})[r["api"][5:]] = int(r["units_used"] or 0) / 1e6
    except Exception:  # noqa: BLE001
        pass
    jours_ia = [((auj - timedelta(days=k)).isoformat()) for k in range(29, -1, -1)]
    ia_jours = [(j, sum((ia.get(j) or {}).values())) for j in jours_ia]
    ia_total = sum(v for _, v in ia_jours)
    ia_par = {}
    for j in ia.values():
        for f, v in j.items():
            ia_par[f] = ia_par.get(f, 0.0) + v

    # partenaires et éditions envoyées
    partenaires = []
    try:
        partenaires = db.all("""SELECT a.id, a.nom, a.pays, a.actif, a.contrat_signe, a.cree_le,
                                   (SELECT COUNT(*) FROM partenaires_editions e WHERE e.partenaire_id = a.id) AS editions,
                                   (SELECT COUNT(*) FROM partenaires_editions e WHERE e.partenaire_id = a.id AND e.envoye_le IS NOT NULL) AS envoyees,
                                   (SELECT MAX(e.envoye_le) FROM partenaires_editions e WHERE e.partenaire_id = a.id) AS dernier
                                FROM partenaires_acces a ORDER BY a.cree_le""")
    except Exception:  # noqa: BLE001
        pass

    # rapports hebdomadaires archivés
    rapports = []
    try:
        from core import storage
        for b in storage.blob_list("rapports/hebdo/"):
            nom = (b.get("pathname") or "").split("/")[-1]
            m = re.match(r"rapport-(\d{4}-\d{2}-\d{2})", nom)
            rapports.append({"url": b.get("url"), "debut": m.group(1) if m else "", "titre": f"Semaine du {_date_fr(m.group(1))}" if m else nom})
        rapports.sort(key=lambda r: r["debut"], reverse=True)
    except Exception:  # noqa: BLE001
        pass

    jour_mois = auj.day
    n = lambda v, d=0: f"{v:,.{d}f}".replace(",", " ").replace(".", ",")  # noqa: E731
    phrases = [
        f"Cauri Charts fonctionne aujourd'hui pour environ {n(recurrent)} $ par mois de services (site, base de données, voix, domaine, bots)"
        + (f", plus {n(recurrent_fondateur)} $ d'abonnements pris en charge par le fondateur." if recurrent_fondateur else "."),
        f"Ce mois-ci, {n(ce_mois, 2)} $ ont été dépensés au {jour_mois} {MOIS[auj.month - 1]}"
        + (f", et les services payés à l'usage (IA, Apify) ont coûté environ {n(ia_total, 2)} $ sur 30 jours." if ia_total else "."),
        (f"Recettes enregistrées : {n(recettes_total)} $." if recettes else
         "Aucune recette n'est encore enregistrée : la priorité reste l'audience (objectif 10 000 abonnés au 31 décembre)."),
    ]
    return {"transactions": transactions, "recurrent": recurrent, "recurrent_fondateur": recurrent_fondateur, "ce_mois": ce_mois,
            "recettes": recettes, "recettes_mois": recettes_mois, "recettes_total": recettes_total, "justificatifs": justificatifs,
            "a_confirmer": a_confirmer, "postes": postes, "echeances": echeances, "ia_jours": ia_jours, "ia_total": ia_total,
            "ia_par": sorted(ia_par.items(), key=lambda kv: -kv[1]), "partenaires": partenaires, "rapports": rapports,
            "phrases": phrases, "mois_fr": f"{MOIS[auj.month - 1]} {auj.year}", "taux": _taux(), "auj": auj.isoformat()}


@admin_view("admin")
def page(request):
    d = donnees()
    d["partenaire"] = request.GET.get("vue") == "partenaire"
    d["title"] = "Économie"
    return admin_render(request, "economie", d)
