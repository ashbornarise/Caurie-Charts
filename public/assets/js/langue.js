/* Langue du site (06/11/2026) : à la première visite, la langue du navigateur choisit la version (français ou /en) ;
   ensuite, le choix du visiteur (lien FR / EN) est retenu sur cet appareil. Chargé dans <head>, avant l'affichage. */
(function () {
  try {
    var p = location.pathname, en = p === '/en' || p.indexOf('/en/') === 0;
    if (/^\/(admin|studio|api)(\/|$)/.test(p)) return;
    var choix = null;
    try { choix = localStorage.getItem('cc_lang'); } catch (e) {}
    if (!choix) {
      // Première visite : on suit le navigateur, sans contredire un lien /en partagé
      var l = ((navigator.languages && navigator.languages[0]) || navigator.language || 'fr').toLowerCase();
      if (!en && l.indexOf('fr') !== 0) location.replace('/en' + (p === '/' ? '/' : p) + location.search + location.hash);
      return;
    }
    if (choix === 'en' && !en) location.replace('/en' + (p === '/' ? '/' : p) + location.search + location.hash);
    else if (choix === 'fr' && en) location.replace((p.slice(3) || '/') + location.search + location.hash);
  } catch (e) {}
  // Lien FR / EN : retenir le choix
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('[data-langue]');
    if (a) { try { localStorage.setItem('cc_lang', a.getAttribute('data-langue')); } catch (e) {} }
  });
})();
