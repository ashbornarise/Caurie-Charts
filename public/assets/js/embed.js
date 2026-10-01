// Page « Intégrer le classement » : copie du code d'intégration
document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
        var field = document.getElementById(btn.getAttribute('data-copy'));
        if (!field) return;
        field.select();
        var done = function () { btn.textContent = 'Copié !'; };
        if (navigator.clipboard) {
            navigator.clipboard.writeText(field.value).then(done, function () { document.execCommand('copy'); done(); });
        } else {
            document.execCommand('copy');
            done();
        }
    });
});

// Aperçu mis à jour dès qu'un réglage change
document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
    form.addEventListener('change', function () { form.submit(); });
});
