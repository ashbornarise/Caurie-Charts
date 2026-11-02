// Administration : bouton « Copier la légende » (posts réseaux sociaux)
document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
        var field = document.getElementById(btn.getAttribute('data-copy'));
        if (!field) { return; }
        var done = function () {
            var label = btn.textContent;
            btn.textContent = 'Copié ✓';
            setTimeout(function () { btn.textContent = label; }, 1800);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(field.value).then(done, function () { field.select(); document.execCommand('copy'); done(); });
        } else {
            field.select();
            document.execCommand('copy');
            done();
        }
    });
});

// Menu latéral : ouvert sur ordinateur, replié derrière « Menu » sur téléphone (refonte du 02/11/2026)
(function () {
    var menu = document.querySelector('.adm-menu__plier');
    if (!menu) return;
    var large = window.matchMedia('(min-width: 980px)');
    var regle = function () { menu.open = large.matches; };
    regle();
    if (large.addEventListener) large.addEventListener('change', regle);
})();
