"""Envoi TikTok par morceaux (05/11/2026) : « The chunk size is invalid » sur une vidéo de 10 à 20 Mo."""
from core.services import tiktok_publie as T

MO = 1024 * 1024


def test_un_seul_morceau_jusqu_a_64_mo():
    for taille in (2 * MO, 7 * MO, 15 * MO, 64 * MO):
        s = T._source(taille)
        assert s["total_chunk_count"] == 1 and s["chunk_size"] == taille


def test_gros_fichier_en_morceaux():
    s = T._source(95 * MO + 123)
    assert s["chunk_size"] == 10 * MO and s["total_chunk_count"] == 9
    # le dernier morceau absorbe le reste et reste sous la limite de 128 Mo
    assert s["video_size"] - (s["total_chunk_count"] - 1) * s["chunk_size"] < 128 * MO
