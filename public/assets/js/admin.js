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
