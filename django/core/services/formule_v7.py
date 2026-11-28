"""Formule v7 des classements (21/11/2026) — « La méthode Cauri Charts », Downloads\\Cauri-Charts-Methode-Formule-v7.pdf.

Travail croisé (Gemini, DeepSeek, Qwen) puis banc d'essai sur les données réelles du Nigeria S47 (accord avec TurnTable :
0,24 pour une formule de type v6, 0,538 pour la v7 à poids égaux). En Python pur : ni numpy ni scipy sur Vercel.

Étapes (notations du document) :
 1. Chaque classement de plateforme -> part d'écoute estimée par la loi de Zipf-Mandelbrot z(r) = (r+β)^-α / Σ_k (k+β)^-α
    (α, β mesurés sur Spotify Nigeria) ; jour d'absence = valeur censurée z(N+1) (jamais zéro) ; moyenne sur les jours relevés.
 2. YouTube (vues MONDIALES de la semaine) compressé : y = V^γ / Σ V^γ ; titre sans clip officiel : YouTube absent.
    Poids π_YT = π_max / (1 + λ L), L = Σ q_s des sources d'écoute du pays.
 3. Couverture q_s = n_s / (n_s + κ), poids brut ω_s q_s (ω = 2 pour Spotify, seule mesure d'écoutes DANS un pays).
 4. Score : moyenne géométrique pondérée, ramenée à 10 000 points dans le pays.
 6. Anti-fraude YouTube : pic (écart robuste, MAD) et engagement (loi bêta des j'aime/vues), combinés par Fisher (χ² à
    4 degrés), seuil de Bonferroni 0,01/N ; un clip suspect est retiré du score du titre jusqu'à la revue humaine.
 8. Fiabilité du pays F = Σ ω q / (1 + Σ ω q).
"""
import math
from statistics import median

PLANCHER_P = 1e-12


# ---------------------------------------------------------------- étape 1 : rangs -> parts d'écoute

class Zipf:
    def __init__(self, alpha: float, beta: float):
        self.a, self.b, self._z = float(alpha), float(beta), {}

    def total(self, n: int) -> float:
        if n not in self._z:
            self._z[n] = sum((k + self.b) ** -self.a for k in range(1, n + 1))
        return self._z[n]

    def part(self, r: float, n: int) -> float:
        return (r + self.b) ** -self.a / self.total(n)


def parts_classements(obs: list, ids: set, zipf: Zipf) -> tuple[dict, dict]:
    """obs : [(track_id, source, jour, position)] des classements DU pays pendant la semaine (tous les titres, étrangers
    compris : le dénominateur est le classement entier). Renvoie ({track_id: {source: x}}, {source: {N, jours, n}}).
    Un titre suivi absent d'une source relevée reçoit la valeur censurée z(N+1) chaque jour."""
    meta: dict = {}
    for tid, s, jour, pos in obs:
        m = meta.setdefault(s, {"N": 0, "jours": set(), "titres": set()})
        m["N"] = max(m["N"], int(pos))
        m["jours"].add(str(jour)[:10])
        if tid in ids:
            m["titres"].add(tid)
    somme: dict = {}
    vus: dict = {}
    for tid, s, jour, pos in obs:
        if tid not in ids:
            continue
        cle = (tid, s, str(jour)[:10])
        if cle in vus:          # deux lignes le même jour (doublon d'import) : la meilleure place
            vus[cle] = min(vus[cle], int(pos))
        else:
            vus[cle] = int(pos)
    for (tid, s, _), pos in vus.items():
        d = somme.setdefault(tid, {}).setdefault(s, [0.0, 0])
        d[0] += zipf.part(pos, meta[s]["N"])
        d[1] += 1
    x: dict = {}
    for tid in ids:
        x[tid] = {}
        for s, m in meta.items():
            dj = len(m["jours"])
            cens = zipf.part(m["N"] + 1, m["N"] + 1)
            tot, pres = (somme.get(tid) or {}).get(s, (0.0, 0))
            x[tid][s] = (tot + (dj - pres) * cens) / dj
    infos = {s: {"N": m["N"], "jours": len(m["jours"]), "n": len(m["titres"])} for s, m in meta.items()}
    return x, infos


# ---------------------------------------------------------------- étape 2 : YouTube

def parts_youtube(vues: dict, avec_clip: set, gamma: float) -> dict:
    """vues : {track_id: vues gagnées dans la semaine}. Titre sans clip officiel : absent du résultat (pas un zéro). Clip
    sans vue cette semaine : la moitié de la plus petite part observée (jamais ln 0)."""
    comp = {t: float(v) ** gamma for t, v in vues.items() if t in avec_clip and v and v > 0}
    # dénominateur : les 100 premiers clips du pays, comme un classement de 100 (parts comparables d'un pays à l'autre,
    # comme celles des classements de plateformes ; essai S47 : la somme sur tout le catalogue favorisait les petits pays)
    tot = sum(sorted(comp.values(), reverse=True)[:100])
    if not tot:
        return {}
    y = {t: c / tot for t, c in comp.items()}
    plancher = min(y.values()) / 2
    return {t: y.get(t, plancher) for t in avec_clip}


# ---------------------------------------------------------------- étape 6 : anti-fraude

def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _betacf(a: float, b: float, x: float) -> float:
    """Fraction continue de la fonction bêta incomplète (Numerical Recipes, 6.4)."""
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c; c = c if abs(c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c; c = c if abs(c) > 1e-30 else 1e-30
        de = d * c
        h *= de
        if abs(de - 1) < 3e-12:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """Fonction de répartition de la loi bêta (fonction bêta incomplète régularisée)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1 - math.exp(lb) * _betacf(b, a, 1 - x) / b


def chi2_4_queue(t: float) -> float:
    """P(χ²(4) > t) = e^(-t/2) (1 + t/2) (forme exacte à 4 degrés de liberté)."""
    return math.exp(-t / 2) * (1 + t / 2) if t > 0 else 1.0


def fraude(vues: dict, likes: dict, histo: dict, seuil_vues: int = 10000, alpha: float = 0.01, sigma_min: float = 0.5,
           nouveaux: set | None = None) -> dict:
    """Clips suspects : {track_id: p} pour ceux dont la p-value combinée est sous 0,01/N (Bonferroni).
    vues / likes : semaine en cours ; histo : {track_id: [vues des semaines précédentes, de la plus récente à la plus ancienne]}.
    Pic : testé seulement avec au moins 4 semaines d'historique (MAD sur 8 au plus, écart plancher σ_min = 0,5) ; engagement : loi bêta ajustée par la
    méthode des moments sur les clips de la semaine à 10 000 vues ou plus."""
    testes = [t for t, v in vues.items() if v and v >= seuil_vues]
    ratios = {t: likes[t] / vues[t] for t in testes if likes.get(t) is not None and 0 <= likes[t] <= vues[t]}
    a = b = None
    vals = [r for r in ratios.values() if 0 < r < 1]
    if len(vals) >= 20:
        m = sum(vals) / len(vals)
        var = sum((r - m) ** 2 for r in vals) / (len(vals) - 1)
        if 0 < var < m * (1 - m):
            k = m * (1 - m) / var - 1
            a, b = m * k, (1 - m) * k
    suspects = {}
    for t in testes:
        p_pic = 1.0
        h = [v for v in (histo.get(t) or []) if v and v > 0][:8]
        if len(h) >= 4 and t not in (nouveaux or ()):  # nouveau clip officiel : le bond de vues est attendu
            lh = [math.log(v) for v in h]
            med4 = median(lh[:4])
            med8 = median(lh)
            # plancher d'écart (essai S47 : 97 clips « suspects » au Nigeria, dont Oh No de Rema qui doublait ; sur un titre très
            # régulier, la MAD est minuscule et toute croissance normale paraissait anormale) : σ ≥ 0,5, il faut ~×5 pour alerter
            sig = max(1.4826 * median([abs(x - med8) for x in lh]), sigma_min)
            # référence = la plus haute de la médiane des 4 semaines et de la semaine d'avant (essai S47 : des clips remplacés
            # par le bon clip officiel le 09/11 passaient de quelques milliers à des millions de vues, sans aucune fraude ; une
            # vraie fraude se voit d'abord comme un saut par rapport à la semaine juste avant)
            z = (math.log(vues[t]) - max(med4, lh[0])) / sig
            p_pic = 1 - _phi(z)
        p_eng = 1.0
        if a and t in ratios:
            f = beta_cdf(ratios[t], a, b)
            p_eng = 2 * min(f, 1 - f)
        tt = -2 * (math.log(max(p_pic, PLANCHER_P)) + math.log(max(p_eng, PLANCHER_P)))
        p = chi2_4_queue(tt)
        if testes and p < alpha / len(testes):
            suspects[t] = p
    return suspects


# ---------------------------------------------------------------- étapes 2 à 4 et 8 : score du pays

def scores(ids: list, x: dict, infos: dict, yt: dict, suspects: set, p: dict, seul_yt: set | None = None) -> tuple[dict, dict]:
    """Score de chaque titre sur 10 000 points dans le pays, détail par titre, fiabilité du pays.
    p : paramètres (omega, kappa, pi_max, lambda, youtube_seul). Renvoie ({track_id: détail}, {fiabilite, poids, pi_yt}).
    seul_yt : titres absents de TOUS les classements d'écoute du pays pendant la semaine. Décision du fondateur (28/11/2026) :
    un tube qui ne vit que sur YouTube a sa place. Avec p["youtube_seul"] = f, son score vient de sa seule part YouTube,
    multipliée par f (une seule source, donc moins sûre) ; sans ce réglage, ses écoutes valent la note plancher partout
    et ses vues ne pèsent que π_YT (il ne pouvait jamais monter). Un clip suspect (anti-fraude) n'a pas cette voie."""
    f_seul = float(p.get("youtube_seul") or 0)
    kappa, omega = float(p.get("kappa", 5)), p.get("omega") or {}
    q = {s: m["n"] / (m["n"] + kappa) for s, m in infos.items() if m["jours"] > 0}
    wq = {s: float(omega.get(s, 1)) * q[s] for s in q}
    somme = sum(wq.values())
    L = sum(q.values())
    pi_yt = float(p.get("pi_max", 0.5)) / (1 + float(p.get("lambda", 0.8)) * L) if somme > 0 else 1.0
    b_audio = {s: (1 - pi_yt) * w / somme for s, w in wq.items()} if somme > 0 else {}
    fiab = somme / (1 + somme)
    out, S = {}, {}
    for t in ids:
        if f_seul > 0 and t in (seul_yt or ()) and t in yt and t not in suspects:
            S[t] = f_seul * yt[t]
            out[t] = {"geo": S[t], "poids": {"youtube": 1.0}, "parts": {"youtube": round(yt[t], 8)}, "youtube_seul": f_seul}
            continue
        b = dict(b_audio)
        if t in yt and t not in suspects:
            b["youtube"] = pi_yt
        tot = sum(b.values())
        if tot <= 0:
            continue
        ln = 0.0
        for s, w in b.items():
            v = yt[t] if s == "youtube" else x[t][s]
            ln += (w / tot) * math.log(v)
        S[t] = math.exp(ln)
        out[t] = {"geo": S[t], "poids": {s: round(w / tot, 4) for s, w in b.items()},
                  "parts": {s: round(yt[t] if s == "youtube" else x[t][s], 8) for s in b}}
    total = sum(S.values()) or 1
    for t in out:
        out[t]["score"] = round(10000 * S[t] / total, 4)
    return out, {"fiabilite": round(fiab, 4), "poids": {s: round(w, 4) for s, w in b_audio.items()}, "pi_yt": round(pi_yt, 4),
                 "couverture": {s: round(v, 4) for s, v in q.items()}}
