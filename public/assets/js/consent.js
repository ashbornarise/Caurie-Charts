// Gestion du consentement aux cookies.
// Rien n'est chargé tant que le visiteur n'a pas accepté : Google Analytics, Meta Pixel et les
// clips YouTube (domaine youtube-nocookie) restent inactifs par défaut. Refuser est aussi simple
// qu'accepter, et le choix se modifie à tout moment via le lien « Gérer mes cookies ».
(function () {
    'use strict';

    var body = document.body;
    var COOKIE = 'cauri_consent';
    var gaId = body.getAttribute('data-ga') || '';
    var pixelId = body.getAttribute('data-pixel') || '';
    var months = parseInt(body.getAttribute('data-consent-months') || '6', 10);
    var banner = document.getElementById('consent');

    function read() {
        var m = document.cookie.match(/(?:^|;\s*)cauri_consent=([^;]+)/);
        if (!m) { return null; }
        try { return JSON.parse(decodeURIComponent(m[1])); } catch (e) { return null; }
    }

    function write(choice) {
        choice.v = 1;
        choice.ts = new Date().toISOString().slice(0, 10);
        var secure = location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = COOKIE + '=' + encodeURIComponent(JSON.stringify(choice)) +
            '; Max-Age=' + (months * 30 * 86400) + '; Path=/; SameSite=Lax' + secure;
    }

    // Supprime les cookies déposés par les outils quand le visiteur retire son accord
    function purge(prefixes) {
        var host = location.hostname;
        var domains = ['', host, '.' + host, '.' + host.split('.').slice(-2).join('.')];
        document.cookie.split(';').forEach(function (c) {
            var name = c.split('=')[0].trim();
            prefixes.forEach(function (p) {
                if (name.indexOf(p) === 0) {
                    domains.forEach(function (d) {
                        document.cookie = name + '=; Max-Age=0; Path=/' + (d ? '; Domain=' + d : '');
                    });
                }
            });
        });
    }

    function loadScript(src) {
        var s = document.createElement('script');
        s.async = true;
        s.src = src;
        document.head.appendChild(s);
    }

    function loadAnalytics() {
        if (!gaId || window.__cauriGa) { return; }
        window.__cauriGa = true;
        window.dataLayer = window.dataLayer || [];
        window.gtag = function () { window.dataLayer.push(arguments); };
        window.gtag('js', new Date());
        window.gtag('config', gaId, { anonymize_ip: true });
        loadScript('https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(gaId));
    }

    function loadPixel() {
        if (!pixelId || window.fbq) { return; }
        var fbq = window.fbq = function () {
            fbq.callMethod ? fbq.callMethod.apply(fbq, arguments) : fbq.queue.push(arguments);
        };
        window._fbq = fbq;
        fbq.push = fbq;
        fbq.loaded = true;
        fbq.version = '2.0';
        fbq.queue = [];
        loadScript('https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', pixelId);
        fbq('track', 'PageView');
    }

    // Clips YouTube : une image et un bouton ; le lecteur ne se charge qu'au clic (ou si déjà autorisé)
    function playVideo(box) {
        var id = box.getAttribute('data-yt-id');
        if (!/^[A-Za-z0-9_-]{6,20}$/.test(id)) { return; }
        var frame = document.createElement('iframe');
        frame.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0';
        frame.title = box.getAttribute('data-yt-title') || 'YouTube';
        frame.allow = 'accelerometer; autoplay; encrypted-media; picture-in-picture';
        frame.allowFullscreen = true;
        frame.loading = 'lazy';
        box.innerHTML = '';
        box.appendChild(frame);
        box.classList.add('video--playing');
    }

    // Lecteur Spotify (playlist) : même principe, rien n'est chargé depuis Spotify avant le clic ou l'accord
    function playSpotify(box) {
        var id = box.getAttribute('data-spotify-playlist');
        if (!/^[A-Za-z0-9]{10,40}$/.test(id)) { return; }
        var frame = document.createElement('iframe');
        frame.src = 'https://open.spotify.com/embed/playlist/' + id + '?utm_source=generator&theme=0';
        frame.title = box.getAttribute('data-spotify-title') || 'Spotify';
        frame.allow = 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture';
        frame.loading = 'lazy';
        box.innerHTML = '';
        box.appendChild(frame);
        box.classList.add('spotify--playing');
    }

    function apply(choice) {
        if (choice.analytics) { loadAnalytics(); }
        if (choice.ads) { loadPixel(); }
        if (choice.media) {
            document.querySelectorAll('[data-yt-id]').forEach(playVideo);
            document.querySelectorAll('[data-spotify-playlist]').forEach(playSpotify);
        }
    }

    function syncForm(choice) {
        if (!banner) { return; }
        ['analytics', 'ads', 'media'].forEach(function (k) {
            var box = banner.querySelector('input[name="' + k + '"]');
            if (box) { box.checked = !!(choice && choice[k]); }
        });
    }

    function decide(choice) {
        var previous = read();
        write(choice);
        if (banner) { banner.hidden = true; }
        // Retrait d'un accord : on efface les cookies déjà déposés et on recharge sans les outils
        var withdrawn = previous && ((previous.analytics && !choice.analytics) || (previous.ads && !choice.ads));
        if (withdrawn) {
            if (!choice.analytics) { purge(['_ga', '_gid']); }
            if (!choice.ads) { purge(['_fbp', '_fbc']); }
            location.reload();
            return;
        }
        apply(choice);
    }

    document.querySelectorAll('[data-spotify-play]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            playSpotify(btn.closest('[data-spotify-playlist]'));
        });
    });

    document.querySelectorAll('[data-yt-play]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            playVideo(btn.closest('[data-yt-id]'));
        });
    });

    var choice = read();
    if (choice) {
        apply(choice);
    }

    if (!banner) { return; }

    banner.querySelector('[data-consent-accept]').addEventListener('click', function () {
        decide({ analytics: true, ads: true, media: true });
    });
    banner.querySelector('[data-consent-refuse]').addEventListener('click', function () {
        decide({ analytics: false, ads: false, media: false });
    });
    banner.querySelector('[data-consent-custom]').addEventListener('click', function () {
        var panel = banner.querySelector('[data-consent-panel]');
        panel.hidden = !panel.hidden;
        this.setAttribute('aria-expanded', String(!panel.hidden));
    });
    banner.querySelector('[data-consent-save]').addEventListener('click', function () {
        var get = function (k) { var b = banner.querySelector('input[name="' + k + '"]'); return !!(b && b.checked); };
        decide({ analytics: get('analytics'), ads: get('ads'), media: get('media') });
    });
    document.querySelectorAll('[data-consent-open]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            syncForm(read());
            banner.hidden = false;
            banner.querySelector('[data-consent-panel]').hidden = false;
            banner.querySelector('[data-consent-refuse]').focus();
        });
    });

    if (!choice) {
        banner.hidden = false;
    }
})();
