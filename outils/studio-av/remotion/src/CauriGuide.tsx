// « Le guide Cauri Charts » (14/11/2026) — la caméra se promène sur les vraies pages des documents (Le voyage d'un titre,
// Cauri Charts Magazine), la mascotte entre dans l'image et touche du doigt chaque point expliqué. Charte claire.
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame,
  useVideoConfig, Easing } from "remotion";
import { loadFont as antonFont } from "@remotion/google-fonts/Anton";
import { loadFont as montFont } from "@remotion/google-fonts/Montserrat";

const { fontFamily: ANTON } = antonFont();
const { fontFamily: MONT } = montFont("normal", { weights: ["500", "700", "800", "900"] });
const ENCRE = "#16132b", VIOLET = "#7B5CFF", CIEL = "#2FA8FF", MAGENTA = "#E04FD0";

type Mot = { m: string; d: number; f: number };
type Touche = { t: number; x: number; y: number };
type Seg = { d: number; f: number; page: string; W: number; H: number; de: number[]; a: number[]; pose: string;
  carte: { grand: string; petit: string }; touches: Touche[]; etiquette: string };
type Extrait = { d: number; f: number; src: string; titre: string; artiste: string; etiquette: string };
export type GuideProps = { duree: number; voix: { src: string; d: number }[]; mots: Mot[]; segs: Seg[]; extrait: Extrait | null;
  fond: string; fin: { d: number } };

export const dureeGuide = (p: GuideProps) => Math.round(p.duree * 30);

// la carte-page : 1000 × 900 px à l'écran
const CX = 40, CY = 230, CW = 1000, CH = 900;
// bout de l'index dans m2-presente.png (511 × 914) : la main pointe vers la gauche
const DOIGT = { x: 0.006, y: 0.232, w: 511, h: 914 };
const HM = 620;   // hauteur de la mascotte qui touche

const camera = (s: Seg, k: number) => {
  const e = Easing.inOut(Easing.cubic)(Math.min(1, Math.max(0, k)));
  const cx = s.de[0] + (s.a[0] - s.de[0]) * e, cy = s.de[1] + (s.a[1] - s.de[1]) * e, z = s.de[2] + (s.a[2] - s.de[2]) * e;
  const rh = z * s.H, rw = rh * CW / CH;                       // région de la page montrée (px de l'image)
  const x0 = Math.min(Math.max(cx * s.W - rw / 2, 0), Math.max(0, s.W - rw));
  const y0 = Math.min(Math.max(cy * s.H - rh / 2, 0), Math.max(0, s.H - rh));
  return { x0, y0, sc: CH / rh };
};

const Fond: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "#fbfbff" }}>
      <div style={{ position: "absolute", width: 900, height: 900, borderRadius: "50%", right: -300, top: -250 + Math.sin(f / 90) * 30,
        background: "radial-gradient(circle, rgba(47,168,255,.28), rgba(47,168,255,0) 70%)" }} />
      <div style={{ position: "absolute", width: 1000, height: 1000, borderRadius: "50%", left: -400, bottom: -300 + Math.cos(f / 80) * 30,
        background: "radial-gradient(circle, rgba(123,92,255,.25), rgba(123,92,255,0) 70%)" }} />
    </AbsoluteFill>
  );
};

const Entete: React.FC<{ texte: string }> = ({ texte }) => (
  <div style={{ position: "absolute", top: 70, left: 40, right: 40, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
    <Img src={staticFile("raconte/logo.png")} style={{ height: 70, filter: "invert(1) brightness(.15)" }} />
    <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 26, letterSpacing: 4, color: "#fff", padding: "12px 22px", borderRadius: 999,
      background: `linear-gradient(90deg, ${VIOLET}, ${CIEL})`, boxShadow: "0 10px 30px rgba(123,92,255,.35)" }}>{texte}</div>
  </div>
);

// une étape : la page filmée, la carte du chiffre, la mascotte qui vient toucher les points
const Etape: React.FC<{ s: Seg; dernier: boolean; num: string }> = ({ s, dernier, num }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.round((s.f - s.d) * 30);
  const entree = interpolate(f, [0, 9], [0, 1], { extrapolateRight: "clamp" });
  const sortie = dernier ? 1 : interpolate(f, [n - 6, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const k = f / n;
  const cam = camera(s, k);
  const s1 = spring({ frame: f - 6, fps, config: { damping: 13, stiffness: 150 } });

  // mascotte : la touche en cours (celle dont le moment est passé, jusqu'à la suivante)
  const tps = s.touches.map((x) => Math.round(x.t * n));
  let i = -1;
  tps.forEach((tp, j) => { if (f >= tp - 12) i = j; });
  const touche = i >= 0 ? s.touches[i] : null;
  const debut = i >= 0 ? tps[i] - 12 : 0;
  const arrive = spring({ frame: f - debut, fps, config: { damping: 15, stiffness: 110 } });
  let mascotte = null, onde = null;
  if (touche) {
    const c2 = camera(s, k);
    const w = HM * DOIGT.w / DOIGT.h;
    const pos = (t: Touche) => {
      const px = CX + (t.x * s.W - c2.x0) * c2.sc, py = CY + (t.y * s.H - c2.y0) * c2.sc;
      const gauche = px > 560;                                 // point à droite : la mascotte vient par la droite, main vers la gauche
      return { px, py, gauche, left: gauche ? px - DOIGT.x * w : px - (1 - DOIGT.x) * w, top: py - DOIGT.y * HM };
    };
    const ici = pos(touche);
    const { px, py, gauche } = ici;
    const avant = i > 0 ? pos(s.touches[i - 1]) : { left: gauche ? 1100 : -w - 60, top: ici.top + 200 };
    const x = avant.left + (ici.left - avant.left) * arrive;
    const top = avant.top + (ici.top - avant.top) * arrive;
    const appui = interpolate(f - tps[i], [-4, 0, 4, 10], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    mascotte = (
      <div style={{ position: "absolute", left: x, top: top + 6 * appui, width: w, height: HM, opacity: sortie,
        transform: gauche ? undefined : "scaleX(-1)", filter: "drop-shadow(0 24px 30px rgba(40,30,90,.35))" }}>
        <Img src={staticFile("raconte/m2-presente.png")} style={{ width: "100%", height: "100%" }} />
      </div>);
    const r = interpolate(f - tps[i], [0, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    onde = f >= tps[i] ? (
      <>
        <div style={{ position: "absolute", left: px - 70 * r, top: py - 70 * r, width: 140 * r, height: 140 * r, borderRadius: "50%",
          border: `6px solid ${MAGENTA}`, opacity: (1 - r) * sortie }} />
        <div style={{ position: "absolute", left: px - 16, top: py - 16, width: 32, height: 32, borderRadius: "50%",
          background: `radial-gradient(circle, #fff 0 30%, ${MAGENTA} 32% 100%)`, opacity: interpolate(f - tps[i], [0, 4, 40, 50], [0, 1, 1, 0], { extrapolateRight: "clamp" }) * sortie,
          boxShadow: `0 0 30px ${MAGENTA}` }} />
      </>) : null;
  }
  const repos = !touche || (i >= 0 && f < tps[i] - 12);
  return (
    <AbsoluteFill style={{ opacity: Math.min(entree, sortie) }}>
      {/* la page filmée */}
      <div style={{ position: "absolute", left: CX, top: CY, width: CW, height: CH, borderRadius: 34, overflow: "hidden", background: "#fff",
        boxShadow: "0 40px 80px rgba(40,50,120,.18), 0 0 0 1px rgba(123,92,255,.12)" }}>
        <Img src={staticFile(s.page)} style={{ position: "absolute", left: -cam.x0 * cam.sc, top: -cam.y0 * cam.sc, width: s.W * cam.sc, height: s.H * cam.sc }} />
      </div>
      {/* la carte du chiffre */}
      <div style={{ position: "absolute", right: 40, top: 1470, width: 560, padding: "26px 30px", borderRadius: 30, color: "#fff",
        background: `linear-gradient(135deg, ${MAGENTA}, ${VIOLET} 50%, ${CIEL})`, boxShadow: "0 24px 50px rgba(123,92,255,.35)",
        transform: `translateY(${(1 - s1) * 80}px) scale(${0.85 + 0.15 * s1})`, opacity: s1 }}>
        <div style={{ fontFamily: ANTON, fontSize: s.carte.grand.length > 7 ? 86 : 112, lineHeight: 1 }}>{s.carte.grand}</div>
        <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 32, marginTop: 8, lineHeight: 1.2 }}>{s.carte.petit}</div>
      </div>
      {/* numéro d'étape, détouré, quand la mascotte est partie toucher la page */}
      {!repos ? <div style={{ position: "absolute", left: 50, top: 1440, fontFamily: ANTON, fontSize: num.length > 2 ? 200 : 300, lineHeight: 1, color: "transparent",
        WebkitTextStroke: "3px rgba(123,92,255,.35)", opacity: s1 }}>{num}</div> : null}
      {/* la mascotte au repos, dans son coin */}
      {repos ? (
        <div style={{ position: "absolute", left: 10, bottom: -10, height: 560, transform: `translateY(${(1 - s1) * 300}px)`,
          filter: "drop-shadow(0 24px 30px rgba(40,30,90,.3))" }}>
          <Img src={staticFile(s.pose)} style={{ height: "100%" }} />
        </div>) : null}
      {onde}
      {mascotte}
    </AbsoluteFill>
  );
};

const ExtraitVue: React.FC<{ e: Extrait }> = ({ e }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.round((e.f - e.d) * 30);
  const s = spring({ frame: f - 4, fps, config: { damping: 14, stiffness: 120 } });
  const o = interpolate(f, [0, 8, n - 8, n], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0814", opacity: o }}>
      <OffthreadVideo src={staticFile(e.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.04 + f / 3000})` }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(8,6,20,.55) 0%, rgba(8,6,20,0) 30%, rgba(8,6,20,0) 55%, rgba(8,6,20,.85) 100%)" }} />
      <div style={{ position: "absolute", left: 60, right: 60, bottom: 260, transform: `translateY(${(1 - s) * 60}px)`, opacity: s }}>
        <div style={{ display: "inline-block", fontFamily: MONT, fontWeight: 900, fontSize: 30, letterSpacing: 4, color: "#14102a", background: "#fff",
          padding: "10px 22px", borderRadius: 999 }}>{e.etiquette}</div>
        <div style={{ fontFamily: ANTON, fontSize: 150, color: "#fff", lineHeight: 1, marginTop: 18, textShadow: "0 10px 40px rgba(0,0,0,.6)" }}>{e.titre}</div>
        <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 46, color: "#8FD3FF", marginTop: 6 }}>{e.artiste}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", height: 60, marginTop: 24 }}>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} style={{ width: 12, borderRadius: 6, background: MAGENTA, height: 14 + Math.abs(Math.sin(f / (3 + i) + i * 1.7)) * 46 }} />))}
          <span style={{ fontFamily: MONT, fontWeight: 800, fontSize: 34, color: "#fff", marginLeft: 14 }}>EN ÉCOUTE</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// sous-titres : 4 mots au plus, le mot dit s'allume
const groupes = (mots: Mot[]) => {
  const g: Mot[][] = [];
  let cur: Mot[] = [];
  mots.forEach((m, i) => {
    const pause = i > 0 && m.d - mots[i - 1].f > 0.28;
    if (cur.length && (pause || cur.length >= 4)) { g.push(cur); cur = []; }
    cur.push(m);
  });
  if (cur.length) g.push(cur);
  return g;
};

const SousTitres: React.FC<{ mots: Mot[]; cache: { d: number; f: number } | null }> = ({ mots, cache }) => {
  const f = useCurrentFrame();
  const t = f / 30;
  if (cache && t >= cache.d && t < cache.f) return null;
  const gs = groupes(mots);
  const g = gs.find((x, i) => t >= x[0].d - 0.05 && t < (gs[i + 1] ? gs[i + 1][0].d - 0.05 : x[x.length - 1].f + 0.6));
  if (!g) return null;
  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: 1170, height: 260, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center", lineHeight: 1.12 }}>
        {g.map((m, i) => {
          const actif = t >= m.d && t < m.f + 0.08;
          return (
            <span key={i} style={{ fontFamily: MONT, fontWeight: 900, fontSize: 70, textTransform: "uppercase", display: "inline-block", margin: "0 12px",
              color: actif ? VIOLET : t >= m.d ? ENCRE : "rgba(22,19,43,.35)", transform: `translateY(${actif ? -6 : 0}px)`,
              WebkitTextStroke: "8px #fff", paintOrder: "stroke fill" }}>{m.m}</span>);
        })}
      </div>
    </div>
  );
};

const Progression: React.FC<{ total: number }> = ({ total }) => {
  const f = useCurrentFrame();
  return <div style={{ position: "absolute", top: 0, left: 0, height: 10, width: `${(f / total) * 100}%`,
    background: `linear-gradient(90deg, ${CIEL}, ${VIOLET}, ${MAGENTA})` }} />;
};

export const CauriGuide: React.FC<GuideProps> = (p) => {
  const total = dureeGuide(p);
  const fr = (s: number) => Math.round(s * 30);
  const f = useCurrentFrame();
  const seg = p.segs.find((s) => f / 30 >= s.d && f / 30 < s.f) ?? p.segs[p.segs.length - 1];
  const ex = p.extrait;
  return (
    <AbsoluteFill>
      <Fond />
      {p.segs.map((s, i) => {
        const dernier = i === p.segs.length - 1;
        const fin = dernier ? total : fr(s.f) + 6;
        return <Sequence key={i} from={fr(s.d)} durationInFrames={fin - fr(s.d)}><Etape s={{ ...s, f: dernier ? p.duree : s.f }} dernier={dernier} num={i < 8 ? String(i + 1).padStart(2, "0") : "N°46"} /></Sequence>;
      })}
      <Entete texte={seg.etiquette} />
      <SousTitres mots={p.mots} cache={ex} />
      {ex ? <Sequence from={fr(ex.d)} durationInFrames={fr(ex.f) - fr(ex.d)}><ExtraitVue e={ex} />
        <Audio src={staticFile(ex.src)} volume={(k) => interpolate(k, [0, 10, fr(ex.f - ex.d) - 15, fr(ex.f - ex.d)], [0, 0.95, 0.95, 0], { extrapolateRight: "clamp" })} /></Sequence> : null}
      {p.segs.map((s, i) => i ? <Sequence key={"w" + i} from={fr(s.d)}><Audio src={staticFile("raconte/sfx/whoosh-fast.mp3")} volume={0.16} /></Sequence> : null)}
      {p.segs.flatMap((s, i) => s.touches.map((t, j) => (
        <Sequence key={`t${i}-${j}`} from={fr(s.d + t.t * (s.f - s.d))}><Audio src={staticFile("raconte/sfx/sparkle-whoosh.mp3")} volume={0.12} /></Sequence>)))}
      {p.voix.map((v, i) => <Sequence key={"v" + i} from={fr(v.d)}><Audio src={staticFile(v.src)} /></Sequence>)}
      <Audio src={staticFile(p.fond)} loop volume={(k) => {
        const t = k / 30;
        if (ex && t > ex.d - 0.4 && t < ex.f + 0.2) return 0;
        return t > p.fin.d ? 0.12 : 0.05;
      }} />
      <Progression total={total} />
    </AbsoluteFill>
  );
};
