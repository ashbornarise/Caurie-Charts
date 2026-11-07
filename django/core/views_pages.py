"""Pages dédiées appelées par le pied de page (06/11/2026) : tous les pays, et les tendances du moment."""
from core import db, repos
from core.i18n import tr
from core.views import render, use_locale


def pays(request):
    """Les 16 pays : drapeau, N°1 officiel de la dernière semaine publiée, lien vers le classement."""
    use_locale(request)
    n1 = {r["code"]: r for r in db.all(
        """SELECT DISTINCT ON (c.code) c.code, t.title, t.slug AS track_slug, a.name AS artist_name, r.period_key
           FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code = 'prime'
           JOIN countries c ON c.id = r.country_id JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
           JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
           WHERE r.status = 'published' AND r.period_type = 'week' ORDER BY c.code, r.period_start DESC""")}
    return render(request, "pays", {"n1": n1, "meta": {"title": tr("Tous les pays") + " · Cauri Charts",
                                                       "description": tr("Les classements de la musique des 16 pays d’Afrique de l’Ouest.")}})


def tendances(request):
    """Artistes et titres les plus présents dans les relevés des plateformes ces derniers jours."""
    use_locale(request)
    artistes = db.all("""SELECT a.name, a.slug, COALESCE(a.image_hd_url, a.image_url) AS image, c.code AS pays
                         FROM artists a LEFT JOIN countries c ON c.id = a.submission_country_id WHERE a.status = 'active'
                         AND EXISTS (SELECT 1 FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                     WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7)
                         ORDER BY COALESCE(a.youtube_subscribers, 0) + COALESCE(a.fans, 0) DESC LIMIT 24""")
    titres = db.all("""SELECT t.title, t.slug, t.cover_url, a.name AS artist_name, c.code AS pays
                       FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                       LEFT JOIN countries c ON c.id = a.submission_country_id
                       WHERE a.status = 'active' AND o.observed_on >= CURRENT_DATE - 3
                       GROUP BY t.id, t.title, t.slug, t.cover_url, a.name, c.code
                       ORDER BY COUNT(DISTINCT o.source || o.country_id) DESC, MIN(o.position) LIMIT 24""")
    return render(request, "tendances", {"artistes": artistes, "titres": titres,
                                         "meta": {"title": tr("Tendances") + " · Cauri Charts",
                                                  "description": tr("Les artistes et les titres qui montent sur les plateformes en Afrique de l’Ouest.")}})


ARTISTES_PAR_PAGE = 48


def artistes(request):
    """Tous les artistes suivis (07/11/2026), filtrables par pays, avec recherche et tri. Adresse partageable :
    /artistes?pays=ci&tri=spotify&q=did&page=2 (une adresse par vue, donc compatible avec le cache)."""
    from core.views import req_str
    use_locale(request)
    codes = {c["code"].lower(): c for c in repos.countries()}
    pays = req_str(request, "pays").lower()
    pays = pays if pays in codes else ""
    q = req_str(request, "q").strip()[:60]
    tri = req_str(request, "tri", "populaires")
    tri = tri if tri in ("populaires", "spotify", "youtube", "nom") else "populaires"
    try:
        page = max(1, int(req_str(request, "page", "1") or 1))
    except ValueError:
        page = 1
    where, params = ["a.status = 'active'", "c.code IS NOT NULL"], []
    if pays:
        where.append("c.code = ?")
        params.append(pays.upper())
    if q:
        where.append("a.name ILIKE ?")
        params.append("%" + q.replace("%", "").replace("_", "") + "%")
    ordre = {"nom": "lower(a.name)",
             "spotify": "sp.auditeurs DESC NULLS LAST, a.name",
             "youtube": "a.youtube_subscribers DESC NULLS LAST, a.name",
             "populaires": "(COALESCE(sp.auditeurs, 0) + COALESCE(a.youtube_subscribers, 0) * 3 + COALESCE(a.fans, 0)) DESC, a.name"}[tri]
    base = f"""FROM artists a LEFT JOIN countries c ON c.id = a.submission_country_id
               LEFT JOIN LATERAL (SELECT s.auditeurs FROM spotify_artistes s WHERE s.artist_id = a.id AND s.auditeurs IS NOT NULL
                                  ORDER BY s.releve_le DESC LIMIT 1) sp ON TRUE
               WHERE {' AND '.join(where)}"""
    total = int(db.value("SELECT COUNT(*) " + base, params) or 0)
    pages = max(1, -(-total // ARTISTES_PAR_PAGE))
    page = min(page, pages)
    liste = db.all(f"""SELECT a.name, a.slug, COALESCE(a.image_hd_url, a.image_url) AS image, c.code AS pays,
                              sp.auditeurs, a.youtube_subscribers {base} ORDER BY {ordre}
                       LIMIT {ARTISTES_PAR_PAGE} OFFSET {(page - 1) * ARTISTES_PAR_PAGE}""", params)
    compte = {r["code"]: int(r["n"]) for r in db.all(
        """SELECT c.code, COUNT(*) n FROM artists a JOIN countries c ON c.id = a.submission_country_id
           WHERE a.status = 'active' GROUP BY c.code""")}
    from core.helpers import country_name
    titre = tr("Tous les artistes") + (" · " + country_name(pays.upper()) if pays else "")
    return render(request, "artistes", {"liste": liste, "total": total, "page": page, "pages": pages, "pays": pays, "q": q,
                                        "tri": tri, "compte": compte, "robots": "noindex" if q or page > 1 else None,
                                        "meta": {"title": titre + " · Cauri Charts",
                                                 "description": tr("Tous les artistes suivis par Cauri Charts dans les 16 pays d’Afrique de l’Ouest.")}})
