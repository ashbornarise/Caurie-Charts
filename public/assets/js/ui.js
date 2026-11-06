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

/* Défilé des pochettes de l'accueil (06/11/2026) : la carte au centre en grand, le lecteur affiche le titre ; avance seul
   toutes les 4 secondes (arrêt au survol, au toucher, avec le bouton pause, ou si l'utilisateur réduit les animations) */
(function () {
  var flow = document.querySelector('[data-flow]');
  if (!flow) return;
  var piste = flow.querySelector('[data-flow-piste]'), cartes = Array.prototype.slice.call(piste.children);
  if (!cartes.length) return;
  var courant = 0, minuterie = null, enPause = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function affiche(i) {
    courant = (i + cartes.length) % cartes.length;
    cartes.forEach(function (c, k) {
      c.classList.toggle('est-centre', k === courant);
      c.classList.toggle('est-gauche', k < courant);
      c.classList.toggle('est-droite', k > courant);
    });
    var c = cartes[courant];
    flow.querySelector('[data-flow-titre]').textContent = c.dataset.titre;
    flow.querySelector('[data-flow-artiste]').textContent = c.dataset.artiste;
    flow.querySelector('[data-flow-rang]').textContent = 'N°' + c.dataset.rang;
    flow.querySelector('[data-flow-lien]').href = c.dataset.lien;
    var img = flow.querySelector('[data-flow-img]');
    if (c.dataset.cover) { img.src = c.dataset.cover; img.hidden = false; } else { img.hidden = true; }
  }
  function centre(i, doux) {
    affiche(i);
    var c = cartes[courant];
    piste.scrollTo({left: c.offsetLeft - (piste.clientWidth - c.offsetWidth) / 2, behavior: doux ? 'smooth' : 'auto'});
  }
  function arrete() { if (minuterie) { clearInterval(minuterie); minuterie = null; } }
  // avance par rang (1, 2, 3…) : le N°1 est au centre, les autres alternent à gauche et à droite
  function parRang(delta) {
    var n = cartes.length, r = +cartes[courant].dataset.rang, cible = ((r - 1 + delta) % n + n) % n + 1;
    for (var k = 0; k < n; k++) { if (+cartes[k].dataset.rang === cible) return k; }
    return courant;
  }
  function lance() { arrete(); if (!enPause) minuterie = setInterval(function () { centre(parRang(1), true); }, 4000); }
  flow.querySelector('[data-flow-prec]').addEventListener('click', function () { centre(parRang(-1), true); lance(); });
  flow.querySelector('[data-flow-suiv]').addEventListener('click', function () { centre(parRang(1), true); lance(); });
  var bp = flow.querySelector('[data-flow-pause]');
  bp.addEventListener('click', function () { enPause = !enPause; bp.classList.toggle('est-pause', enPause); if (enPause) { arrete(); } else { lance(); } });
  cartes.forEach(function (c, k) {
    c.addEventListener('click', function (ev) { if (k !== courant) { ev.preventDefault(); centre(k, true); lance(); } });
  });
  // défilement au doigt : la carte la plus proche du centre devient la carte courante
  var att = null;
  piste.addEventListener('scroll', function () {
    clearTimeout(att);
    att = setTimeout(function () {
      var mid = piste.scrollLeft + piste.clientWidth / 2, best = 0, d = Infinity;
      cartes.forEach(function (c, k) { var x = Math.abs(c.offsetLeft + c.offsetWidth / 2 - mid); if (x < d) { d = x; best = k; } });
      if (best !== courant) affiche(best);
    }, 90);
  }, {passive: true});
  flow.addEventListener('mouseenter', arrete);
  flow.addEventListener('mouseleave', lance);
  piste.addEventListener('touchstart', arrete, {passive: true});
  var un = 0;
  cartes.forEach(function (c, k) { if (c.dataset.rang === '1') un = k; });
  centre(un, false);
  lance();
})();
