// Atelier vidéo du Cauri Studio : les compositions que Python rend avec « npx remotion render src/index.ts <Nom> ».
import React from "react";
import { Composition } from "remotion";
import { CauriRaconte } from "./CauriRaconte";
import { CauriGuide, dureeGuide } from "./CauriGuide";

const DEMO = { duree: 6, titre: { haut: "LA LÉGENDE DE", nom: "CAURI CHARTS", bas: "" }, mots: [], plans: [], sansBarre: true,
  fin: { d: 3.5, titre: "TA LÉGENDE ?", texte: "Écris-la en commentaire : prochain épisode" } };

export const Racine: React.FC = () => (
  <>
    <Composition id="CauriRaconte" component={CauriRaconte as any} width={1080} height={1920} fps={30} durationInFrames={180}
      defaultProps={DEMO as any}
      calculateMetadata={({ props }: any) => ({ durationInFrames: Math.max(30, Math.round((props.duree || 6) * 30)) })} />
    <Composition id="CauriGuide" component={CauriGuide as any} width={1080} height={1920} fps={30} durationInFrames={300}
      defaultProps={{ duree: 10, voix: [], mots: [], segs: [], extrait: null, fond: "", fin: { d: 9 } } as any}
      calculateMetadata={({ props }: any) => ({ durationInFrames: Math.max(30, dureeGuide(props)) })} />
  </>
);