"""Écoutes Spotify de chaque titre (07/11/2026) : lecture de la page Kworb d'un artiste."""
from core.services.imports import spotify_ecoutes as S

PAGE = ('<html><body>Last updated: 2026/11/05<table>'
        '<tr><td class="text"><div><a href="https://open.spotify.com/track/2REbaRuhstqXHA06wtdOMb" target="_blank">NUMBER ONE (feat. Minz)</a></div></td><td>41,985,916</td><td>60,504</td></tr>'
        '<tr><td class="text"><div>* <a href="https://open.spotify.com/track/7LqBwxnUwyGv9zqTVL2bYG" target="_blank">Légendes</a></div></td><td>9,602,010</td><td>12,008</td></tr>'
        '</table></body></html>')


class _Rep:
    status_code = 200
    content = PAGE.encode("utf-8")

    def raise_for_status(self):
        pass


class _Session:
    def get(self, *a, **k):
        return _Rep()


def test_lecture_kworb():
    lignes, jour = S.lire_kworb("39SBljHcUD66edvRmiRqlS", _Session())
    assert jour == "2026-11-05"
    assert lignes == [("2REbaRuhstqXHA06wtdOMb", "NUMBER ONE (feat. Minz)", 41985916, 60504, False),
                      ("7LqBwxnUwyGv9zqTVL2bYG", "Légendes", 9602010, 12008, True)]   # « * » : featuring
