// JavaScript minimal : le sélecteur d'historique change de page sans bouton.
document.querySelectorAll('[data-history-select]').forEach(function (select) {
    select.addEventListener('change', function () {
        if (select.value.indexOf('/classements/') === 0) {
            window.location.href = select.value;
        }
    });
});
