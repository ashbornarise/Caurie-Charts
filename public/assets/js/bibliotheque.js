// Bibliothèque Cauri Charts (18/11/2026) : filtres et lecteur
(function () {
    var data = {}; JSON.parse(document.getElementById('bib-data').textContent).forEach(function (e) { data[e.id] = e; });
    var cartes = [].slice.call(document.querySelectorAll('.bib-c')), page = 48, cat = '', type = '', q = '';
    var plus = document.getElementById('bib-plus'), vide = document.getElementById('bib-vide');
    function montre() {
        var n = 0;
        cartes.forEach(function (c) {
            var ok = (!cat || c.dataset.cat === cat) && (!type || c.dataset.type === type) && (!q || c.dataset.q.indexOf(q) >= 0);
            if (ok) n++;
            c.hidden = !ok || n > page;
        });
        plus.parentNode.hidden = n <= page;
        vide.hidden = n > 0;
    }
    document.querySelectorAll('.bib-chips .yt-chip').forEach(function (b) {
        b.addEventListener('click', function () {
            document.querySelectorAll('.bib-chips .yt-chip').forEach(function (x) { x.classList.remove('on'); });
            b.classList.add('on'); cat = b.dataset.cat; page = 48; montre();
        });
    });
    document.getElementById('bib-type').addEventListener('change', function (e) { type = e.target.value; page = 48; montre(); });
    document.getElementById('bib-q').addEventListener('input', function (e) { q = e.target.value.trim().toLowerCase(); page = 48; montre(); });
    plus.addEventListener('click', function () { page += 48; montre(); });
    montre();

    var dlg = document.getElementById('bib-lecteur'), media = document.getElementById('bib-media');
    function ouvre(id) {
        var e = data[id]; if (!e) return;
        media.innerHTML = '';
        if (e.video) {
            var v = document.createElement('video'); v.src = e.video; v.controls = true; v.playsInline = true; v.autoplay = true;
            if (e.image) v.poster = e.image; media.appendChild(v);
        } else {
            (e.pages && e.pages.length ? e.pages : [e.image]).forEach(function (u) {
                var i = document.createElement('img'); i.src = u; i.alt = e.titre; i.loading = 'lazy'; media.appendChild(i);
            });
        }
        document.getElementById('bib-l-cat').textContent = e.cat_nom || '';
        document.getElementById('bib-l-cat').className = 'bib-cat c-' + e.cat;
        document.getElementById('bib-l-titre').textContent = e.titre;
        document.getElementById('bib-l-meta').textContent = [e.date_fr, e.artiste, e.pays_nom].filter(Boolean).join(' · ');
        document.getElementById('bib-l-leg').textContent = e.legende || '';
        dlg.showModal();
    }
    document.addEventListener('click', function (ev) {
        var b = ev.target.closest('[data-ouvre]'); if (b) ouvre(b.dataset.ouvre);
    });
    dlg.querySelector('.bib-fermer').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });
    dlg.addEventListener('close', function () { media.innerHTML = ''; });
})();
