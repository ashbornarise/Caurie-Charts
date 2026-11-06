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
