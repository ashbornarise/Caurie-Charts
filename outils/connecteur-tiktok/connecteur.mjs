// Connecteur TikTok LIVE -> régie Cauri Charts (recréé le 27/11/2026 : l'original vivait sur l'ancien PC, jamais versionné).
//
// Il écoute le live du compte (commentaires, j'aime, cadeaux, arrivées, abonnements, nombre de spectateurs) et envoie
// toutes les 2 secondes un paquet à la régie : POST /live/<jeton>/regie/commentaires
//   {liste: [{user, nom, texte}], cadeaux: [{user, nom, diamants, n, cadeau}], arrivees: [nom], abonnes: [nom],
//    likes: n, likesPar: {user: n}, spectateurs: n, mode}
// Le jeton de la régie n'est PAS dans le dépôt : il est lu dans le fichier de réglages (voir lancer.cmd).
//
//   node connecteur.mjs            -> live réel
//   node connecteur.mjs --test     -> paquets marqués « test » (la régie les traite à part)
import fs from 'node:fs';
import { TikTokLiveConnection, WebcastEvent, ControlEvent } from 'tiktok-live-connector';

const REGLAGES = process.env.CAURI_CONNECTEUR || 'C:/Users/agbal/Cauri-relais/connecteur.env';
const conf = Object.fromEntries(fs.readFileSync(REGLAGES, 'utf8').split(/\r?\n/)
  .map(l => l.trim()).filter(l => l && !l.startsWith('#') && l.includes('='))
  .map(l => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()]));
// --essai <compte> : se branche sur le live d'un autre compte et AFFICHE les paquets sans rien envoyer (vérification)
const ESSAI = process.argv.includes('--essai') ? (process.argv[process.argv.indexOf('--essai') + 1] || '') : '';
const COMPTE = (ESSAI || conf.TIKTOK_COMPTE || 'caurichartsofficial').replace(/^@/, '');
const REGIE = conf.REGIE_URL;   // https://cauricharts.com/live/<jeton>/regie/commentaires
const MODE = process.argv.includes('--test') ? 'test' : '';
if (!REGIE || !/\/regie\/commentaires$/.test(REGIE)) { console.error(`REGIE_URL manquante ou invalide dans ${REGLAGES}`); process.exit(1); }

const heure = () => new Date().toLocaleTimeString('fr-FR');
const log = (...a) => console.log(heure(), ...a);

// ---------------- paquet en cours (vidé à chaque envoi réussi)
let p = vide();
function vide() { return { liste: [], cadeaux: [], arrivees: [], abonnes: [], likes: 0, likesPar: {}, spectateurs: null }; }
// 27/11/2026 : en 2.5.0, les champs réels diffèrent du README : pseudo = user.displayId, texte = content,
// j'aime = count, spectateurs = total (vérifié sur un vrai live). On garde les anciens noms en secours.
const pseudo = u => String(u?.displayId || u?.uniqueId || u?.idStr || u?.id || '?').slice(0, 30);
const nom = u => String(u?.nickname || u?.uniqueId || '?').slice(0, 30);

async function envoie() {
  const a = p;
  if (!a.liste.length && !a.cadeaux.length && !a.arrivees.length && !a.abonnes.length && !a.likes && a.spectateurs === null) return;
  p = vide();
  if (ESSAI) {   // vérification : rien ne part vers la régie
    log(`paquet : ${a.liste.length} commentaire(s), ${a.likes} j'aime de ${Object.keys(a.likesPar).length} personne(s), ` +
        `${a.cadeaux.length} cadeau(x) ${a.cadeaux.map(g => g.cadeau + ' ' + g.diamants + 'd').join(', ')}, ${a.arrivees.length} arrivée(s), ` +
        `${a.abonnes.length} abonné(s), spectateurs ${a.spectateurs ?? '-'}${a.liste[0] ? ' | ex. « ' + a.liste[0].texte.slice(0, 40) + ' »' : ''}`);
    return;
  }
  try {
    const r = await fetch(REGIE, { method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': 'cauri-connecteur' },
      body: JSON.stringify({ ...a, mode: MODE }), signal: AbortSignal.timeout(15000) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
  } catch (e) {
    // réseau coupé ou site en déploiement : on remet le paquet devant le suivant (sans grossir à l'infini)
    p.liste = [...a.liste, ...p.liste].slice(-300); p.cadeaux = [...a.cadeaux, ...p.cadeaux].slice(-150);
    p.arrivees = [...a.arrivees, ...p.arrivees].slice(-50); p.abonnes = [...a.abonnes, ...p.abonnes].slice(-100);
    p.likes += a.likes; for (const [u, n] of Object.entries(a.likesPar)) p.likesPar[u] = (p.likesPar[u] || 0) + n;
    if (p.spectateurs === null) p.spectateurs = a.spectateurs;
    log('envoi raté, nouvel essai dans 2 s :', e.message);
  }
}
setInterval(envoie, 2000);

// ---------------- les événements, d'où qu'ils viennent (TikTok en direct ou TikFinity) : mêmes règles
// Un événement peut avoir le pseudo dans d.user (tiktok-live-connector 2.x) ou à plat (TikFinity : uniqueId, nickname…).
const qui = d => d.user || d;
let premierCadeau = true;
const EV = {
  chat: d => p.liste.push({ user: pseudo(qui(d)), nom: nom(qui(d)), texte: String(d.content ?? d.comment ?? '').slice(0, 200) }),
  like: d => { const n = Number(d.count ?? d.likeCount) || 0; if (!n) return; p.likes += n; const u = pseudo(qui(d)); p.likesPar[u] = (p.likesPar[u] || 0) + n; },
  gift: d => {
    if (ESSAI && premierCadeau) { premierCadeau = false; log('1er cadeau (champs) :', Object.keys(d).join(','), JSON.stringify({ giftDetails: d.giftDetails && { giftType: d.giftDetails.giftType, giftName: d.giftDetails.giftName, diamondCount: d.giftDetails.diamondCount }, giftType: d.giftType, diamondCount: d.diamondCount, repeatCount: d.repeatCount, comboCount: d.comboCount, repeatEnd: d.repeatEnd })); }
    const det = d.giftDetails || d.gift || {};
    const type = det.giftType ?? det.type ?? d.giftType;
    if (type === 1 && !d.repeatEnd) return;   // série en cours : on compte une seule fois, à la fin de la série
    const n = Math.max(1, Number(d.repeatCount ?? d.comboCount) || 1);
    const unite = Number(det.diamondCount ?? det.diamond_count ?? d.diamondCount ?? 1) || 1;
    p.cadeaux.push({ user: pseudo(qui(d)), nom: nom(qui(d)), n, diamants: unite * n,
      cadeau: String(det.giftName || det.name || d.giftName || 'cadeau').slice(0, 30) });
  },
  member: d => p.arrivees.push(nom(qui(d))),
  follow: d => p.abonnes.push(nom(qui(d))),
  roomUser: d => { const v = d.total ?? d.viewerCount; if (v != null) p.spectateurs = Number(v); },
};

// ---------------- source 1 : TikTok en direct (tiktok-live-connector), avec reconnexion tant que le connecteur tourne
let conn = null, attente = 15;
async function connecte() {
  // enableExtendedGiftInfo : NON (27/11/2026, la liste des cadeaux exige un abonnement Business chez Euler Stream et
  // bloquait toute la connexion) ; la valeur d'un cadeau vient de giftDetails.diamondCount
  conn = new TikTokLiveConnection(COMPTE, { processInitialData: false, enableExtendedGiftInfo: false, ...(conf.SIGN_API_KEY ? { signApiKey: conf.SIGN_API_KEY } : {}) });
  conn.on(WebcastEvent.CHAT, EV.chat);
  conn.on(WebcastEvent.LIKE, EV.like);
  conn.on(WebcastEvent.GIFT, EV.gift);
  conn.on(WebcastEvent.MEMBER, EV.member);
  conn.on(WebcastEvent.FOLLOW, EV.follow);
  conn.on(WebcastEvent.ROOM_USER, EV.roomUser);
  conn.on(WebcastEvent.STREAM_END, () => { log('le live est terminé'); relance(); });
  conn.on(ControlEvent.DISCONNECTED, () => { log('déconnecté'); relance(); });
  conn.on(ControlEvent.ERROR, ({ info }) => log('erreur :', info || ''));
  try {
    const etat = await conn.connect();
    attente = 15;
    log(`connecté au live de @${COMPTE} (salle ${etat.roomId})${MODE ? ' — MODE TEST' : ''}`);
  } catch (e) {
    log(`pas de live en cours sur @${COMPTE} (${e.constructor?.name || 'erreur'} : ${String(e.message || e).slice(0, 120)}) — nouvel essai dans ${attente} s`);
    relance();
  }
}
let minuteur = null;
function relance() {
  if (minuteur) return;
  try { conn?.disconnect(); } catch (e) { /* déjà fermé */ }
  minuteur = setTimeout(() => { minuteur = null; connecte(); }, attente * 1000);
  attente = Math.min(60, attente + 15);
}

// ---------------- source 2 : TikFinity (application Windows) qui est déjà branchée sur le live.
// TikFinity diffuse les événements du live sur ce PC (ws://localhost:21213/) : on les lit et on les envoie à la régie.
const TIKFINITY = process.argv.includes('--tikfinity') || conf.SOURCE === 'tikfinity';
const TF_URL = conf.TIKFINITY_URL || 'ws://localhost:21213/';
function tikfinity() {
  const ws = new WebSocket(TF_URL);
  ws.onopen = () => log(`branché sur TikFinity (${TF_URL})${MODE ? ' — MODE TEST' : ''}`);
  ws.onmessage = m => {
    let x; try { x = JSON.parse(m.data); } catch (e) { return; }
    const nomEv = String(x.event || x.type || ''), d = x.data || x;
    const f = EV[nomEv] || EV[{ viewerCount: 'roomUser' }[nomEv]];
    if (f) { try { f(d); } catch (e) { log('événement TikFinity illisible :', nomEv); } }
  };
  ws.onclose = () => { log('TikFinity fermé ou pas encore lancé — nouvel essai dans 10 s'); setTimeout(tikfinity, 10000); };
  ws.onerror = () => {};
}

log(`connecteur Cauri Charts : @${COMPTE} -> régie${MODE ? ' (MODE TEST)' : ''}${TIKFINITY ? ' — source : TikFinity' : ' — source : TikTok en direct'}`);
if (TIKFINITY) tikfinity(); else connecte();
