// Cauri Charts Monthly Show (v2) : lecteur de l'émission (page /show en direct, /show/repetition, /show/antenne pour OBS).
// Conducteur : /show/programme.json. Tout le monde est calé sur la même horloge (data-start, UTC) : chaque clip et chaque
// clip est repositionné sur le temps du show. Clips : lecteur YouTube officiel intégré (non modifié, rien par-dessus, aucun
// autre son pendant un clip). Musique : uniquement les clips officiels, en entier, dans un lecteur visible : à l'appel de
// chaque nom et dans le « juke-box » d'ambiance (titres de chaque pays). Fonds Mixkit en secours (vitesse > ×2), bruitages Mixkit. Pas de style en ligne dans le HTML (CSP) : valeurs via element.style.
(function () {
  'use strict';
  var root = document.getElementById('sp');
  if (!root) return;
  var FL = root.dataset.flags, rehearsal = root.dataset.rehearsal === '1';
  var S = { speed: parseFloat(root.dataset.speed || '1'), adj: parseFloat(root.dataset.jump || '0'), paused: null,
            idx: -2, sub: null, sound: false, prog: null, icons: {}, revealed: {} };
  S.start = root.dataset.start === 'now' ? Date.now() + 8000 : Date.parse(root.dataset.start);
  var CLIP_DEBUT = 20;     // on entre dans le clip à 20 s (après les intros)
  var APPEL = 3;           // secondes d'appel (nom à l'écran, voix) avant que le clip parte

  // ------------------------------------------------------------------ outils
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ico(n, size) {
    return '<svg class="sp-i" width="' + (size || 24) + '" height="' + (size || 24) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (S.icons[n] || '') + '</svg>';
  }
  function flag(code, cls) { return code === 'WA' ? '<span class="sp-flag sp-flag--wa ' + (cls || '') + '"></span>' : '<img class="sp-flag ' + (cls || '') + '" src="' + FL + code.toLowerCase() + '.svg" alt="">'; }
  function img(url, cls) { return url ? '<img class="' + cls + '" src="' + esc(url) + '" alt="" referrerpolicy="no-referrer">' : '<span class="' + cls + ' sp-vide"></span>'; }
  function delays(el) { el.querySelectorAll('[data-d]').forEach(function (x) { x.style.animationDelay = x.dataset.d + 's'; }); }
  function now() { return S.paused !== null ? S.paused : (Date.now() - S.start) / 1000 * S.speed + S.adj; }
  function fmt(x) { x = Math.max(0, Math.floor(x)); return Math.floor(x / 60) + ':' + String(x % 60).padStart(2, '0'); }

  // ------------------------------------------------------------------ musique : deux voies en fondu enchaîné (jamais de coupure sèche)
  var SONS = (root.dataset.assets || '/assets/show/') + 'sons/', FONDU = .9;
  function voie() { var a = new Audio(); a.preload = 'auto'; a._cible = 0; a.volume = 0; return a; }
  var voies = [voie(), voie()], ac = 0, acSrc = null, credit = null;
  function joue(src, pos, vol, boucle, info) {
    if (!src) { silence(); return; }
    var on = S.sound && S.paused === null;
    if (src !== acSrc) {
      var n = voies[1 - ac]; voies[ac]._cible = 0;
      n.loop = !!boucle; n.src = src; n._pos = pos || 0; n.volume = 0; n._cible = on ? vol : 0;
      n.addEventListener('loadedmetadata', function () { try { if (n._pos) n.currentTime = n._pos; } catch (e) { /* pas encore prêt */ } }, { once: true });
      if (on) n.play().catch(function () {});
      ac = 1 - ac; acSrc = src; montreCredit(info);
    } else {
      var a = voies[ac]; a._cible = on ? vol : 0;
      if (on && a.paused) a.play().catch(function () {});
      if (!boucle && pos != null && a.readyState > 1 && Math.abs(a.currentTime - pos) > 4) { try { a.currentTime = pos; } catch (e) {} }
    }
  }
  function silence() { voies.forEach(function (v) { v._cible = 0; }); montreCredit(null); }
  function pasAudio(dt) {
    voies.forEach(function (v) {
      var d = v._cible - v.volume, st = dt / FONDU;
      v.volume = Math.max(0, Math.min(1, v.volume + Math.sign(d) * Math.min(Math.abs(d), st)));
      if (v.volume < .005 && v._cible === 0 && !v.paused) v.pause();
    });
  }
  // vrai titre : son clip officiel dans la zone visible du segment (juke-box ou écran) ; secours : fond Mixkit
  function titre(e, t, el, reste) {
    var zone = el && (el.querySelector('.sp-juke') || el.querySelector('.sp-ecran'));
    if (e && e.youtube && zone && S.speed <= 2 && clip(e.youtube, t, zone, reste)) { silence(); montreCredit(e); return; }
    clipStop(); lit('rythme', .5); montreCredit(null);
  }
  function lit(nom, vol) { joue(SONS + 'lit-' + nom + '.mp3', null, vol, true, null); }
  function fond(seg, t, el) { titre(seg && seg.fond, t, el, seg ? seg.d - t : null); }   // ambiance : clip d'un titre du pays
  function sfx(nom, vol) {
    if (!S.sound || S.speed > 2 || S.paused !== null) return;
    var a = new Audio(SONS + nom + '.mp3'); a.volume = vol == null ? .6 : vol; a.play().catch(function () {});
  }

  // pas de voix off : l'émission parle par la musique, les clips et l'habillage (décision du 10 oct. 2026)

  // ------------------------------------------------------------------ plateau : boucles de vrai concert selon l'ambiance
  var PLATEAU = (root.dataset.assets || '/assets/show/') + 'plateau/';
  var BOUCLE = { avant: 'veille', fin: 'veille', generique: 'clip', ambiance: 'ambiance', enjeu: 'ambiance2', clip: 'clip', duel: 'ambiance2',
    silence: 'veille2', numero1: 'revelation', flash: 'revelation2', prix: 'revelation2', tubes: 'pause', sondage: 'pause', supporters: 'pause2',
    bientot: 'veille2', tableau: 'pause2', big5: 'clip', cloture: 'veille' };
  var pvs = [], pAc = 0, pSrc = null;
  function plateau(type) {
    var nom = BOUCLE[type] || 'clip';
    if (nom === pSrc) return;
    var n = pvs[1 - pAc], o = pvs[pAc];
    n.src = PLATEAU + nom + '.mp4'; n.play().catch(function () {}); n.classList.add('on'); o.classList.remove('on');
    var d = root.querySelector('.sp-decor'); if (d) { d.src = n.src; d.play().catch(function () {}); }
    // changement d'ambiance bien visible : coup de lumière blanche sur le plateau
    if (pSrc) { scene.classList.remove('sp-bascule'); void scene.offsetWidth; scene.classList.add('sp-bascule'); }
    setTimeout(function () { if (!o.classList.contains('on')) o.pause(); }, 1200);
    pAc = 1 - pAc; pSrc = nom;
  }
  // tempo : les lumières pulsent à 120 BPM, ou sur l'énergie réelle du son quand le clip est un fichier (analyse audio)
  var actx = null, analyseurs = [], niveau = 0;
  function analyse(v) {
    try {
      if (!window.AudioContext) return;
      actx = actx || new AudioContext();
      if (v._an) return;
      var src = actx.createMediaElementSource(v), an = actx.createAnalyser(); an.fftSize = 512;
      src.connect(an); an.connect(actx.destination); v._an = an; analyseurs.push(v);
    } catch (e) { /* déjà relié ou non permis */ }
  }
  var basses = new Uint8Array(256);
  function lumiere(t) {
    var p = 0, v = vids[vAc];
    if (v && v._an && v._actif && !v.paused) {
      v._an.getByteFrequencyData(basses); var e = 0; for (var k = 1; k < 12; k++) e += basses[k]; e /= 11 * 255;
      niveau = Math.max(e, niveau * .9); p = Math.max(0, (e - .35) * 2.2);
    } else {
      var ph = (t % .5) / .5; p = Math.exp(-ph * 6);          // battement à 120 BPM
    }
    scene.style.setProperty('--pulse', p.toFixed(3));
  }
  function dj(nom, vol) { sfx(nom, vol == null ? .55 : vol); }

  // ------------------------------------------------------------------ clips en fichier (fournis par les artistes, régie seulement)
  var vids = [], vAc = 0, vSrc = null;
  function locale(id) { return S.prog && S.prog.clips_locaux && S.prog.clips_locaux[id]; }
  function video(url, pos, reste) {
    var on = S.paused === null;
    if (url !== vSrc) {
      var n = vids[1 - vAc], o = vids[vAc]; o._actif = false; o.classList.remove('on');
      n._actif = true; n.src = url; n.muted = !S.sound; n.volume = 0; n._cible = 1;
      n.addEventListener('loadedmetadata', function () { try { n.currentTime = CLIP_DEBUT + pos; } catch (e) {} }, { once: true });
      if (on) n.play().catch(function () {});
      n.classList.add('on'); vAc = 1 - vAc; vSrc = url;
    }
    var v = vids[vAc]; v.muted = !S.sound;
    v._cible = Math.min(1, pos / 1.2, (reste == null ? 9 : reste) / 1.8);
    if (!on) { if (!v.paused) v.pause(); }
    else {
      if (v.paused) v.play().catch(function () {});
      if (v.readyState > 1 && Math.abs(v.currentTime - (CLIP_DEBUT + pos)) > 4) { try { v.currentTime = CLIP_DEBUT + pos; } catch (e) {} }
    }
    scene.classList.add('sp-plein');
    return true;
  }
  function videoStop() { vids.forEach(function (v) { v._actif = false; v._cible = 0; v.classList.remove('on'); }); vSrc = null; scene.classList.remove('sp-plein'); }
  function pasVideo(dt) {
    vids.forEach(function (v) {
      var d = (v._cible || 0) - v.volume; v.volume = Math.max(0, Math.min(1, v.volume + Math.sign(d) * Math.min(Math.abs(d), dt / .9)));
      if (!v._actif && v.volume < .01 && !v.paused) v.pause();
    });
  }

  // ------------------------------------------------------------------ clips : lecteur YouTube officiel
  var yt = null, ytReady = false, ytWant = null, ytHost = null;
  function ytLoad() {
    if (window.YT && window.YT.Player) return ytInit();
    var s = document.createElement('script'); s.src = 'https://www.youtube.com/iframe_api'; document.head.appendChild(s);
    window.onYouTubeIframeAPIReady = ytInit;
  }
  function ytInit() {
    ytHost = document.createElement('div'); ytHost.className = 'sp-yt off';
    var inner = document.createElement('div'); inner.id = 'sp-yt-player'; ytHost.appendChild(inner); scene.appendChild(ytHost);
    yt = new YT.Player('sp-yt-player', { width: 1080, height: 608,
      playerVars: { autoplay: 1, controls: 0, rel: 0, playsinline: 1, modestbranding: 1, mute: 1, origin: location.origin, enablejsapi: 1 },
      events: { onReady: function () { ytReady = true; }, onError: function (ev) { if (ytWant) { ytWant.erreur = true; ytWant.code = ev && ev.data; } } } });
  }
  // place le lecteur sur la zone prévue et le cale sur le temps du show ; volume qui monte et descend en douceur
  var ytVol = 0;
  function clip(id, pos, zone, reste) {
    if (id && locale(id)) { if (ytHost && !ytHost.classList.contains('off')) { ytHost.classList.add('off'); try { yt.pauseVideo(); } catch (e) {} } return video(locale(id), pos, reste); }
    videoStop();
    if (!yt || !ytReady || !id) return false;
    if (!ytWant || ytWant.id !== id) { ytWant = { id: id, t0: Date.now() }; ytVol = 0; yt.loadVideoById({ videoId: id, startSeconds: CLIP_DEBUT + pos }); }
    if (ytWant.erreur) return false;
    if (zone && zone._poster !== id) {
      zone._poster = id; zone.classList.add('sp-poster');
      zone.style.backgroundImage = 'url(https://i.ytimg.com/vi/' + id + '/hqdefault.jpg)';
    }
    var joue = false; try { joue = yt.getPlayerState() === 1 && yt.getCurrentTime() > 0; } catch (e) {}
    ytHost.classList.toggle('off', !joue);
    var r = zone.getBoundingClientRect(), s = scene.getBoundingClientRect(), k = s.width / 1080;
    var lw = r.width / k, lh = r.height / k;
    ytHost.style.left = (lw >= 1000 ? 0 : (r.left - s.left) / k) + 'px'; ytHost.style.top = (r.top - s.top) / k + 'px';
    ytHost.style.width = (lw >= 1000 ? 1080 : lw) + 'px'; ytHost.style.height = (lw >= 1000 ? 608 : lh) + 'px';
    try {
      var cible = !S.sound ? 0 : 95 * Math.min(1, pos / 1.2, (reste == null ? 9 : reste) / 1.8);
      ytVol += (cible - ytVol) * .2;
      if (S.sound) { if (yt.isMuted()) yt.unMute(); yt.setVolume(Math.round(ytVol)); } else if (!yt.isMuted()) yt.mute();
      var etat = yt.getPlayerState();
      if (S.paused !== null) { if (etat === 1) yt.pauseVideo(); }
      else {
        // on ne recale que si l'écart est grand et que la vidéo joue vraiment (pas pendant la mise en mémoire)
        if (etat === 1 && Date.now() - ytWant.t0 > 4000 && Math.abs(yt.getCurrentTime() - (CLIP_DEBUT + pos)) > 6) yt.seekTo(CLIP_DEBUT + pos, true);
        if (etat === 2 || etat === 5 || etat === -1) yt.playVideo();
      }
    } catch (e) { /* lecteur pas prêt */ }
    return true;
  }
  function clipStop() { if (ytHost && !ytHost.classList.contains('off')) { ytHost.classList.add('off'); try { yt.pauseVideo(); } catch (e) {} } ytWant = null; videoStop(); }
  // préchargement : pendant un segment sans clip, on prépare le prochain clip YouTube (démarrage instantané)
  function precharge(i) {
    if (!yt || !ytReady || ytWant || !S.prog) return;
    var n = S.prog.segments.slice(i + 1, i + 3).map(function (x) { return x.youtube || (x.fond && x.fond.youtube); }).filter(Boolean)[0];
    if (n && !locale(n) && S.cue !== n) { S.cue = n; try { yt.cueVideoById({ videoId: n, startSeconds: CLIP_DEBUT }); } catch (e) {} }
  }

  // ------------------------------------------------------------------ scène
  root.innerHTML = '<video class="sp-decor" muted loop playsinline preload="auto"></video><div class="sp-scene"><div class="sp-fond"><video class="sp-pv" muted loop playsinline preload="auto"></video>' +
    '<video class="sp-pv" muted loop playsinline preload="auto"></video><div class="sp-teinte"></div><div class="sp-truss"></div>' +
    '<i></i><i></i><i></i><i></i><i></i><div class="sp-brume"></div><div class="sp-strobe"></div></div>' +
    '<div class="sp-videos"><video class="sp-v" playsinline preload="auto"></video><video class="sp-v" playsinline preload="auto"></video></div>' +
    '<div class="sp-voile"></div><div class="sp-content"></div>' +
    '<div class="sp-bug"><span class="sp-mono"></span><span>CAURI CHARTS<b>MONTHLY SHOW</b></span></div>' +
    '<div class="sp-live"><i></i>' + (rehearsal ? 'RÉPÉTITION' : 'EN DIRECT') + '</div>' +
    '<div class="sp-ticker"><span class="sp-ticker__txt"></span></div><div class="sp-flash"></div></div>' +
    '<button class="sp-son" type="button">Regarder avec le son</button>';
  var scene = root.querySelector('.sp-scene'), content = root.querySelector('.sp-content');
  vids = Array.prototype.slice.call(root.querySelectorAll('.sp-v')); vids.forEach(function (v) { v._cible = 0; v.volume = 0; });
  pvs = Array.prototype.slice.call(root.querySelectorAll('.sp-pv'));
  var flashEl = root.querySelector('.sp-flash'), ticker = root.querySelector('.sp-ticker__txt');
  function fit() {
    var k = Math.min(root.clientWidth / 1080, root.clientHeight / 1920);
    scene.style.transform = 'scale(' + k + ')'; scene.style.left = ((root.clientWidth - 1080 * k) / 2) + 'px';
  }
  window.addEventListener('resize', fit); fit();
  var btn = root.querySelector('.sp-son');
  btn.addEventListener('click', function () {
    S.sound = true; btn.hidden = true;
    // sur téléphone, le son ne se débloque que dans le geste lui-même : on réveille les lecteurs ici
    try { if (yt && ytReady) { yt.unMute(); yt.playVideo(); } } catch (e) {}
    vids.forEach(function (v) { v.muted = false; analyse(v); v.play().then(function () { if (!v._actif) v.pause(); }).catch(function () {}); });
    if (actx && actx.state === 'suspended') actx.resume();
  });
  var creditEl = document.createElement('div'); creditEl.className = 'sp-credit'; creditEl.hidden = true; scene.appendChild(creditEl);
  function montreCredit(info) {
    if (!info || !info.artiste) { creditEl.hidden = true; return; }
    creditEl.innerHTML = ico('volume', 30) + '<span><b>' + esc(info.titre) + '</b> · ' + esc(info.artiste) + (info.pays ? ' · ' + esc(info.pays) : '') + '</span>';
    creditEl.hidden = false;
  }
  function flash() { flashEl.classList.remove('on'); void flashEl.offsetWidth; flashEl.classList.add('on'); }
  function revele(seg) { S.revealed[seg.code + (seg.big5 ? '5' : '')] = (seg.code === 'WA' ? 'AFRIQUE DE L’OUEST' : seg.nom.toUpperCase()) + ' · N°1 ' + seg.artiste; majTicker(); }
  function majTicker() {
    var v = Object.keys(S.revealed).map(function (k) { return S.revealed[k]; });
    var txt = v.length ? v.join('     ◆     ') : 'Les N°1 de la soirée s’affichent ici au fil des révélations     ◆     cauricharts.com';
    if (ticker.textContent !== txt) ticker.textContent = txt;
  }
  function tete(seg, droite) {
    return '<div class="sp-head in-up">' + flag(seg.code, 'sp-flag--l') + '<b>' + esc(seg.code === 'WA' ? 'BIG 5' : seg.nom.toUpperCase()) + '</b>' +
      (droite ? '<span>' + droite + '</span>' : '') + '</div>';
  }

  // ------------------------------------------------------------------ segments : rendu (R.x) et suivi image par image (R.x.tick)
  var R = {};
  R.avant = function (el) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">' + (rehearsal ? 'RÉPÉTITION GÉNÉRALE' : 'LE SHOW COMMENCE DANS') + '</p>' +
      '<div class="sp-cd in-pop" data-d=".1">--:--</div><p class="sp-t2 in-up" data-d=".3">' + esc(S.prog.mois) + ' · ' + S.prog.scenes.length + ' scènes · 1 BIG 5</p>' +
      '<div class="sp-card sp-hint in-up" data-d=".5">' + ico('volume', 44) + '<span>Activez le son : chaque classement commence par la musique.</span></div></div>';
  };
  R.avant.tick = function (el, t) {
    var s = Math.max(0, Math.ceil(-t)); el.querySelector('.sp-cd').textContent = fmt(s);
    var liste = (S.prog.avant || []).filter(Boolean), k = Math.floor((t + 3600) / 90);
    titre(liste.length ? liste[k % liste.length] : null, (t + 3600) % 90, el, 90 - (t + 3600) % 90);
  };

  R.ambiance = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center sp-amb"><p class="sp-k in-up">SCÈNE ' + s.numero + ' · ' + esc(s.nom.toUpperCase()) + '</p>' +
      '<p class="sp-h1 in-zoom" data-d=".4">ÉCOUTEZ…</p><div class="sp-covers">' + s.extraits.map(function (x, i) {
        return '<div class="sp-cover in-pop" data-d="' + (.8 + i * .15) + '">' + img(x.pochette, 'sp-cover__img') + '<span>' + (i + 1) + '</span></div>'; }).join('') +
      '</div><div class="sp-onde">' + new Array(40).join('<i></i>') + '</div>' +
      '<p class="sp-t2 in-up" data-d="1.4">' + (s.format === 'blind_test' ? 'Devinez l’ordre du Top 5 en commentaire' : 'Reconnaissez-vous les titres ? Les noms arrivent…') + '</p></div>';
    el.querySelectorAll('.sp-onde i').forEach(function (b, i) { b.style.animationDelay = (-(i * 97) % 900) / 1000 + 's'; });
  };
  R.ambiance.tick = function (el, t, s) {
    var n = s.extraits.length, part = (s.d - 3) / n, i = Math.min(n - 1, Math.floor(Math.max(0, t - 2) / part));
    fond(s, t, el);
    if (S.sub !== i) { S.sub = i; el.querySelectorAll('.sp-cover').forEach(function (c, j) { c.classList.toggle('on', j === i); }); }
  };

  R.enjeu = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center">' + tete(s) + '<p class="sp-label in-up" data-d=".3">' + esc(s.label) + '</p>' +
      '<p class="sp-chiffre grad in-zoom" data-d=".6">' + esc(s.chiffre) + '</p><p class="sp-t2 in-up" data-d="1.2">' + esc(s.texte) + '</p></div>';
    flash(); sfx('impact-logo', .7);
  };
  R.enjeu.tick = function (el, t, s) { fond(s, t, el); };

  R.clip = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-clipcol">' + tete(s, s.big5 ? 'AFRIQUE DE L’OUEST' : 'TOP 5') +
      '<div class="sp-rang grad in-zoom">#' + s.rang + '</div>' +
      '<div class="sp-ecran in-up" data-d=".2">' + img(s.photo, 'sp-ecran__photo') + '</div>' +
      '<p class="sp-artist in-up" data-d=".3">' + esc(s.artiste) + '</p><p class="sp-title in-up" data-d=".45">' + esc(s.titre) + '</p>' +
      '<p class="sp-meta in-up" data-d=".6">' + ico('play', 22) + 'Clip officiel · YouTube' + (s.sources ? ' · classé sur ' + s.sources + ' source' + (s.sources > 1 ? 's' : '') : '') + '</p></div>';
  };
  R.clip.tick = function (el, t, s) {
    var zone = el.querySelector('.sp-ecran');
    if (t < APPEL) { clipStop(); montreCredit(null); lit('tension', .35); return; }
    if (S.speed > 2 || !clip(s.youtube, t - APPEL, zone, s.d - t)) { clipStop(); lit('rythme', .5); } else silence();
  };

  R.duel = function (el, s) {
    var tot = (s.duel[0].points + s.duel[1].points) || 1;
    el.innerHTML = '<div class="sp-col sp-center">' + tete(s, 'PHOTO-FINISH') + '<p class="sp-h2 in-up" data-d=".2">IL RESTE <span class="grad">DEUX NOMS</span></p>' +
      '<div class="sp-duel">' + s.duel.map(function (e, i) {
        return '<div class="sp-card sp-duel__c in-' + (i ? 'right' : 'left') + '" data-d=".5">' + img(e.photo, 'sp-photo') + '<b>' + esc(e.artiste) + '</b><span>' + esc(e.titre) + '</span>' +
          '<div class="sp-jauge"><i data-p="' + Math.round(e.points / tot * 100) + '"></i></div></div>'; }).join('') + '</div>' +
      '<p class="sp-t2 in-up" data-d="1.2">' + s.ecart + ' % d’écart · votez sur cauricharts.com/show/vote</p><p class="sp-tendance">Le vote est un pronostic : le classement vient des données.</p><div class="sp-bar"><i></i></div></div>';
  };
  R.duel.tick = function (el, t, s) {
    var v = S.votes['duel-' + String(s.code).toLowerCase()], tend = el.querySelector('.sp-tendance');
    if (v && tend) tend.textContent = v.statut === 'scelle' ? 'Vote du public : résultat sous scellé' : (v.total_suffisant ?
      'Vote du public : ' + v.options.map(function (o) { return o.label + ' ' + o.pct + ' %'; }).join(' · ') : 'Vote du public : le vote chauffe…');
    el.querySelectorAll('.sp-jauge i').forEach(function (j, i) { j.style.width = (Math.min(1, t / 3) * (+j.dataset.p + (i ? -1 : 1) * 4 * Math.sin(t * 1.3))) + '%'; });
    el.querySelector('.sp-bar i').style.width = Math.max(0, 100 - t / s.d * 100) + '%';
    var i = Math.floor(t / 15) % 2; titre(s.duel[i], t % 15, el, 15 - t % 15);
  };

  R.silence = function (el) { el.innerHTML = '<div class="sp-col sp-center"><div class="sp-dots"><i></i><i></i><i></i></div></div>'; scene.classList.add('sp-noir'); silence(); sfx('coeur-un-battement', .9); };
  R.silence.tick = function () { silence(); clipStop(); };

  R.numero1 = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-clipcol">' + tete(s, 'N°1') +
      '<div class="sp-rang sp-rang--1 grad in-zoom">#1</div><div class="sp-ecran in-pop" data-d=".2">' + img(s.photo, 'sp-ecran__photo') + '</div>' +
      '<p class="sp-artist sp-artist--l in-up" data-d=".5">' + esc(s.artiste) + '</p><p class="sp-title in-up" data-d=".7">' + esc(s.titre) + '</p>' +
      '<div class="sp-rings"><i></i><i></i><i></i></div></div>' +
      '<div class="sp-distinction" hidden><div class="sp-dist__carte">' +
        '<div class="sp-dist__haut"><span class="sp-mono"></span><span>CAURI CHARTS<b>DISTINCTION OFFICIELLE</b></span></div>' +
        '<div class="sp-dist__photo">' + img(s.photo, 'sp-dist__img') + '<span class="sp-dist__n1">N°1</span></div>' +
        '<p class="sp-dist__artiste">' + esc(s.artiste) + '</p><p class="sp-dist__titre">' + esc(s.titre) + '</p>' +
        '<p class="sp-dist__classement">' + esc((s.big5 ? 'Top 20 · Afrique de l’Ouest' : 'Top 5 · ' + s.nom) + ' · ' + s.mois) + '</p>' +
        '<p class="sp-dist__ref">la référence de la musique ouest-africaine</p></div></div>';
    flash(); revele(s); sfx('impact-trailer', .8); sfx('foule-victoire', .35);
  };
  R.numero1.tick = function (el, t, s) {
    var zone = el.querySelector('.sp-ecran');
    if (t < s.revel) { silence(); clipStop(); return; }
    if (t < s.revel + s.clip) {
      if (S.speed > 2 || !clip(s.youtube, t - s.revel, zone, s.revel + s.clip - t)) { clipStop(); lit('rythme', .55); } else silence();
      return;
    }
    clipStop(); lit('veille', .45);
    var m = el.querySelector('.sp-distinction'); if (m.hidden) { m.hidden = false; el.querySelector('.sp-clipcol').classList.add('sp-cache'); sfx('applaudissements', .35); }
  };

  R.generique = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><span class="sp-logo in-zoom"></span><h1 class="sp-h1 in-up" data-d=".8">THE <span class="grad">MONTHLY SHOW</span></h1>' +
      '<p class="sp-t2 in-up" data-d="1.4">' + esc(s.mois) + ' · ' + s.pays + ' pays · 1 BIG 5</p><p class="sp-tag in-up" data-d="2">la référence de la musique ouest-africaine</p></div>';
    flash(); sfx('impact-trailer', .7);
  };
  R.generique.tick = function (el, t, s) { fond(s, t, el); };

  R.tubes = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">RUBRIQUE</p><p class="sp-h2 in-up" data-d=".2">LES TUBES <span class="grad">DE DEMAIN</span></p>' +
      '<p class="sp-t2 in-up" data-d=".4">Les plus fortes progressions du mois · Buzz Chart</p><div class="sp-tubes">' + s.titres.map(function (e, i) {
        return '<div class="sp-card sp-tube in-right" data-d="' + (.6 + i * .2) + '">' + img(e.pochette, 'sp-tube__img') + '<div><b>' + esc(e.artiste) + '</b><span>' + esc(e.titre) + '</span></div>' + ico('trending-up', 40) + '</div>'; }).join('') + '</div></div>';
  };
  R.tubes.tick = function (el, t, s) {
    var i = Math.min(s.titres.length - 1, Math.floor(t / s.par));
    titre(s.titres[i], t % s.par, el, s.par - t % s.par);
    if (S.sub !== i) { S.sub = i; el.querySelectorAll('.sp-tube').forEach(function (c, j) { c.classList.toggle('on', j === i); }); }
  };

  R.sondage = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><span class="sp-ico sp-ico--l in-pop">' + ico('message', 110) + '</span>' +
      '<p class="sp-h2 in-up" data-d=".3">À VOUS DE <span class="grad">JOUER</span></p><p class="sp-t2 in-up" data-d=".5">Quel pays attendez-vous ? Répondez en commentaire.</p><div class="sp-bar"><i></i></div></div>';
  };
  R.sondage.tick = function (el, t, s) { el.querySelector('.sp-bar i').style.width = Math.max(0, 100 - t / s.d * 100) + '%'; fond(s, t, el); };

  R.supporters = function (el) {
    el.innerHTML = '<div class="sp-col sp-center"><div class="sp-card sp-notif in-down">' + ico('gift', 52) + '<span>Un supporter envoie un cadeau…</span></div>' +
      '<p class="sp-h1 grad in-zoom" data-d="1.2">CAURI VIP<br>MOMENT</p>' +
      '<div class="sp-card sp-vip in-up" data-d="1.8"><span class="sp-avatar">' + ico('star', 70) + '</span><div><b>TON NOM ICI</b><span>Envoie un cadeau pendant le live</span></div></div>' +
      (rehearsal ? '<p class="sp-note">Répétition : les vrais supporters s’afficheront ici quand le module des cadeaux sera branché.</p>' : '') + '</div>';
  };
  R.supporters.tick = function (el, t, s) { fond(s, t, el); };

  R.flash = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">LE FLASH · LES AUTRES N°1</p>' + flag(s.code, 'sp-flag--xl in-pop') +
      '<p class="sp-h2 in-up" data-d=".2">' + esc(s.nom.toUpperCase()) + '</p>' + img(s.photo, 'sp-photo sp-photo--l in-pop') +
      '<p class="sp-artist in-up" data-d=".5">' + esc(s.artiste) + '</p><p class="sp-title in-up" data-d=".6">' + esc(s.titre) + '</p></div>';
    revele(s); sfx('whoosh-rapide', .6);
  };
  R.flash.tick = function (el, t, s) { titre(s, t, el, s.d - t); };

  R.bientot = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">BIENTÔT CLASSÉS</p><p class="sp-t2 in-up" data-d=".2">Pas encore assez de données pour classer :</p>' +
      '<div class="sp-chips">' + s.pays.map(function (p, i) { return '<span class="sp-chip in-pop" data-d="' + (.3 + i * .1) + '">' + esc(p) + '</span>'; }).join('') + '</div>' +
      '<p class="sp-t2 in-up" data-d="1">Artistes et labels : déclarez votre musique sur cauricharts.com</p></div>';
  };
  R.bientot.tick = function (el, t, s) { fond(s, t, el); };

  R.tableau = function (el) {
    el.innerHTML = '<div class="sp-col"><p class="sp-k in-up">LE TABLEAU DE LA SOIRÉE</p><p class="sp-h2 in-up" data-d=".2">LES N°1 <span class="grad">RÉVÉLÉS</span></p>' +
      '<div class="sp-card sp-tab">' + S.prog.n1.map(function (p, i) {
        var ok = S.revealed[p.code];
        return '<div class="sp-tab__l in-right' + (ok ? '' : ' sp-tab__l--off') + '" data-d="' + (.3 + i * .08) + '">' + flag(p.code) + '<b>' + esc(p.nom) + '</b><span>' + (ok ? esc(p.artiste) : 'à venir') + '</span></div>'; }).join('') + '</div></div>';
  };
  R.tableau.tick = function (el, t, s) { fond(s, t, el); };

  var PRIX_ICO = { 'BIGGEST CLIMBER': 'trending-up', 'FRESH OF THE MONTH': 'sparkles', 'ARTIST OF THE MONTH': 'star', 'LEGEND': 'landmark' };
  R.prix = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">PRIX SPÉCIAL</p><span class="sp-ico sp-ico--l in-pop">' + ico(PRIX_ICO[s.nom] || 'award', 110) + '</span>' +
      '<p class="sp-h2 grad in-up" data-d=".3">' + esc(s.nom) + '</p><p class="sp-t2 in-up" data-d=".5">' + esc(s.explication) + '</p>' +
      img(s.photo, 'sp-photo sp-photo--l in-pop" data-d="1.4') + '<p class="sp-artist in-up" data-d="1.7">' + esc(s.artiste) + '</p><p class="sp-title in-up" data-d="1.9">' + esc(s.titre) + '</p></div>';
  };
  R.prix.tick = function (el, t, s) { if (t < 1.4) { clipStop(); lit('tension', .4); } else titre(s, t - 1.4, el, s.d - t); };

  R.big5 = function (el, s) {
    el.innerHTML = '<div class="sp-col sp-center"><p class="sp-k in-up">LE GRAND MOMENT</p><div class="sp-big5 grad in-zoom" data-d=".3">BIG 5</div>' +
      '<p class="sp-t2 in-up" data-d=".8">AFRIQUE DE L’OUEST · ' + esc(s.mois.toUpperCase()) + '</p></div>';
    flash(); sfx('montee-trailer', .6);
  };
  R.big5.tick = function (el, t, s) { fond(s, t, el); };

  R.cloture = function (el) {
    el.innerHTML = '<div class="sp-col sp-center"><span class="sp-logo in-zoom"></span><p class="sp-h1 in-up" data-d=".6">RENDEZ-VOUS<br><span class="grad">LE MOIS PROCHAIN</span></p>' +
      '<p class="sp-tag in-up" data-d="1">la référence de la musique ouest-africaine</p><div class="sp-card sp-hint in-up" data-d="1.6">' + ico('award', 44) +
      '<span>Classements, distinctions et clips sur cauricharts.com</span></div></div>';
  };
  R.cloture.tick = function (el, t, s) { fond(s, t, el); };
  R.fin = function (el) {
    el.innerHTML = '<div class="sp-col sp-center"><span class="sp-logo in-zoom"></span><p class="sp-h2 in-up" data-d=".3">MERCI !</p><p class="sp-t2 in-up" data-d=".5">Le show est terminé. Rendez-vous le mois prochain.</p></div>';
  };
  R.fin.tick = function () { silence(); clipStop(); };

  // ------------------------------------------------------------------ boucle
  function show(i, seg) {
    S.idx = i; S.sub = null; scene.classList.remove('sp-noir'); clipStop();
    var type = seg ? seg.type : (i === -1 ? 'avant' : 'fin');
    // l'ancien segment s'efface pendant que le nouveau arrive (fondu de 0,6 s, jamais de coupe sèche)
    Array.prototype.forEach.call(content.querySelectorAll('.sp-seg:not(.sp-out)'), function (old) {
      old.classList.add('sp-out'); setTimeout(function () { if (old.parentNode) old.parentNode.removeChild(old); }, 650);
    });
    var el = document.createElement('div'); el.className = 'sp-seg sp-in sp-seg--' + type; content.appendChild(el); S.el = el;
    scene.dataset.etat = type; plateau(type);
    // effets de DJ aux charnières : on change de pays, on part en pause, on revient sur scène
    var prev = S.prevType; S.prevType = type;
    if (type === 'ambiance') dj(prev && prev !== 'generique' ? 'dj-rembobinage' : 'dj-aiguille', .5);
    else if (/^(sondage|supporters|tableau|tubes|bientot)$/.test(type) && !/^(sondage|supporters|tableau|tubes|bientot)$/.test(prev || '')) dj('dj-scratch', .5);
    else if (type === 'big5' || type === 'generique') { dj('dj-sirene', .6); }
    else if (type === 'numero1') setTimeout(function () { dj('dj-sirene', .55); }, 900);
    else if (type === 'flash') dj('dj-swipe', .5);
    (R[type] || R.fin)(el, seg || {});
    if (seg && /^(generique|tubes|sondage|supporters|flash|bientot|tableau|prix|big5)$/.test(seg.type)) hook(el, i);
    if ((seg && (seg.fond || /^(tubes|flash|prix|duel)$/.test(seg.type))) || type === 'avant') {
      el.classList.add('sp-avec-juke'); var j = document.createElement('div'); j.className = 'sp-juke'; el.appendChild(j);
    }
    delays(el);
    regie();
  }
  // prochaine révélation d'un N°1 : pour les hooks et le compte à rebours des pauses
  function prochainN1(i) {
    var segs = S.prog.segments;
    for (var k = i + 1; k < segs.length; k++) if (segs[k].type === 'numero1') return segs[k];
    return null;
  }
  function hook(el, i) {
    var n = prochainN1(i), seg = S.prog.segments[i];
    if (!n) return;
    var h = document.createElement('div'); h.className = 'sp-hook';
    h.innerHTML = '<span class="sp-hook__k">À SUIVRE</span><b class="sp-hook__t">' + (n.code === 'WA' ? 'LE N°1 DE L’AFRIQUE DE L’OUEST' : 'LE N°1 ' + esc(n.nom.toUpperCase())) +
      '</b><span class="sp-hook__cd" data-cible="' + n.t + '"></span>';
    el.appendChild(h); sfx('whoosh-rapide', .6); setTimeout(function () { sfx('impact-logo', .55); }, 250);
    var chip = document.createElement('div'); chip.className = 'sp-chip-n1';
    chip.innerHTML = flag(n.code) + '<span>' + (n.code === 'WA' ? 'N°1 AFRIQUE DE L’OUEST' : 'N°1 ' + esc(n.nom.toUpperCase())) + '</span><b data-cible="' + n.t + '"></b>';
    el.appendChild(chip);
  }
  function majHooks(t) {
    if (!S.el) return;
    S.el.querySelectorAll('[data-cible]').forEach(function (x) { var r = Math.max(0, +x.dataset.cible - t); x.textContent = 'dans ' + fmt(r); });
  }
  function rattrape(i) {
    // saut dans le temps : le ticker reprend tous les N°1 déjà révélés
    S.revealed = {};
    S.prog.segments.slice(0, Math.max(0, i)).forEach(function (s) {
      if (s.type === 'numero1' || s.type === 'flash') S.revealed[s.code + (s.big5 ? '5' : '')] = (s.code === 'WA' ? 'AFRIQUE DE L’OUEST' : s.nom.toUpperCase()) + ' · N°1 ' + s.artiste;
    });
    majTicker();
  }
  function frame() {
    var t = now(), segs = S.prog.segments, i = t < 0 ? -1 : segs.length;
    for (var k = 0; k < segs.length; k++) if (t >= segs[k].t && t < segs[k].t + segs[k].d) { i = k; break; }
    if (i !== S.idx) { if (i !== S.idx + 1) rattrape(i); show(i, segs[i]); }
    var seg = segs[i], type = seg ? seg.type : (i === -1 ? 'avant' : 'fin');
    if (R[type] && R[type].tick) R[type].tick(S.el, seg ? t - seg.t : t, seg);
    var now2 = performance.now(), dt = Math.min(.1, (now2 - (S.last || now2)) / 1000); pasAudio(dt); pasVideo(dt); S.last = now2;
    precharge(i); majHooks(t); lumiere(t);
    if (clock) clock.textContent = fmt(t) + ' / ' + fmt(S.prog.duree) + (seg ? ' · ' + seg.type : '');
    requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------------ régie de répétition
  var regieEl = document.getElementById('sp-regie'), clock = null;
  function regie() {
    if (!regieEl || !S.prog) return;
    var cur = regieEl.querySelector('[aria-current]'); if (cur) cur.removeAttribute('aria-current');
    var li = regieEl.querySelector('[data-i="' + S.idx + '"]'); if (li) { li.setAttribute('aria-current', 'true'); li.scrollIntoView({ block: 'nearest' }); }
  }
  function goto(t) { if (S.paused !== null) S.paused = t; else S.adj += t - now(); }
  function buildRegie() {
    if (!regieEl) return;
    regieEl.innerHTML = '<div class="sp-ctrl"><button data-a="prev" type="button" title="Segment précédent">' + ico('skip-back', 20) + '</button>' +
      '<button data-a="pause" type="button" title="Pause">' + ico('pause', 20) + '</button><button data-a="next" type="button" title="Segment suivant">' + ico('skip-forward', 20) + '</button>' +
      '<span class="sp-clock"></span></div><div class="sp-speed">Vitesse : ' + [1, 2, 4, 8].map(function (v) { return '<button data-v="' + v + '" type="button">×' + v + '</button>'; }).join('') +
      '<small>au-delà de ×2 : fond musical au lieu des clips</small></div>' +
      '<ol class="sp-list">' + S.prog.segments.map(function (s, i) {
        var label = s.type + (s.nom ? ' · ' + s.nom : '') + (s.rang ? ' #' + s.rang : '') + (s.format ? ' · ' + s.format : '') + (s.artiste ? ' · ' + s.artiste : '');
        return '<li data-i="' + i + '"><button type="button" data-t="' + s.t + '"><span>' + fmt(s.t) + '</span>' + esc(label) + '</button>' + '</li>'; }).join('') + '</ol>';
    clock = regieEl.querySelector('.sp-clock');
    regieEl.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var segs = S.prog.segments, i = Math.max(0, S.idx);
      if (b.dataset.t) goto(parseFloat(b.dataset.t) + .01);
      else if (b.dataset.v) { var t = now(); S.speed = parseFloat(b.dataset.v); S.start = Date.now(); S.adj = t; }
      else if (b.dataset.a === 'next') goto((segs[i + 1] || segs[i]).t + .01);
      else if (b.dataset.a === 'prev') goto((segs[i - 1] || segs[0]).t + .01);
      else if (b.dataset.a === 'pause') {
        if (S.paused === null) { S.paused = now(); }
        else { var p = S.paused; S.paused = null; S.start = Date.now(); S.adj = p; }
        b.innerHTML = ico(S.paused === null ? 'pause' : 'play', 20);
      }
    });
  }

  // ------------------------------------------------------------------ vote du public (site) : pastille, code secret, tendance du duel
  var voteEl = document.createElement('div'); voteEl.className = 'sp-vote'; voteEl.hidden = true; scene.appendChild(voteEl);
  S.votes = {};
  function majVotes() {
    fetch('/show/resultats.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) {
      S.votes = {}; (d.votes || []).forEach(function (v) { S.votes[v.slug] = v; });
      var ouverts = (d.votes || []).filter(function (v) { return v.statut === 'ouvert'; }).length;
      var txt = (ouverts ? ico('message', 30) + '<b>VOTE OUVERT</b><span>cauricharts.com/show/vote</span>' : '') +
        (d.code ? '<b class="sp-vote__code">CODE ' + esc(d.code) + '</b>' : '');
      voteEl.innerHTML = txt; voteEl.hidden = !txt;
    }).catch(function () {});
  }
  majVotes(); setInterval(majVotes, 8000);

  // outil de diagnostic (répétition) : état du lecteur YouTube
  window.__spDebug = function () {
    var e = null; try { e = { etat: yt && yt.getPlayerState(), temps: yt && yt.getCurrentTime(), id: ytWant && ytWant.id, erreur: ytWant && ytWant.erreur, pret: ytReady }; } catch (x) { e = { exception: String(x) }; }
    return e;
  };

  // ------------------------------------------------------------------ chargement
  fetch(root.dataset.programme).then(function (r) { return r.json(); }).then(function (p) {
    S.prog = p; S.icons = p.icones || {};
    buildRegie(); majTicker(); ytLoad(); requestAnimationFrame(frame);
  }).catch(function () { content.innerHTML = '<div class="sp-col sp-center"><p class="sp-h2">Le show se charge…</p><p class="sp-t2">Rechargez la page dans un instant.</p></div>'; });
})();
