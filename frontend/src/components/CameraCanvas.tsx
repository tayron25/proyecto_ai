import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { GameState, Target } from "../types";

type Props = {
  source: RefObject<HTMLVideoElement | null>;
  gameState: GameState | null;
};

const SOURCE_W = 640;
const SOURCE_H = 480;

type Viewport = {
  x: number;
  y: number;
  scale: number;
};

export function CameraCanvas({ source, gameState }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let stopped = false;

    const draw = () => {
      if (stopped) {
        return;
      }
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      const video = source.current;
      if (canvas && ctx) {
        const isBoxing = gameState?.state === "boxing";
        const isYoga = gameState?.state === "pose_challenge";
        const isAerobics = gameState?.state === "aerobics";
        const isMenu = gameState?.state === "menu";
        const yogaOk = Boolean(
          isYoga
          && gameState?.activity?.total
          && gameState.activity.met === gameState.activity.total,
        );
        const width = Math.max(1, Math.round(canvas.clientWidth || SOURCE_W));
        const height = Math.max(1, Math.round(canvas.clientHeight || SOURCE_H));
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
        }
        const viewport = getContainViewport(width, height);
        ctx.clearRect(0, 0, width, height);
        if (isMenu) {
          drawMenuPreviewStage(ctx, width, height);
        } else if (isBoxing) {
          drawBoxingStage(ctx, width, height);
        } else if (isYoga) {
          drawYogaStage(ctx, width, height);
        } else if (isAerobics) {
          drawAerobicsStage(ctx, width, height);
        } else if (video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          ctx.save();
          ctx.translate(viewport.x + SOURCE_W * viewport.scale, viewport.y);
          ctx.scale(-viewport.scale, viewport.scale);
          ctx.drawImage(video, 0, 0, SOURCE_W, SOURCE_H);
          ctx.restore();
        } else {
          ctx.fillStyle = "#050819";
          ctx.fillRect(0, 0, width, height);
        }
        drawSkeleton(ctx, gameState, viewport, isBoxing, isYoga, yogaOk, isAerobics, isMenu);
        gameState?.targets.forEach((target) => drawTarget(ctx, target, viewport));
        if (!isYoga && !isAerobics) {
          drawActivityPanel(ctx, gameState, width, height);
        }
        gameState?.messages.forEach((message) => {
          ctx.font = message.kind === "dodge" ? "700 36px Arial" : "700 24px Arial";
          ctx.textAlign = "center";
          ctx.lineWidth = 5;
          ctx.strokeStyle = "rgba(0,0,0,.75)";
          ctx.fillStyle = message.kind === "good" ? "#40f47c" : message.kind === "dodge" ? "#ff4c62" : "#ff4c62";
          const point = mapSourcePoint(message.x, message.y, viewport);
          ctx.strokeText(message.text, point.x, point.y);
          ctx.fillText(message.text, point.x, point.y);
        });
      }
      requestAnimationFrame(draw);
    };

    requestAnimationFrame(draw);
    return () => {
      stopped = true;
    };
  }, [gameState, source]);

  return <canvas ref={canvasRef} className="cameraCanvas" width={SOURCE_W} height={SOURCE_H} />;
}

function drawActivityPanel(ctx: CanvasRenderingContext2D, gameState: GameState | null, canvasW: number, canvasH: number) {
  const activity = gameState?.activity;
  if (!activity) {
    return;
  }

  const panelW = Math.min(300, Math.max(236, canvasW * 0.28));
  const panelH = Math.min(canvasH - 24, 456);
  const textW = panelW - 36;

  ctx.save();
  ctx.fillStyle = "rgba(4, 8, 20, 0.74)";
  ctx.strokeStyle = "rgba(255,255,255,.18)";
  ctx.lineWidth = 1;
  roundRect(ctx, 12, 12, panelW, panelH, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = activity.kind === "yoga" ? "#ff2d79" : "#9cff13";
  ctx.font = "700 20px Arial";
  ctx.fillText(activity.kind === "yoga" ? "YOGA" : "AEROBICOS", 26, 42);

  ctx.fillStyle = "#fff";
  ctx.font = "700 17px Arial";
  wrapText(ctx, activity.title, 26, 70, textW, 19);

  ctx.fillStyle = "rgba(255,255,255,.66)";
  ctx.font = "13px Arial";
  wrapText(ctx, activity.description, 26, 106, textW, 16);

  if (activity.kind === "yoga") {
    drawYogaActivity(ctx, activity);
  } else {
    drawAerobicsActivity(ctx, activity);
  }

  ctx.restore();
}

function drawYogaActivity(ctx: CanvasRenderingContext2D, activity: NonNullable<GameState["activity"]>) {
  const total = activity.total || 0;
  const met = activity.met || 0;
  ctx.fillStyle = activity.success ? "#40f47c" : "#ffb454";
  ctx.font = "700 15px Arial";
  ctx.fillText(`Condiciones ${met}/${total}`, 26, 170);
  if (activity.option) {
    ctx.fillText(`Opcion ${activity.option}`, 26, 194);
  }

  let y = 224;
  (activity.conditions || []).forEach((condition) => {
    ctx.fillStyle = condition.met ? "#40f47c" : "#ff4c62";
    ctx.font = "13px Arial";
    ctx.fillText(`${condition.met ? "OK" : "--"} ${condition.label}`, 26, y);
    y += 18;
  });

  drawProgress(ctx, 26, 420, 196, 14, activity.progress, "#ff2d79");
  ctx.fillStyle = "#ff2d79";
  ctx.font = "700 13px Arial";
  ctx.fillText(`MANTEN ${(activity.progress * 10).toFixed(1)}/10s`, 26, 408);
}

function drawAerobicsActivity(ctx: CanvasRenderingContext2D, activity: NonNullable<GameState["activity"]>) {
  let y = 174;
  (activity.labels || []).forEach((label) => {
    ctx.fillStyle = label.active ? "#40f47c" : "rgba(255,255,255,.45)";
    ctx.font = "14px Arial";
    ctx.fillText(`${label.active ? ">" : "-"} ${label.label}`, 26, y);
    y += 22;
  });

  if (activity.formOk !== null && activity.formOk !== undefined) {
    ctx.fillStyle = activity.formOk ? "#40f47c" : "#ff4c62";
    ctx.font = "700 14px Arial";
    ctx.fillText(activity.formOk ? "FORMA OK" : "AJUSTA CODOS", 26, y + 10);
  }

  const reps = activity.reps || 0;
  const target = activity.target || 1;
  ctx.fillStyle = activity.flash ? "#ffe45c" : "#9cff13";
  ctx.font = "700 16px Arial";
  ctx.fillText(`Reps: ${reps}/${target}`, 26, 408);
  drawProgress(ctx, 26, 420, 196, 14, activity.progress, "#9cff13");
}

function drawProgress(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  value: number,
  color: string,
) {
  ctx.fillStyle = "rgba(255,255,255,.14)";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w * Math.max(0, Math.min(value, 1)), h);
  ctx.strokeStyle = "rgba(255,255,255,.7)";
  ctx.strokeRect(x, y, w, h);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number) {
  const words = text.split(" ");
  let line = "";
  let yy = y;
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, yy);
      line = word;
      yy += lineHeight;
    } else {
      line = test;
    }
  });
  if (line) {
    ctx.fillText(line, x, yy);
  }
}

function getContainViewport(canvasW: number, canvasH: number): Viewport {
  const scale = Math.min(canvasW / SOURCE_W, canvasH / SOURCE_H);
  return {
    x: (canvasW - SOURCE_W * scale) / 2,
    y: (canvasH - SOURCE_H * scale) / 2,
    scale,
  };
}

function mapSourcePoint(x: number, y: number, viewport: Viewport) {
  return {
    x: viewport.x + x * viewport.scale,
    y: viewport.y + y * viewport.scale,
  };
}

function drawBoxingStage(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, "#111522");
  bg.addColorStop(0.58, "#080d16");
  bg.addColorStop(1, "#03070d");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.24;
  ctx.strokeStyle = "rgba(156,255,19,.12)";
  ctx.lineWidth = 1;
  for (let x = -height; x < width; x += 16) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + height, height);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "rgba(156,255,19,.85)";
  [0.12, 0.19, 0.32, 0.48, 0.61, 0.74, 0.86].forEach((x, index) => {
    const y = ((index * 0.17 + 0.08) % 0.8) + 0.08;
    ctx.beginPath();
    ctx.arc(width * x, height * y, index % 2 === 0 ? 2.5 : 1.8, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();

  ctx.fillStyle = "rgba(244,247,251,.22)";
  ctx.font = "700 11px Courier New";
  ctx.textAlign = "center";
  ctx.fillText("YOUR CAMERA FEED", width / 2, height * 0.38);
  ctx.fillText("MIRRORED", width / 2, height * 0.42);
}

function drawYogaStage(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, "#101522");
  bg.addColorStop(0.58, "#080d16");
  bg.addColorStop(1, "#03070d");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.22;
  ctx.strokeStyle = "rgba(255,45,121,.13)";
  ctx.lineWidth = 1;
  for (let x = -height; x < width; x += 16) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + height, height);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "rgba(255,45,121,.78)";
  [0.16, 0.28, 0.42, 0.55, 0.68, 0.82].forEach((x, index) => {
    const y = ((index * 0.19 + 0.14) % 0.74) + 0.08;
    ctx.beginPath();
    ctx.arc(width * x, height * y, index % 2 === 0 ? 2.3 : 1.7, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();

  ctx.fillStyle = "rgba(244,247,251,.22)";
  ctx.font = "700 11px Courier New";
  ctx.textAlign = "center";
  ctx.fillText("YOUR CAMERA FEED", width / 2, height * 0.38);
}

function drawAerobicsStage(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, "#141408");
  bg.addColorStop(0.58, "#0a0d07");
  bg.addColorStop(1, "#030502");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.23;
  ctx.strokeStyle = "rgba(246,255,0,.14)";
  ctx.lineWidth = 1;
  for (let x = -height; x < width; x += 16) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + height, height);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "rgba(246,255,0,.9)";
  [0.1, 0.22, 0.35, 0.49, 0.63, 0.77, 0.91].forEach((x, index) => {
    const y = ((index * 0.21 + 0.09) % 0.76) + 0.08;
    ctx.beginPath();
    ctx.arc(width * x, height * y, index % 2 === 0 ? 2.6 : 1.8, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();

  ctx.fillStyle = "rgba(244,247,251,.2)";
  ctx.font = "700 11px Courier New";
  ctx.textAlign = "center";
  ctx.fillText("YOUR CAMERA FEED", width / 2, height * 0.38);
  ctx.fillText("NEON CARDIO", width / 2, height * 0.42);
}

function drawMenuPreviewStage(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, "#101522");
  bg.addColorStop(0.58, "#080d16");
  bg.addColorStop(1, "#03070d");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.24;
  ctx.strokeStyle = "rgba(17,217,242,.14)";
  ctx.lineWidth = 1;
  for (let x = -height; x < width; x += 14) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + height, height);
    ctx.stroke();
  }
  ctx.restore();

  ctx.fillStyle = "rgba(244,247,251,.18)";
  ctx.font = "700 11px Courier New";
  ctx.textAlign = "center";
  ctx.fillText("YOUR CAMERA FEED", width / 2, height * 0.52);
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  gameState: GameState | null,
  viewport: Viewport,
  isBoxing = false,
  isYoga = false,
  yogaOk = false,
  isAerobics = false,
  isMenu = false,
) {
  if (!gameState || gameState.landmarks.length === 0) {
    return;
  }
  const neon = isBoxing || isYoga || isAerobics || isMenu;
  const skeletonColor = isBoxing
    ? "rgba(156,255,19,.86)"
    : isYoga
      ? yogaOk ? "rgba(17,217,242,.9)" : "rgba(255,45,121,.86)"
      : isAerobics
        ? "rgba(246,255,0,.92)"
        : isMenu
          ? "rgba(17,217,242,.9)"
        : "rgba(255,255,255,.85)";
  const glowColor = isBoxing
    ? "rgba(156,255,19,.72)"
    : isYoga
      ? yogaOk ? "rgba(17,217,242,.78)" : "rgba(255,45,121,.72)"
      : isAerobics
        ? "rgba(246,255,0,.72)"
        : isMenu
          ? "rgba(17,217,242,.7)"
        : "transparent";
  ctx.lineWidth = neon ? 2.5 : 3;
  ctx.strokeStyle = skeletonColor;
  ctx.shadowColor = glowColor;
  ctx.shadowBlur = neon ? 10 : 0;
  gameState.connections.forEach(([startIndex, endIndex]) => {
    const pa = gameState.landmarks[startIndex];
    const pb = gameState.landmarks[endIndex];
    if (!pa || !pb || pa.visibility < 0.3 || pb.visibility < 0.3) {
      return;
    }
    ctx.beginPath();
    const start = mapSourcePoint(pa.x * SOURCE_W, pa.y * SOURCE_H, viewport);
    const end = mapSourcePoint(pb.x * SOURCE_W, pb.y * SOURCE_H, viewport);
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  });
  ctx.shadowBlur = neon ? 18 : 0;
  ctx.fillStyle = isBoxing ? "#9cff13" : isYoga ? yogaOk ? "#11d9f2" : "#ff2d79" : isAerobics ? "#f6ff00" : isMenu ? "#11d9f2" : "#46f0d1";
  gameState.landmarks.forEach((lm) => {
    if (lm.visibility < 0.3) {
      return;
    }
    const point = mapSourcePoint(lm.x * SOURCE_W, lm.y * SOURCE_H, viewport);
    ctx.beginPath();
    ctx.arc(point.x, point.y, Math.max(4, viewport.scale * 4), 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.shadowBlur = 0;
}

function drawTarget(ctx: CanvasRenderingContext2D, target: Target, viewport: Viewport) {
  const [b, g, r] = target.color;
  const warning = target.hit ? 0 : target.lifeRatio <= 0.3 ? 1 - target.lifeRatio / 0.3 : 0;
  const drawB = Math.round(b * (1 - warning));
  const drawG = Math.round(g * (1 - warning));
  const drawR = Math.round(r + (255 - r) * warning);
  const color = `rgb(${drawR}, ${drawG}, ${drawB})`;
  const point = mapSourcePoint(target.x, target.y, viewport);
  const entryScale = target.entryScale ?? 1;
  const radius = Math.max(1, target.radius * entryScale * viewport.scale);
  ctx.save();
  ctx.globalAlpha = target.hit ? 0.55 : 1;
  ctx.fillStyle = color;
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  if (!target.hit && entryScale >= 1) {
    ctx.fillStyle = "#fff";
    ctx.font = `700 ${Math.max(17, viewport.scale * 17)}px Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(0,0,0,.7)";
    ctx.strokeText(target.label, point.x, point.y);
    ctx.fillText(target.label, point.x, point.y);
  }
  ctx.restore();
}
