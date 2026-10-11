// Vote du public : barres de résultat (largeur via JS, pas de style en ligne : CSP).
document.querySelectorAll('.show-res__b[data-p]').forEach(function (b) { b.style.width = b.dataset.p + '%'; });
