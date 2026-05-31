import type { CSSProperties } from "react";
import type { GameState } from "../types";

type Props = {
  state: GameState["state"];
  activity?: GameState["activity"];
  module: NonNullable<GameState["module"]>;
  video: string | null;
  remaining: number;
};

export function ExerciseTransition({ state, activity, module, video, remaining }: Props) {
  const content = getTransitionContent(state, module.index, activity);
  const progress = Math.max(0, Math.min(1, remaining / 5));
  const isBoxing = state === "boxing";
  const isYoga = state === "pose_challenge";
  const isAerobics = state === "aerobics";

  return (
    <div className={`exerciseTransition ${isBoxing ? "boxingStart" : ""} ${isYoga ? "yogaStart" : ""} ${isAerobics ? "aerobicsStart" : ""}`}>
      <div className="transitionSkeleton" aria-hidden="true">
        <span />
        <i />
        <i />
        <b />
        <b />
      </div>

      <div className="transitionHeader">
        <span>{isAerobics ? "INICIO - 60S" : `NEXT EXERCISE - ${module.index + 1} / ${module.total}`}</span>
        <h2>{content.title}</h2>
        <p>{content.description}</p>
      </div>

      <div className="countdownRing" style={{ "--progress": progress } as CSSProperties}>
        <strong>{remaining}</strong>
      </div>

      <aside className="transitionPreview">
        <span>PREVIEW - 5S</span>
        {video ? <video src={video} muted playsInline loop autoPlay /> : <div />}
        <footer>
          <i>{content.difficulty}</i>
          <b>{content.hits}</b>
        </footer>
      </aside>

      <div className="transitionCue">{content.cue}</div>
    </div>
  );
}

function getTransitionContent(state: GameState["state"], index: number, activity?: GameState["activity"]) {
  if (state === "pose_challenge") {
    return {
      title: activity?.title ?? "YOGA",
      description: activity?.description ?? "Prepara tu postura y manten el equilibrio.",
      cue: "RESPIRA PROFUNDO - ALINEA TU POSTURA",
      difficulty: `POSTURA - ${index + 1}`,
      hits: "10S HOLD",
    };
  }

  if (state === "aerobics") {
    return {
      title: "NO PARES HASTA EL FINAL",
      description: "Una rutina, 60 segundos. Sigue el ritmo y mantente en movimiento.",
      cue: "RESPIRA - MANTEN EL RITMO - AGUANTA",
      difficulty: "RUTINA - 1/1",
      hits: "60S",
    };
  }

  return boxingExerciseCopy[index] ?? boxingExerciseCopy[0];
}

const boxingExerciseCopy = [
  {
    title: "JAB + CROSS",
    description: "Golpea alternando derecha e izquierda. Manten la guardia alta y vuelve al centro.",
    cue: "PREPARA TU POSTURA - MANTEN LA GUARDIA ALTA",
    difficulty: "DIFICULTAD - 2/5",
    hits: "8 HITS",
  },
  {
    title: "HOOK COMBO",
    description: "Gancho izquierdo y gancho derecho. Rota la cadera y no bajes los codos.",
    cue: "ROTA LA CADERA - MANTEN LA GUARDIA ALTA",
    difficulty: "DIFICULTAD - 3/5",
    hits: "8 HITS",
  },
  {
    title: "UPPERCUTS",
    description: "Sube los punos desde la guardia. Usa piernas y core para impulsar el golpe.",
    cue: "FLEXIONA SUAVE - SUBE EL GOLPE",
    difficulty: "DIFICULTAD - 3/5",
    hits: "6 HITS",
  },
  {
    title: "JAB CROSS + ESQUIVA",
    description: "Combina golpes rectos y agachate cuando aparezca la senal de esquiva.",
    cue: "MIRA LA SENAL - ESQUIVA A TIEMPO",
    difficulty: "DIFICULTAD - 4/5",
    hits: "10 HITS",
  },
  {
    title: "COMBOS MIXTOS",
    description: "Encadena golpes y esquivas. Manten ritmo, postura y precision hasta el final.",
    cue: "RESPIRA - NO PIERDAS EL RITMO",
    difficulty: "DIFICULTAD - 5/5",
    hits: "12 HITS",
  },
];
