"""Fiche d'accueil d'un membre de l'équipe (PDF) : accès, rôle, classements, principes et règles de Cauri Charts.

Le mot de passe n'y figure que s'il vient d'être créé (il n'est jamais conservé en clair) ; sinon la ligne est vide.
"""
from datetime import date

from django.conf import settings
from fpdf import FPDF

from core.helpers import url

FONTS = settings.REPO_DIR / "resources" / "fonts"
GOLD, INK, MUTED, LINE = (201, 151, 46), (17, 17, 17), (95, 95, 95), (225, 222, 214)

ROLES = {"admin": ("Administrateur", "Tout l'administratif : publication des classements, formule, journal d'audit, équipe."),
         "editor": ("Éditeur", "Classements, déclarations, actualités, posts réseaux sociaux et messages. Pas de formule ni d'équipe.")}

CHARTS = [
    ("Top 20 Afrique de l'Ouest", "Le classement phare : 16 pays, chaque pays pèse autant, au plus 5 titres d'un même pays."),
    ("Prime", "Le classement principal de chaque pays : les titres les plus écoutés de la semaine."),
    ("Buzz", "Les titres qui montent le plus vite, hors Top : la découverte."),
    ("Fresh", "Les sorties des 8 dernières semaines et les artistes émergents."),
    ("Icon", "Les artistes (et non les titres) les plus présents, tous titres confondus."),
    ("Legend", "Le cumul depuis le début des relevés : les classiques."),
]

PRINCIPLES = [
    ("Indépendance", "Personne n'achète une place. Ni un artiste, ni un label, ni un partenaire, ni un sponsor."),
    ("Transparence", "La méthode est publique (page Méthodologie). Toute règle nouvelle y est expliquée avant d'être appliquée."),
    ("Exactitude", "Uniquement des données réelles, relevées sur les plateformes. Une erreur se corrige publiquement."),
    ("Traçabilité", "Chaque chiffre renvoie à sa source (Deezer, Apple Music, Shazam, YouTube) et à sa date."),
    ("Intégrité éditoriale", "Un contenu payant est toujours signalé comme tel et n'influence jamais un classement."),
]

RULES = [
    "Activez la double authentification dès la première connexion (lien proposé en haut de l'admin).",
    "Ne partagez jamais vos accès ; chaque action est enregistrée au journal d'audit à votre nom.",
    "Ne communiquez pas un classement officiel avant qu'il soit publié dans l'admin.",
    "N'inventez aucun chiffre et ne modifiez aucune donnée relevée : signalez une anomalie, l'admin tranche.",
    "Les clips et visuels d'artistes ne viennent que de l'artiste, de son label ou des plateformes officielles.",
    "Conflit d'intérêts (vous travaillez avec un artiste classé) : signalez-le avant toute décision le concernant.",
]


class _Doc(FPDF):
    def header(self):
        self.set_fill_color(*INK)
        self.rect(0, 0, 210, 14, "F")
        self.set_xy(15, 4)
        self.set_font("anton", size=13)
        self.set_text_color(*GOLD)
        self.cell(0, 6, "CAURI CHARTS")
        self.set_xy(-80, 4.5)
        self.set_font("lato", size=8)
        self.set_text_color(255, 255, 255)
        self.cell(65, 6, "Fiche d'accueil de l'équipe", align="R")
        self.set_y(22)

    def footer(self):
        self.set_y(-12)
        self.set_font("lato", size=7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Document interne et confidentiel · cauricharts.com · page {self.page_no()}", align="C")


def _title(pdf: FPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("anton", size=15)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, text.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 40, pdf.get_y())
    pdf.ln(3)


def _pairs(pdf: FPDF, rows: list, key_w: float = 48) -> None:
    for key, value in rows:
        y = pdf.get_y()
        pdf.set_font("latob", size=9.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(key_w, 5.2, key)
        end = pdf.get_y()
        pdf.set_xy(15 + key_w, y)
        pdf.set_font("lato", size=9.5)
        pdf.set_text_color(55, 55, 55)
        pdf.multi_cell(180 - key_w, 5.2, value)
        pdf.set_y(max(end, pdf.get_y()) + 1.6)


def build(member: dict, password: str | None = None) -> bytes:
    pdf = _Doc(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, 16)
    pdf.add_font("anton", fname=str(FONTS / "Anton-Regular.ttf"))
    pdf.add_font("lato", fname=str(FONTS / "Lato-Regular.ttf"))
    pdf.add_font("latob", fname=str(FONTS / "Lato-Bold.ttf"))
    pdf.add_page()

    pdf.set_font("anton", size=30)
    pdf.set_text_color(*INK)
    pdf.cell(0, 14, "BIENVENUE, " + str(member["name"]).upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("lato", size=10.5)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5.5, "Cauri Charts mesure la musique d'Afrique de l'Ouest : des classements hebdomadaires bâtis sur des "
                           "données réelles, pour 16 pays. Cette fiche réunit vos accès et les règles que toute l'équipe applique.")

    role, scope = ROLES.get(member["role"], (member["role"], ""))
    _title(pdf, "Vos accès")
    pdf.set_fill_color(248, 244, 233)
    top = pdf.get_y()
    pdf.rect(15, top, 180, 36, "F")
    pdf.set_y(top + 3)
    _pairs(pdf, [("Adresse de connexion", url("admin/connexion")), ("Identifiant (e-mail)", member["email"]),
                 ("Mot de passe", password or "transmis séparément (ou « Nouveau mot de passe » dans Admin > Équipe)"),
                 ("Rôle", f"{role} : {scope}")], 50)
    pdf.set_y(top + 39)
    pdf.set_font("lato", size=8.5)
    pdf.set_text_color(160, 60, 40)
    pdf.multi_cell(0, 4.6, "Changez ce mot de passe à la première connexion et gardez cette fiche privée : "
                           "ne l'envoyez pas dans un groupe, ne l'imprimez pas sur un poste partagé.")

    _title(pdf, "Nos classements")
    _pairs(pdf, CHARTS, 52)
    pdf.set_font("lato", size=8.8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4.8, "Sources : Deezer, Apple Music, Shazam, YouTube (tendances, nouveaux clips, vues). Relevés chaque nuit ; "
                           "classement officiel calculé le lundi, vérifié puis publié dans l'admin. Méthode complète : "
                           + url("methodologie"))

    _title(pdf, "Ce qui est sacré")
    _pairs(pdf, PRINCIPLES, 44)

    _title(pdf, "Règles de l'équipe")
    pdf.set_font("lato", size=9.5)
    pdf.set_text_color(55, 55, 55)
    for i, rule in enumerate(RULES, 1):
        pdf.set_font("latob", size=9.5)
        pdf.cell(7, 5.4, f"{i}.")
        pdf.set_font("lato", size=9.5)
        pdf.multi_cell(0, 5.4, rule)
        pdf.ln(0.8)

    _title(pdf, "Vos premiers pas")
    _pairs(pdf, [("1. Connexion", "Connectez-vous, changez le mot de passe, activez la double authentification."),
                 ("2. Méthodologie", "Lisez la page Méthodologie du site : c'est elle que l'on cite aux artistes."),
                 ("3. Tableau de bord", "Admin > Tableau de bord : relevés de la nuit, signalements, posts à valider."),
                 ("4. Une question", "Écrivez à l'administrateur qui vous a créé ce compte.")], 38)
    pdf.ln(2)
    pdf.set_font("lato", size=8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, f"Fiche éditée le {date.today():%d/%m/%Y}.")
    return bytes(pdf.output())
