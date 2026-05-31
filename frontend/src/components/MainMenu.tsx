import { useState } from "react";

type MenuButton = {
  label: string;
  action: string;
  rect: [number, number, number, number];
  hovered: boolean;
};

type Props = {
  menu: {
    title: string;
    hint: string;
    clapRatio: number;
    hoveredIndex: number;
    buttons: MenuButton[];
    wrists: { x: number; y: number }[];
  } | null;
  onSelectAction: (action: string) => void;
};

export function MainMenu({ menu, onSelectAction }: Props) {
  const buttons = menu?.buttons ?? fallbackButtons;
  const [logoReady, setLogoReady] = useState(true);

  return (
    <div className="mainMenu">
      <div className="menuLogo" aria-label="NeoFit">
        {logoReady && (
          <img
            src="/assets/images/logo/neofit-logo-transparent.png"
            alt=""
            onError={() => setLogoReady(false)}
          />
        )}
        {!logoReady && (
          <>
            <span />
            <strong>NeoFit</strong>
            <small>MOVEMENT AI</small>
          </>
        )}
      </div>
      <div className="menuKicker">MEDIAPIPE + POSE TRACKING ACTIVE</div>
      <h1>Tu cuerpo es<br />el mando.</h1>
      <p>Tres disciplinas, una camara. Elige tu entrenamiento y deja que la IA puntue cada movimiento en tiempo real.</p>

      <div className="menuPlane">
        {menu?.wrists.map((wrist, index) => (
          <span
            key={`${wrist.x}-${wrist.y}-${index}`}
            className="menuWrist"
            style={{ left: `${(wrist.x / 640) * 100}%`, top: `${(wrist.y / 480) * 100}%` }}
          />
        ))}

        {buttons.map((button, index) => {
          const [x, y, w, h] = button.rect;
          const ratio = index === menu?.hoveredIndex ? Math.max(menu.clapRatio, 0.01) : 0;
          const meta = menuMeta[button.action] ?? menuMeta.boxing;

          return (
            <button
              key={button.action}
              type="button"
              className={`menuDiscipline ${button.hovered ? "hovered" : ""}`}
              style={{
                left: `${(x / 640) * 100}%`,
                top: `${(y / 600) * 100}%`,
                width: `${(w / 640) * 100}%`,
                height: `${(h / 480) * 100}%`,
              }}
              onClick={() => onSelectAction(button.action)}
            >
              <span>{button.label}</span>
              <em>{meta.summary}</em>
              <strong>{meta.tags}</strong>
              {ratio > 0 && <i style={{ transform: `scaleX(${ratio})` }} />}
            </button>
          );
        })}
      </div>

      {menu?.clapRatio ? (
        <div className="clapProgress">
          <span style={{ transform: `scaleX(${menu.clapRatio})` }} />
          <strong>APLAUDE!</strong>
        </div>
      ) : null}
    </div>
  );
}

const fallbackButtons: MenuButton[] = [
  { label: "BOX", action: "boxing", rect: [28, 326, 180, 130], hovered: false },
  { label: "YOGA", action: "pose_challenge", rect: [230, 326, 180, 130], hovered: false },
  { label: "AEROBICO", action: "aerobics", rect: [432, 326, 180, 130], hovered: false },
];

const menuMeta: Record<string, { summary: string; tags: string }> = {
  boxing: {
    summary: "5 combos · 10s c/u",
    tags: "VELOCIDAD · POTENCIA · PRECISION",
  },
  pose_challenge: {
    summary: "5 posturas · 10s hold",
    tags: "EQUILIBRIO · FLEXIBILIDAD · RESPIRACION",
  },
  aerobics: {
    summary: "1 rutina · 60s",
    tags: "RITMO · RESISTENCIA · ENERGIA",
  },
};
