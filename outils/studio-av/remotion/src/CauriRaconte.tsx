// « Cauri raconte » — composition verticale 1080 × 1920, 30 i/s.
// Reconstruite le 28/11/2026 (l'atelier Studio-AV est parti avec l'ancien PC) à partir de ce que fabriquent
// django/core/services/social/raconte_v2.py, raconte_v3.py, raconte_v4.py et studio_raconte.py : tous les temps (d, f) sont
// en secondes depuis le début ; tous les fichiers sont relatifs à public/ (staticFile). Les plans vidéo sont déjà coupés
// et montés (muets) par Python ; le son est entièrement dans voix.mp3, les musiques et les effets.
import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, random, spring, staticFile, useCurrentFrame,
  useVideoConfig, Easing } from "remotion";
import { loadFont as antonFont } from "@remotion/google-fonts/Anton";
import { loadFont as montFont } from "@remotion/google-fonts/Montserrat";
import { loadFont as specialElite } from "@remotion/google-fonts/SpecialElite";

const { fontFamily: ANTON } = antonFont();
const { fontFamily: MONT } = montFont("normal", { weights: ["500", "700", "800", "900"] });
const { fontFamily: MACHINE } = specialElite();
const FPS = 30;
const VIOLET = "#7B5CFF", CIEL = "#2FA8FF", MAGENTA = "#E04FD0", OR = "#F5C04A", ENCRE = "#16132b";
// mêmes temps que MACHINE dans raconte_v4.py : les frappes sonores tombent sur les lettres
const MACH = { depart: 0.3, car_num: 0.07, entre: 0.35, car_titre: 0.1 };

type T = { d: number; f: number };
export type RaconteProps = Record<string, any> & { duree: number };

const fr = (s: number) => Math.round(s * FPS);
const src = (s: string) => (/^https?:/.test(s) ? s : staticFile(s));
const Seq: React.FC<{ d: number; f: number; children: React.ReactNode; nom?: string }> = ({ d, f, children, nom }) =>
  f - d <= 0 ? null : <Sequence from={fr(d)} durationInFrames={Math.max(1, fr(f) - fr(d))} name={nom} layout="none">{children}</Sequence>;

// apparition / disparition douce d'un élément qui dure n images
const useFondu = (n: number, entree = 7, sortie = 7) => {
  const f = useCurrentFrame();
  return Math.min(interpolate(f, [0, entree], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(f, [n - sortie, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
};

// ------------------------------------------------------------------------------------------------ plans
const Plan: React.FC<{ p: any }> = ({ p }) => {
  const f = useCurrentFrame();
  const n = fr(p.f) - fr(p.d);
  const z = interpolate(f, [0, n], [1.04, 1.12]);
  const etiquette = p.libelle || p.annee;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {p.image ? (
        <>
          {p.fond ? <Img src={src(p.fond)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} /> : null}
          <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
            <Img src={src(p.src)} style={{ width: "100%", height: p.fond ? "auto" : "100%", maxHeight: "100%", objectFit: p.fond ? "contain" : "cover",
              transform: `scale(${z})` }} />
          </AbsoluteFill>
        </>
      ) : (
        <OffthreadVideo src={src(p.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      )}
      {etiquette ? (
        <div style={{ position: "absolute", top: 250, left: 50, fontFamily: MONT, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: "#fff",
          padding: "10px 20px", borderRadius: 999, background: "rgba(0,0,0,.45)", border: "2px solid rgba(255,255,255,.35)" }}>{etiquette}</div>
      ) : null}
      {p.credit ? (
        <div style={{ position: "absolute", bottom: 60, right: 40, fontFamily: MONT, fontWeight: 500, fontSize: 20, color: "rgba(255,255,255,.75)" }}>{p.credit}</div>
      ) : null}
    </AbsoluteFill>
  );
};

const Flash: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: "#fff", opacity: interpolate(f, [0, 4], [0.55, 0], { extrapolateRight: "clamp" }) }} />;
};

const Voile: React.FC = () => (
  <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 55%, rgba(0,0,0,.72) 100%)" }} />
);

// ------------------------------------------------------------------------------------------------ titre d'ouverture
const Ouverture: React.FC<{ titre: any; n: number }> = ({ titre, n }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const o = useFondu(n, 5, 10);
  const t = typeof titre === "string" ? { haut: "", nom: titre, bas: "" } : titre || {};
  const s = spring({ frame: f - 3, fps, config: { damping: 12, stiffness: 140 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: o, padding: 60 }}>
      <div style={{ textAlign: "center", transform: `scale(${0.85 + 0.15 * s})` }}>
        {t.haut ? <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 46, letterSpacing: 10, color: OR, textShadow: "0 4px 20px rgba(0,0,0,.6)" }}>{t.haut}</div> : null}
        <div style={{ fontFamily: ANTON, fontSize: t.nom && t.nom.length > 12 ? 130 : 170, lineHeight: 1, color: "#fff", textTransform: "uppercase",
          textShadow: "0 10px 40px rgba(0,0,0,.7)", marginTop: 10 }}>{t.nom}</div>
        {t.bas ? <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 34, color: "#fff", marginTop: 26, opacity: 0.92,
          textShadow: "0 4px 20px rgba(0,0,0,.7)" }}>{t.bas}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ titres de chapitre
const TitreChapitre: React.FC<{ c: any }> = ({ c }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(c.f) - fr(c.d);
  const t = f / FPS;
  if (c.style === "machine") {
    const bruit = c.bruit || 0;
    const t0 = bruit + MACH.depart;
    const num: string = c.numero || "";
    const titre: string = c.titre || "";
    const nNum = Math.max(0, Math.min(num.length, Math.floor((t - t0) / MACH.car_num) + 1));
    const t1 = t0 + num.length * MACH.car_num + MACH.entre;
    const nTit = Math.max(0, Math.min(titre.length, Math.floor((t - t1) / MACH.car_titre) + 1));
    const curseur = Math.floor(f / 8) % 2 === 0;
    return (
      <AbsoluteFill style={{ background: "#0b0a0f", justifyContent: "center", alignItems: "center", padding: 80 }}>
        {t < bruit ? <AbsoluteFill style={{ background: `repeating-linear-gradient(0deg, rgba(255,255,255,${0.05 + 0.1 * random("bruit" + f)}) 0 2px, transparent 2px 5px)` }} /> : null}
        <div style={{ fontFamily: MACHINE, color: "#f1ead8", textAlign: "left", width: "100%" }}>
          <div style={{ fontSize: 54, letterSpacing: 6, opacity: 0.85 }}>{num.slice(0, t >= t0 ? nNum : 0)}</div>
          <div style={{ fontSize: 92, lineHeight: 1.1, marginTop: 30 }}>{titre.slice(0, t >= t1 ? nTit : 0)}{curseur ? "▌" : " "}</div>
          {c.annees && t > t1 + titre.length * MACH.car_titre ? <div style={{ fontSize: 40, marginTop: 30, color: OR }}>{c.annees}</div> : null}
        </div>
      </AbsoluteFill>
    );
  }
  const o = useFondu(n, 6, 8);
  const s = spring({ frame: f - 4, fps, config: { damping: 14, stiffness: 120 } });
  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 40%, #241d4a 0%, #0b0a14 70%)", justifyContent: "center", alignItems: "center",
      opacity: o, padding: 70 }}>
      <div style={{ textAlign: "center", transform: `translateY(${(1 - s) * 60}px)` }}>
        {c.numero ? <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 40, letterSpacing: 12, color: OR }}>{String(c.numero).toUpperCase()}</div> : null}
        <div style={{ fontFamily: ANTON, fontSize: 118, lineHeight: 1.02, color: "#fff", textTransform: "uppercase", marginTop: 18 }}>{c.titre}</div>
        {c.annees ? <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 38, color: CIEL, marginTop: 24, letterSpacing: 4 }}>{c.annees}</div> : null}
        <div style={{ width: 160 * s, height: 6, borderRadius: 3, margin: "34px auto 0", background: `linear-gradient(90deg, ${VIOLET}, ${MAGENTA})` }} />
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ jauge des secrets
// écran noir, barre sphérique et royale ; le cauri avance un peu, puis le cadenas saute (son « unlock » à +1,2 s)
const Jauge: React.FC<{ s: any }> = ({ s }) => {
  const f = useCurrentFrame();
  const total = Math.max(1, s.total || 1);
  const avant = s.k / total, apres = (s.k + 1) / total;
  const prog = interpolate(f, [8, 34], [avant, apres], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const tremble = f > 22 && f < 36 ? Math.sin(f * 2.2) * 6 : 0;
  const ouvert = f >= 36;
  const o = interpolate(f, [0, 6, 70, 78], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#000", justifyContent: "center", alignItems: "center", opacity: o }}>
      <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 36, letterSpacing: 10, color: OR, marginBottom: 60 }}>
        SECRET {s.k + 1} / {total}
      </div>
      <div style={{ position: "relative", width: 860, height: 64, borderRadius: 32, background: "linear-gradient(180deg,#2a2233,#120e18)",
        boxShadow: "inset 0 4px 14px rgba(0,0,0,.8), 0 0 40px rgba(245,192,74,.25)", border: "3px solid #6b5326" }}>
        <div style={{ position: "absolute", left: 6, top: 6, bottom: 6, width: `calc(${prog * 100}% - 12px)`, borderRadius: 26,
          background: "linear-gradient(180deg,#ffe8a3 0%,#f5c04a 45%,#b8861c 100%)", boxShadow: "0 0 30px rgba(245,192,74,.8)" }} />
        <div style={{ position: "absolute", top: -34, left: `calc(${prog * 100}% - 66px)`, width: 132, height: 132, borderRadius: "50%",
          background: "radial-gradient(circle at 35% 30%, #fffdf3, #f3e2b8 45%, #c9a35a 100%)", boxShadow: "0 10px 30px rgba(0,0,0,.6)",
          transform: `translateX(${tremble}px) rotate(${prog * 40}deg)`, display: "flex", justifyContent: "center", alignItems: "center" }}>
          <div style={{ width: 16, height: 76, borderRadius: 8, background: "#7a5a22", boxShadow: "inset 0 0 0 4px #e6cc8f" }} />
        </div>
      </div>
      <svg width="120" height="150" viewBox="0 0 120 150" style={{ marginTop: 90, transform: `scale(${ouvert ? 1.15 : 1})`,
        filter: ouvert ? "drop-shadow(0 0 24px #f5c04a)" : "none" }}>
        <path d={ouvert ? "M30 62 V40 a30 30 0 0 1 58 -10" : "M30 62 V40 a30 30 0 0 1 60 0 V62"} fill="none" stroke={OR} strokeWidth="12" strokeLinecap="round" />
        <rect x="12" y="62" width="96" height="78" rx="14" fill={OR} />
        <circle cx="60" cy="96" r="10" fill="#3a2a0a" /><rect x="56" y="100" width="8" height="22" rx="3" fill="#3a2a0a" />
      </svg>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ mascotte et bulle de BD
const Mascotte: React.FC<{ m: any }> = ({ m }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(m.f) - fr(m.d);
  const entree = spring({ frame: f, fps, config: { damping: 14, stiffness: 120 } });
  const sortie = interpolate(f, [n - 8, n], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const gauche = m.cote !== "droite";
  const dx = (1 - entree + sortie) * 520 * (gauche ? -1 : 1);
  const h = m.h || 820;
  return (
    <Img src={src(m.src)} style={{ position: "absolute", bottom: -30, [gauche ? "left" : "right"]: -40, height: h,
      transform: `translateX(${dx}px) translateY(${Math.sin(f / 9) * 6}px) ${gauche ? "" : "scaleX(-1)"}`,
      filter: "drop-shadow(0 20px 30px rgba(0,0,0,.5))" } as React.CSSProperties} />
  );
};

const Bulle: React.FC<{ b: any }> = ({ b }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(b.f) - fr(b.d);
  const s = spring({ frame: f, fps, config: { damping: 10, stiffness: 160 } });
  const o = interpolate(f, [n - 6, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const gauche = b.cote !== "droite";
  return (
    <div style={{ position: "absolute", top: 800, [gauche ? "left" : "right"]: 230, width: 760, opacity: o, transform: `scale(${s})`,
      transformOrigin: gauche ? "15% 100%" : "85% 100%" } as React.CSSProperties}>
      <div style={{ position: "relative", background: "#fff", borderRadius: 50, border: "6px solid #111", padding: "34px 40px",
        boxShadow: "10px 12px 0 rgba(0,0,0,.35)" }}>
        <div style={{ position: "absolute", top: -46, [gauche ? "right" : "left"]: 30, fontFamily: ANTON, fontSize: 56, color: MAGENTA,
          transform: "rotate(-6deg)", textShadow: "3px 3px 0 #111" } as React.CSSProperties}>{b.cri}</div>
        <div style={{ fontFamily: MONT, fontWeight: 900, fontSize: 40, lineHeight: 1.2, color: "#111", textTransform: "uppercase" }}>{b.texte}</div>
        <div style={{ position: "absolute", bottom: -52, [gauche ? "left" : "right"]: 40, width: 0, height: 0, borderLeft: "30px solid transparent",
          borderRight: "30px solid transparent", borderTop: "56px solid #111" } as React.CSSProperties} />
      </div>
    </div>
  );
};

const Verite: React.FC<{ n: number }> = ({ n }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 9, stiffness: 200 } });
  const o = interpolate(f, [n - 8, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: o }}>
      <div style={{ fontFamily: ANTON, fontSize: 150, color: OR, letterSpacing: 6, transform: `scale(${2 - s}) rotate(-4deg)`,
        textShadow: "0 0 40px rgba(245,192,74,.6), 0 8px 0 #000", border: `10px solid ${OR}`, padding: "10px 40px", borderRadius: 20 }}>LA VÉRITÉ</div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ cartes, contrats, projets
const Carte: React.FC<{ c: any }> = ({ c }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(c.f) - fr(c.d);
  const s = spring({ frame: f, fps, config: { damping: 13, stiffness: 150 } });
  const o = interpolate(f, [n - 7, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const couleur = c.or ? OR : "#fff";
  return (
    <div style={{ position: "absolute", top: 330, left: 70, right: 70, opacity: o, transform: `translateY(${(1 - s) * -60}px) scale(${0.9 + 0.1 * s})` }}>
      <div style={{ borderRadius: 40, padding: "40px 46px", background: "rgba(20,16,40,.45)", backdropFilter: "blur(18px)",
        border: `2px solid ${c.or ? "rgba(245,192,74,.7)" : "rgba(255,255,255,.35)"}`, boxShadow: "0 20px 60px rgba(0,0,0,.45)", textAlign: "center" }}>
        <div style={{ fontFamily: ANTON, fontSize: c.grand && String(c.grand).length > 10 ? 96 : 140, lineHeight: 1, color: couleur,
          textShadow: c.or ? "0 0 30px rgba(245,192,74,.5)" : "none" }}>{c.grand}</div>
        {c.petit ? <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 36, color: "#fff", marginTop: 14, opacity: 0.92 }}>{c.petit}</div> : null}
      </div>
    </div>
  );
};

const Contrat: React.FC<{ c: any }> = ({ c }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(c.f) - fr(c.d);
  const s = spring({ frame: f, fps, config: { damping: 14, stiffness: 120 } });
  const o = interpolate(f, [n - 7, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", top: 300, left: 90, right: 90, opacity: o, transform: `rotate(${-3 + 3 * s}deg) translateY(${(1 - s) * 200}px)` }}>
      <div style={{ background: "#fbf6e9", borderRadius: 12, padding: "44px 50px", boxShadow: "0 30px 70px rgba(0,0,0,.55)", color: ENCRE,
        fontFamily: MONT, border: "1px solid #d9cfb4" }}>
        <div style={{ fontWeight: 800, fontSize: 26, letterSpacing: 8, color: "#8a7a55" }}>CONTRAT {c.annee ? "· " + c.annee : ""}</div>
        <div style={{ fontFamily: ANTON, fontSize: 70, lineHeight: 1.05, marginTop: 14, textTransform: "uppercase" }}>{c.quoi}</div>
        {c.avec ? <div style={{ fontWeight: 700, fontSize: 34, marginTop: 10 }}>avec {c.avec}</div> : null}
        {c.montant ? <div style={{ fontFamily: ANTON, fontSize: 96, color: "#1d7a3a", marginTop: 20 }}>{c.montant}</div> : null}
        {(c.devises || []).map((x: string, i: number) => <div key={i} style={{ fontWeight: 700, fontSize: 30, color: "#5b5340" }}>≈ {x}</div>)}
        <div style={{ marginTop: 26, fontFamily: MACHINE, fontSize: 40, color: "#2a3f8f", transform: "rotate(-3deg)" }}>signé</div>
      </div>
    </div>
  );
};

const Projet: React.FC<{ p: any }> = ({ p }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(p.f) - fr(p.d);
  const o = useFondu(n, 8, 10);
  const s = spring({ frame: f - 4, fps, config: { damping: 13, stiffness: 110 } });
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <Img src={src(p.cover)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", filter: "blur(40px) brightness(.45)",
        transform: "scale(1.2)" }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: 70 }}>
        {p.etiquette ? <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 34, letterSpacing: 10, color: OR, marginBottom: 34 }}>{p.etiquette}</div> : null}
        <Img src={src(p.cover)} style={{ width: 720, height: 720, objectFit: "cover", borderRadius: 24, boxShadow: "0 40px 90px rgba(0,0,0,.7)",
          transform: `scale(${0.8 + 0.2 * s}) rotate(${(1 - s) * -8}deg) scale(${interpolate(f, [0, n], [1, 1.04])})` }} />
        <div style={{ fontFamily: ANTON, fontSize: p.titre && p.titre.length > 16 ? 86 : 110, lineHeight: 1.02, color: "#fff", marginTop: 46, textAlign: "center",
          textTransform: "uppercase" }}>{p.titre}</div>
        {p.invites ? <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 34, color: "#fff", opacity: 0.85, marginTop: 14, textAlign: "center" }}>
          {Array.isArray(p.invites) ? "avec " + p.invites.join(", ") : p.invites}</div> : null}
        {p.chiffre ? <div style={{ fontFamily: MONT, fontWeight: 900, fontSize: 44, color: CIEL, marginTop: 26, textAlign: "center" }}>{p.chiffre}</div> : null}
        {p.morceau ? <div style={{ fontFamily: MONT, fontWeight: 700, fontSize: 28, color: "#fff", marginTop: 26, padding: "10px 24px", borderRadius: 999,
          background: "rgba(255,255,255,.14)" }}>♪ EN ÉCOUTE · {String(p.morceau).toUpperCase()}</div> : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// v3 : vrai ou faux (affirmation, puis verdict au temps v)
const Mythe: React.FC<{ m: any }> = ({ m }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(m.f) - fr(m.d);
  const o = useFondu(n, 6, 8);
  const v = fr(m.v - m.d);
  const s = spring({ frame: f - v, fps, config: { damping: 9, stiffness: 200 } });
  const vrai = String(m.verdict || "").toUpperCase().startsWith("VRAI");
  return (
    <div style={{ position: "absolute", top: 320, left: 70, right: 70, opacity: o }}>
      <div style={{ borderRadius: 36, padding: "40px 44px", background: "rgba(10,8,20,.72)", border: "2px solid rgba(255,255,255,.25)" }}>
        <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 28, letterSpacing: 8, color: OR }}>MYTHE OU RÉALITÉ ?</div>
        <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 44, color: "#fff", marginTop: 18, lineHeight: 1.2 }}>« {m.affirmation} »</div>
        {f >= v ? <div style={{ fontFamily: ANTON, fontSize: 110, marginTop: 20, color: vrai ? "#3ddc84" : "#ff4d6d", transform: `scale(${2 - s}) rotate(-5deg)`,
          transformOrigin: "left center" }}>{m.verdict}</div> : null}
      </div>
    </div>
  );
};

// enquête : pièce à conviction (polaroïd épinglé, tampon)
const Indice: React.FC<{ x: any }> = ({ x }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = fr(x.f) - fr(x.d);
  const s = spring({ frame: f, fps, config: { damping: 12, stiffness: 140 } });
  const o = interpolate(f, [n - 7, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", top: 300, left: 0, right: 0, display: "flex", justifyContent: "center", opacity: o }}>
      <div style={{ background: "#fff", padding: "26px 26px 30px", width: 700, transform: `rotate(${-6 + 3 * s}deg) scale(${0.7 + 0.3 * s})`,
        boxShadow: "0 30px 70px rgba(0,0,0,.6)", position: "relative" }}>
        <div style={{ position: "absolute", top: -22, left: "50%", width: 44, height: 44, marginLeft: -22, borderRadius: "50%",
          background: "radial-gradient(circle at 35% 35%, #ff6b6b, #a30f0f)" }} />
        {x.img ? <Img src={src(x.img)} style={{ width: "100%", height: 600, objectFit: "cover", filter: "sepia(.25) contrast(1.05)" }} /> : null}
        <div style={{ fontFamily: MACHINE, fontSize: 38, color: ENCRE, marginTop: 20 }}>{x.n ? `PIÈCE N°${x.n} · ` : ""}{x.titre}</div>
        {x.sous ? <div style={{ fontFamily: MONT, fontWeight: 600, fontSize: 28, color: "#444", marginTop: 6 }}>{x.sous}</div> : null}
        {x.tampon ? <div style={{ position: "absolute", right: 30, top: 80, fontFamily: ANTON, fontSize: 64, color: "rgba(200,20,40,.85)",
          border: "6px solid rgba(200,20,40,.85)", padding: "4px 20px", transform: `rotate(-14deg) scale(${f > 10 ? 1 : 1.6})`,
          opacity: f > 8 ? 1 : 0 }}>{x.tampon}</div> : null}
      </div>
    </div>
  );
};

// enquête : la route des villes, chaque ville s'allume quand la voix la dit
const Villes: React.FC<{ v: any }> = ({ v }) => {
  const f = useCurrentFrame();
  const n = fr(v.f) - fr(v.d);
  const o = useFondu(n, 8, 8);
  const liste: string[] = v.liste || [];
  const quand = (i: number) => (v.temps && v.temps[i] != null ? fr(v.temps[i]) : Math.round((i * (n - 30)) / Math.max(1, liste.length)));
  return (
    <div style={{ position: "absolute", top: 300, left: 80, right: 80, opacity: o }}>
      <div style={{ borderRadius: 36, padding: "40px 44px", background: "rgba(10,8,20,.72)", border: "2px solid rgba(255,255,255,.2)" }}>
        {liste.map((nom, i) => {
          const a = interpolate(f, [quand(i), quand(i) + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 26, opacity: 0.25 + 0.75 * a, transform: `translateX(${(1 - a) * -40}px)`,
              margin: "14px 0" }}>
              <div style={{ width: 34, height: 34, borderRadius: "50%", background: a > 0.5 ? MAGENTA : "#555", boxShadow: a > 0.5 ? `0 0 20px ${MAGENTA}` : "none" }} />
              <div style={{ fontFamily: ANTON, fontSize: 64, color: "#fff", textTransform: "uppercase" }}>{nom}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------------------------------------ sous-titres mot à mot
type Mot = { m: string; d: number; f: number };
const groupes = (mots: Mot[]) => {
  const out: Mot[][] = [];
  let cur: Mot[] = [];
  mots.forEach((m, i) => {
    const prec = mots[i - 1];
    if (cur.length && (cur.length >= 4 || (prec && m.d - prec.f > 0.35) || /[.!?…:;]$/.test(prec?.m || ""))) {
      out.push(cur);
      cur = [];
    }
    cur.push(m);
  });
  if (cur.length) out.push(cur);
  return out;
};

const SousTitres: React.FC<{ mots: Mot[]; caches: T[] }> = ({ mots, caches }) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  if (caches.some((c) => t >= c.d && t < c.f)) return null;
  const g = groupes(mots).find((x) => t >= x[0].d - 0.05 && t <= x[x.length - 1].f + 0.2);
  if (!g) return null;
  return (
    <div style={{ position: "absolute", left: 60, right: 60, top: 1330, textAlign: "center", lineHeight: 1.15 }}>
      {g.map((m, i) => {
        const actif = t >= m.d && t <= m.f + 0.05;
        return (
          <span key={i} style={{ fontFamily: MONT, fontWeight: 900, fontSize: 68, textTransform: "uppercase", margin: "0 10px", display: "inline-block",
            color: actif ? OR : "#fff", transform: `scale(${actif ? 1.08 : 1})`,
            textShadow: "0 0 3px #000, 0 4px 0 #000, 0 8px 24px rgba(0,0,0,.8)", WebkitTextStroke: "2px #000" }}>{m.m}</span>
        );
      })}
    </div>
  );
};

// ------------------------------------------------------------------------------------------------ fin, logo, barre
const Fin: React.FC<{ fin: any; n: number }> = ({ fin, n }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - 6, fps, config: { damping: 13, stiffness: 120 } });
  const o = interpolate(f, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "rgba(8,6,18,.6)", opacity: o, justifyContent: "flex-start", alignItems: "center", paddingTop: 360 }}>
      <Img src={staticFile("raconte/logo.png")} style={{ height: 150, marginBottom: 50, transform: `scale(${s})` }} />
      <div style={{ fontFamily: ANTON, fontSize: 130, color: "#fff", textAlign: "center", lineHeight: 1, transform: `translateY(${(1 - s) * 40}px)` }}>{fin.titre}</div>
      <div style={{ fontFamily: MONT, fontWeight: 800, fontSize: 40, color: OR, marginTop: 30, textAlign: "center", padding: "0 80px" }}>{fin.texte}</div>
    </AbsoluteFill>
  );
};

const Logo: React.FC = () => (
  <Img src={staticFile("raconte/logo.png")} style={{ position: "absolute", top: 70, right: 50, height: 70, opacity: 0.9,
    filter: "drop-shadow(0 4px 10px rgba(0,0,0,.6))" }} />
);

const Barre: React.FC<{ duree: number }> = ({ duree }) => {
  const f = useCurrentFrame();
  return <div style={{ position: "absolute", top: 0, left: 0, height: 8, width: `${(100 * f) / fr(duree)}%`,
    background: `linear-gradient(90deg, ${VIOLET}, ${MAGENTA})` }} />;
};

// ------------------------------------------------------------------------------------------------ son
const Musique: React.FC<{ m: any; fond: number }> = ({ m, fond }) => {
  const n = fr(m.f) - fr(m.d);
  const vol = m.plein ? 1 : m.vol ?? fond;
  return (
    <Audio src={src(m.src)} startFrom={fr(m.depuis || 0)}
      volume={(f) => vol * Math.min(interpolate(f, [0, 12], [0, 1], { extrapolateRight: "clamp" }),
        interpolate(f, [n - 15, n], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }))} />
  );
};

// ------------------------------------------------------------------------------------------------ la composition
export const CauriRaconte: React.FC<RaconteProps> = (p) => {
  const duree = p.duree || 10;
  const titres: any[] = [...(p.titresChapitre || []), ...(p.chapitres || [])];
  const debutChap = titres.length ? Math.min(...titres.map((c) => c.d)) : Math.min(6, duree);
  const fond = typeof p.fond === "number" ? p.fond : 0.2;
  const fin = p.fin && p.fin.d != null ? p.fin : null;
  // sous-titres cachés pendant les écrans plein cadre (titres, jauges) et quand l'artiste parle lui-même
  const caches: T[] = [...(p.extraits || []), ...titres.map((c) => ({ d: c.d, f: c.f })),
    ...(p.secrets || []).map((s: any) => ({ d: s.d, f: s.d + 2.6 })), ...(p.projets || []).map((x: any) => ({ d: x.d, f: x.f })),
    ...(fin ? [{ d: fin.d + 0.4, f: duree + 1 }] : [])];
  const musiques: any[] = p.musiques && p.musiques.length ? p.musiques
    : p.musique && p.musique !== p.voix ? [{ src: p.musique, d: 0, f: duree, depuis: 0, vol: fond }] : [];
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {(p.plans || []).map((x: any, i: number) => <Seq key={"p" + i} d={x.d} f={x.f} nom={"plan " + i}><Plan p={x} /></Seq>)}
      {(p.flashs || []).map((t: number, i: number) => <Seq key={"fl" + i} d={t} f={t + 0.15}><Flash /></Seq>)}
      <Voile />
      {p.titre ? <Seq d={0.3} f={Math.max(1.2, Math.min(debutChap, 4.6))}><Ouverture titre={p.titre} n={fr(Math.max(1.2, Math.min(debutChap, 4.6)) - 0.3)} /></Seq> : null}
      {(p.cartes || []).map((c: any, i: number) => <Seq key={"c" + i} d={c.d} f={c.f}><Carte c={c} /></Seq>)}
      {(p.contrats || []).map((c: any, i: number) => <Seq key={"k" + i} d={c.d} f={c.f}><Contrat c={c} /></Seq>)}
      {(p.mythes || []).map((m: any, i: number) => <Seq key={"my" + i} d={m.d} f={m.f}><Mythe m={m} /></Seq>)}
      {(p.indices || []).map((x: any, i: number) => <Seq key={"in" + i} d={x.d} f={x.f}><Indice x={x} /></Seq>)}
      {(p.villes || []).map((v: any, i: number) => <Seq key={"vi" + i} d={v.d} f={v.f}><Villes v={v} /></Seq>)}
      {(p.mascottes || []).map((m: any, i: number) => <Seq key={"m" + i} d={m.d} f={m.f}><Mascotte m={m} /></Seq>)}
      {(p.bulles || []).map((b: any, i: number) => <Seq key={"b" + i} d={b.d} f={b.f}><Bulle b={b} /></Seq>)}
      {(p.verites || []).map((v: any, i: number) => <Seq key={"v" + i} d={v.d} f={v.f}><Verite n={fr(v.f) - fr(v.d)} /></Seq>)}
      <SousTitres mots={p.mots || []} caches={caches} />
      {(p.projets || []).map((x: any, i: number) => <Seq key={"pr" + i} d={x.d} f={x.f}><Projet p={x} /></Seq>)}
      {titres.map((c: any, i: number) => <Seq key={"t" + i} d={c.d} f={c.f}><TitreChapitre c={c} /></Seq>)}
      {(p.secrets || []).map((s: any, i: number) => <Seq key={"s" + i} d={s.d} f={s.d + 2.6}><Jauge s={s} /></Seq>)}
      {fin ? <Seq d={fin.d + 0.4} f={duree}><Fin fin={fin} n={fr(duree - fin.d)} /></Seq> : null}
      <Logo />
      {p.sansBarre ? null : <Barre duree={duree} />}
      {p.voix ? <Audio src={src(p.voix)} /> : null}
      {musiques.map((m, i) => <Seq key={"mu" + i} d={m.d} f={m.f}><Musique m={m} fond={fond} /></Seq>)}
      {(p.sfx || []).map((x: any, i: number) => (
        <Seq key={"x" + i} d={x.d} f={x.d + (x.dur || 3)}><Audio src={src(x.src)} volume={x.vol ?? 0.3} /></Seq>
      ))}
    </AbsoluteFill>
  );
};
