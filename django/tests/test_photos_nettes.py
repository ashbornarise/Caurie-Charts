from core.services.social import monde as M


def test_plus_grande_taille_apple_et_deezer():
    apple = "https://is1-ssl.mzstatic.com/image/thumb/AMCArtistImages/v4/a/b/file_cropped.png/800x800bb.jpg"
    assert M._plus_grande(apple).endswith("/file_cropped.png/3000x3000bb.jpg")
    deezer = "https://cdn-images.dzcdn.net/images/artist/abc/1000x1000-000000-80-0-0.jpg"
    assert M._plus_grande(deezer).endswith("/1200x1200-000000-80-0-0.jpg")
    autre = "https://exemple.com/photo.jpg"
    assert M._plus_grande(autre) == autre
    assert "\x02" not in open(M.__file__, encoding="utf-8").read()
