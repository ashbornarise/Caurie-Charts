// Finitions de l'interface (02/11/2026) : en-tête qui se détache au défilement, apparition douce des blocs,
// flèches sur les carrousels (ordinateur). Rien d'indispensable : sans JavaScript, tout reste lisible.
(function () {
    var calme = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var root = document.documentElement;

    // En-tête : ombre légère dès qu'on a quitté le haut de la page
    var header = document.querySelector('.site-header');
    if (header) {
        var surveille = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
        surveille();
        window.addEventListener('scroll', surveille, { passive: true });
    }

    // Apparition des blocs situés sous la ligne de flottaison (ceux déjà visibles ne bougent pas)
    if (!calme && 'IntersectionObserver' in window) {
        var cibles = document.querySelectorAll('main section, main .acc-fin__card, .pied__haut, .pied__cols > nav');
        var h = window.innerHeight;
        var obs = new IntersectionObserver(function (entrees) {
            entrees.forEach(function (e) {
                if (e.isIntersecting) { e.target.classList.add('is-in'); obs.unobserve(e.target); }
            });
        }, { rootMargin: '0px 0px -8% 0px' });
        root.classList.add('anime');
        Array.prototype.forEach.call(cibles, function (el, i) {
            if (el.getBoundingClientRect().top < h) return;
            el.classList.add('reveal');
            el.style.transitionDelay = (i % 4) * 40 + 'ms';
            obs.observe(el);
        });
    }

    // Visiteurs humains : une vue n'est comptée qu'après 1,5 s de page réellement affichée (la plupart des robots
    // n'exécutent pas ce script). Une « visite » = première page de l'onglet. Aucun cookie, aucun identifiant.
    if (navigator.sendBeacon && document.visibilityState !== 'prerender') {
        var envoye = false;
        var compte = function () {
            if (envoye || document.visibilityState !== 'visible') return;
            envoye = true;
            var nouvelle = false;
            try { nouvelle = !sessionStorage.getItem('cc_v'); sessionStorage.setItem('cc_v', '1'); } catch (e) { nouvelle = false; }
            navigator.sendBeacon('/api/vu', JSON.stringify({ p: location.pathname, r: document.referrer, n: nouvelle }));
        };
        setTimeout(compte, 1500);
        document.addEventListener('visibilitychange', function () { setTimeout(compte, 1500); });
    }

    // Carrousels : flèches précédent / suivant sur ordinateur
    if (window.matchMedia('(hover: hover) and (min-width: 820px)').matches) {
        Array.prototype.forEach.call(document.querySelectorAll('.acc-rail'), function (rail) {
            if (rail.scrollWidth <= rail.clientWidth + 8) return;
            var cadre = document.createElement('div');
            cadre.className = 'rail-cadre';
            rail.parentNode.insertBefore(cadre, rail);
            cadre.appendChild(rail);
            [['prev', -1, 'Précédent'], ['next', 1, 'Suivant']].forEach(function (b) {
                var bouton = document.createElement('button');
                bouton.type = 'button';
                bouton.className = 'rail-fleche rail-fleche--' + b[0];
                bouton.setAttribute('aria-label', b[2]);
                bouton.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="' +
                    (b[1] < 0 ? 'M15 18l-6-6 6-6' : 'M9 18l6-6-6-6') + '" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
                bouton.addEventListener('click', function () {
                    rail.scrollBy({ left: b[1] * rail.clientWidth * 0.85, behavior: calme ? 'auto' : 'smooth' });
                });
                cadre.appendChild(bouton);
            });
            var maj = function () {
                cadre.classList.toggle('au-debut', rail.scrollLeft < 8);
                cadre.classList.toggle('a-la-fin', rail.scrollLeft + rail.clientWidth > rail.scrollWidth - 8);
            };
            maj();
            rail.addEventListener('scroll', maj, { passive: true });
        });
    }
})();

/* Newsletter du pied de page (06/11/2026) : envoi en arrière-plan, les pages étant en cache */
(function () {
  var f = document.querySelector('[data-newsletter]');
  if (!f) return;
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var msg = f.querySelector('.pied__lettre-msg'), b = f.querySelector('button');
    b.disabled = true;
    fetch('/api/newsletter', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: f.email.value, langue: f.langue.value, site: f.site.value})})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        msg.textContent = d.statut === 'ok' ? msg.dataset.ok : d.statut === 'deja' ? msg.dataset.deja : msg.dataset.err;
        if (d.statut === 'ok') f.email.value = '';
      })
      .catch(function () { msg.textContent = msg.dataset.err; })
      .then(function () { b.disabled = false; });
  });
})();
