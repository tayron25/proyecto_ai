import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { CameraCanvas } from "./components/CameraCanvas";
import { ExerciseTransition } from "./components/ExerciseTransition";
import { MainMenu } from "./components/MainMenu";
import { TrainerVideo } from "./components/TrainerVideo";
import { useCamera } from "./hooks/useCamera";
import { useGameSocket } from "./hooks/useGameSocket";
import type { BoxingModuleResult, ClientCommand, YogaPoseResult } from "./types";

const CAPTURE_W = 640;
const CAPTURE_H = 480;
const PREP_SECONDS = 5;
const AEROBICS_AUDIO_SRC = "/assets/audio/aerobics/aerobics.mp3";
const AEROBICS_COUNTDOWN_AUDIO_SRC = "/assets/audio/aerobics/aerobics-countdown.mp3";
const BOXING_AUDIO_SRC = "/assets/audio/boxing/boxing.mp3";
const CELEBRATION_AUDIO_SRC = "/assets/audio/celebration/celebration.mp3";
const MENU_AUDIO_SRC = "/assets/audio/menu/menu.mp3";
const YOGA_AUDIO_SRC = "/assets/audio/yoga/yoga.mp3";
const AEROBICS_WAVE_BARS = 64;
const AEROBICS_WAVE_PATTERN = [0.34, 0.62, 0.86, 1, 0.82, 0.42, 0.28, 0.7, 0.92, 0.76, 0.36, 0.52];

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "00:00";
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export default function App() {
  const { videoRef, streamReady, error } = useCamera();
  const trainerVideoRef = useRef<HTMLVideoElement | null>(null);
  const aerobicsAudioRef = useRef<HTMLAudioElement | null>(null);
  const aerobicsCountdownAudioRef = useRef<HTMLAudioElement | null>(null);
  const boxingAudioRef = useRef<HTMLAudioElement | null>(null);
  const celebrationAudioRef = useRef<HTMLAudioElement | null>(null);
  const menuAudioRef = useRef<HTMLAudioElement | null>(null);
  const yogaAudioRef = useRef<HTMLAudioElement | null>(null);
  const lastCelebrationKeyRef = useRef<string | null>(null);
  const { connected, gameState, sendFrame, sendCommand, selectGame } = useGameSocket();
  const [lastCommand, setLastCommand] = useState<ClientCommand | null>(null);
  const [prep, setPrep] = useState<{ key: string; remaining: number; active: boolean } | null>(null);
  const [boxingResult, setBoxingResult] = useState<BoxingModuleResult | null>(null);
  const [celebrationEnded, setCelebrationEnded] = useState(false);
  const [yogaPoseResult, setYogaPoseResult] = useState<YogaPoseResult | null>(null);
  const [aerobicsAudio, setAerobicsAudio] = useState({ current: 0, duration: 0 });
  const [cameraFps, setCameraFps] = useState(0);
  const preparedKeyRef = useRef<string | null>(null);
  const lastBoxingResultRef = useRef<string | null>(null);
  const lastYogaPoseResultRef = useRef<string | null>(null);
  const isPlaying = gameState?.state === "boxing" || gameState?.state === "pose_challenge" || gameState?.state === "aerobics";
  const isBoxing = gameState?.state === "boxing";
  const isYoga = gameState?.state === "pose_challenge";
  const isAerobics = gameState?.state === "aerobics";
  const hasBoxingSummary = Boolean(isBoxing && gameState?.nextState === "summary" && gameState?.boxing?.summary);
  const hasYogaSummary = Boolean(isYoga && gameState?.nextState === "summary" && gameState?.yoga?.summary);
  const isAerobicsSummary = Boolean(isAerobics && gameState?.nextState === "summary" && gameState?.aerobics?.summary);
  const isShowingBoxingResult = Boolean(boxingResult);
  const pendingBoxingResult = Boolean(
    isBoxing
    && gameState?.boxing?.lastResult
    && lastBoxingResultRef.current !== gameState.boxing.lastResult.id,
  );
  const pendingYogaPoseResult = Boolean(
    isYoga
    && gameState?.yoga?.poseResult
    && lastYogaPoseResultRef.current !== gameState.yoga.poseResult.id,
  );
  const isBoxingSummary = Boolean(hasBoxingSummary && !boxingResult && !pendingBoxingResult);
  const isYogaSummary = Boolean(hasYogaSummary && !yogaPoseResult && !pendingYogaPoseResult);
  const isMenu = !gameState || gameState.state === "menu";
  const isSummary = isBoxingSummary || isYogaSummary || isAerobicsSummary;
  const summaryClapRatio = Math.max(0, Math.min(gameState?.summaryClap?.ratio ?? 0, 1));
  const isPreparing = Boolean(prep?.active && isPlaying);
  const isPausedOverlay = isPreparing || isShowingBoxingResult || pendingBoxingResult || isBoxingSummary || Boolean(yogaPoseResult) || pendingYogaPoseResult || isYogaSummary || isAerobicsSummary;

  const dispatchCommand = useCallback(
    (command: ClientCommand, videoTime = 0) => {
      setLastCommand(command);
      sendCommand(command, videoTime);
    },
    [sendCommand],
  );

  useEffect(() => {
    if (!streamReady) {
      setCameraFps(0);
      return;
    }

    const video = videoRef.current;
    if (!video) {
      setCameraFps(0);
      return;
    }

    let stopped = false;
    let rafId = 0;
    let lastTime = performance.now();
    let lastFrames = video.getVideoPlaybackQuality?.().totalVideoFrames ?? 0;
    let fallbackFrames = 0;

    const updateFromQuality = () => {
      if (stopped) {
        return;
      }
      const now = performance.now();
      const quality = video.getVideoPlaybackQuality?.();
      if (quality) {
        const frameDelta = quality.totalVideoFrames - lastFrames;
        const timeDelta = now - lastTime;
        if (timeDelta >= 500) {
          setCameraFps(Math.max(0, Math.round((frameDelta * 1000) / timeDelta)));
          lastFrames = quality.totalVideoFrames;
          lastTime = now;
        }
      } else {
        fallbackFrames += 1;
        const timeDelta = now - lastTime;
        if (timeDelta >= 500) {
          setCameraFps(Math.max(0, Math.round((fallbackFrames * 1000) / timeDelta)));
          fallbackFrames = 0;
          lastTime = now;
        }
      }
      rafId = requestAnimationFrame(updateFromQuality);
    };

    rafId = requestAnimationFrame(updateFromQuality);
    return () => {
      stopped = true;
      cancelAnimationFrame(rafId);
    };
  }, [streamReady, videoRef]);

  useEffect(() => {
    if (!streamReady || !connected) {
      return;
    }

    const capture = document.createElement("canvas");
    capture.width = CAPTURE_W;
    capture.height = CAPTURE_H;
    const ctx = capture.getContext("2d");
    let stopped = false;
    let lastSent = 0;

    const loop = (now: number) => {
      if (stopped) {
        return;
      }
      const video = videoRef.current;
      if (ctx && video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && now - lastSent > 80) {
        ctx.save();
        ctx.scale(-1, 1);
        ctx.drawImage(video, -CAPTURE_W, 0, CAPTURE_W, CAPTURE_H);
        ctx.restore();
        sendFrame(capture.toDataURL("image/jpeg", 0.62), trainerVideoRef.current?.currentTime ?? 0, isPausedOverlay);
        lastSent = now;
      }
      requestAnimationFrame(loop);
    };

    requestAnimationFrame(loop);
    return () => {
      stopped = true;
    };
  }, [connected, isPausedOverlay, sendFrame, streamReady, videoRef]);

  useEffect(() => {
    const audio = menuAudioRef.current;
    if (!audio) {
      return;
    }

    const shouldPlay = isMenu || (isSummary && celebrationEnded);
    if (shouldPlay) {
      void audio.play().catch(() => undefined);
    } else {
      audio.pause();
    }
  }, [celebrationEnded, isMenu, isSummary]);

  useEffect(() => {
    const audio = aerobicsAudioRef.current;
    if (!audio) {
      return;
    }

    if (!isAerobics) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }

    const videoTime = trainerVideoRef.current?.currentTime ?? 0;
    if (Number.isFinite(videoTime) && Math.abs(audio.currentTime - videoTime) > 0.6) {
      audio.currentTime = videoTime;
    }

    if (isPlaying && !isPausedOverlay) {
      void audio.play().catch(() => undefined);
    } else {
      audio.pause();
    }
  }, [gameState?.video, isAerobics, isPausedOverlay, isPlaying]);

  useEffect(() => {
    const audio = aerobicsCountdownAudioRef.current;
    if (!audio) {
      return;
    }

    if (!isAerobics || !prep?.active) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }

    audio.currentTime = 0;
    void audio.play().catch(() => undefined);

    return () => {
      audio.pause();
      audio.currentTime = 0;
    };
  }, [isAerobics, prep?.active, prep?.key]);

  useEffect(() => {
    const audio = boxingAudioRef.current;
    if (!audio) {
      return;
    }

    if (!isBoxing) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }

    if (isBoxingSummary) {
      audio.pause();
      return;
    }

    void audio.play().catch(() => undefined);
  }, [isBoxing, isBoxingSummary]);

  useEffect(() => {
    const audio = yogaAudioRef.current;
    if (!audio) {
      return;
    }

    if (!isYoga) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }

    if (isYogaSummary) {
      audio.pause();
      return;
    }

    void audio.play().catch(() => undefined);
  }, [isYoga, isYogaSummary]);

  useEffect(() => {
    const summaryKey = isBoxingSummary
      ? "boxing"
      : isYogaSummary
        ? "yoga"
        : isAerobicsSummary
          ? "aerobics"
          : null;
    const audio = celebrationAudioRef.current;
    if (!audio) {
      return;
    }
    if (!summaryKey) {
      lastCelebrationKeyRef.current = null;
      setCelebrationEnded(false);
      audio.pause();
      audio.currentTime = 0;
      return;
    }
    if (lastCelebrationKeyRef.current === summaryKey) {
      return;
    }
    lastCelebrationKeyRef.current = summaryKey;
    setCelebrationEnded(false);
    audio.currentTime = 0;
    void audio.play().catch(() => setCelebrationEnded(true));
  }, [isAerobicsSummary, isBoxingSummary, isYogaSummary]);

  useEffect(() => {
    const audio = aerobicsAudioRef.current;
    if (!audio || !isAerobics) {
      setAerobicsAudio({ current: 0, duration: 0 });
      return;
    }

    let stopped = false;
    const update = () => {
      if (stopped) {
        return;
      }
      setAerobicsAudio({
        current: Number.isFinite(audio.currentTime) ? audio.currentTime : 0,
        duration: Number.isFinite(audio.duration) ? audio.duration : 0,
      });
      requestAnimationFrame(update);
    };

    update();
    return () => {
      stopped = true;
    };
  }, [isAerobics]);

  useEffect(() => {
    if (isShowingBoxingResult || pendingBoxingResult || yogaPoseResult || pendingYogaPoseResult) {
      return;
    }
    if (!isPlaying || !gameState?.module || !gameState.video) {
      preparedKeyRef.current = null;
      setPrep(null);
      return;
    }

    const key = gameState.state === "aerobics"
      ? `${gameState.state}-${gameState.video}`
      : `${gameState.state}-${gameState.module.index}-${gameState.video}`;
    if (preparedKeyRef.current === key || prep?.key === key) {
      return;
    }

    trainerVideoRef.current?.pause();
    if (trainerVideoRef.current) {
      trainerVideoRef.current.currentTime = 0;
    }
    setPrep({ key, remaining: PREP_SECONDS, active: true });
  }, [gameState?.state, gameState?.module, gameState?.video, isPlaying, isShowingBoxingResult, pendingBoxingResult, yogaPoseResult, pendingYogaPoseResult, prep?.key]);

  useEffect(() => {
    if (!prep?.active) {
      return;
    }

    if (prep.remaining <= 0) {
      preparedKeyRef.current = prep.key;
      setPrep({ ...prep, active: false });
      return;
    }

    const timer = window.setTimeout(() => {
      setPrep((current) => current ? { ...current, remaining: current.remaining - 1 } : current);
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [prep]);

  useEffect(() => {
    const result = gameState?.boxing?.lastResult;
    if (!isBoxing || !result || lastBoxingResultRef.current === result.id) {
      return;
    }
    lastBoxingResultRef.current = result.id;
    setBoxingResult(result);
    const timer = window.setTimeout(() => {
      setBoxingResult(null);
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [gameState?.boxing?.lastResult?.id, isBoxing]);

  useEffect(() => {
    const result = gameState?.yoga?.poseResult;
    if (!isYoga || !result || lastYogaPoseResultRef.current === result.id) {
      return;
    }
    lastYogaPoseResultRef.current = result.id;
    setYogaPoseResult(result);
    const timer = window.setTimeout(() => {
      setYogaPoseResult(null);
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [gameState?.yoga?.poseResult?.id, isYoga]);

  const replayBoxing = useCallback(() => {
    preparedKeyRef.current = null;
    lastBoxingResultRef.current = null;
    setBoxingResult(null);
    dispatchCommand("reset");
  }, [dispatchCommand]);

  const exitToMenu = useCallback(() => {
    preparedKeyRef.current = null;
    lastBoxingResultRef.current = null;
    lastYogaPoseResultRef.current = null;
    setBoxingResult(null);
    setYogaPoseResult(null);
    dispatchCommand("menu");
  }, [dispatchCommand]);

  const replayCurrent = useCallback(() => {
    preparedKeyRef.current = null;
    lastBoxingResultRef.current = null;
    lastYogaPoseResultRef.current = null;
    setBoxingResult(null);
    setYogaPoseResult(null);
    dispatchCommand("reset");
  }, [dispatchCommand]);

  const summaryClapPrompt = isSummary ? (
    <div className="summaryClapPrompt">
      <span>Aplaude {gameState?.summaryClap?.holdSeconds?.toFixed(1) ?? "3.5"}s para volver al menu</span>
      <i aria-hidden="true">
        <b style={{ transform: `scaleX(${summaryClapRatio})` }} />
      </i>
    </div>
  ) : null;

  return (
    <main className={`appShell ${isPlaying ? "playMode" : "menuMode"} ${isBoxing ? "boxingMode" : ""} ${isYoga ? "yogaMode" : ""} ${isAerobics ? "aerobicsMode" : ""}`}>
      <div className="cameraFpsBadge">CAM {cameraFps || "--"} FPS</div>
      <audio ref={aerobicsAudioRef} src={AEROBICS_AUDIO_SRC} preload="auto" />
      <audio ref={aerobicsCountdownAudioRef} src={AEROBICS_COUNTDOWN_AUDIO_SRC} preload="auto" />
      <audio ref={boxingAudioRef} src={BOXING_AUDIO_SRC} preload="auto" loop />
      <audio ref={celebrationAudioRef} src={CELEBRATION_AUDIO_SRC} preload="auto" onEnded={() => setCelebrationEnded(true)} />
      <audio ref={menuAudioRef} src={MENU_AUDIO_SRC} preload="auto" loop />
      <audio ref={yogaAudioRef} src={YOGA_AUDIO_SRC} preload="auto" loop />
      <section className="trainerPane">
        <TrainerVideo
          ref={trainerVideoRef}
          src={gameState?.video ?? null}
          playing={isPlaying && !isPausedOverlay}
          onEnded={() => dispatchCommand("videoEnded", trainerVideoRef.current?.currentTime ?? 0)}
        />
      </section>

      <section className="gamePane">
        <video ref={videoRef} className="cameraSource" playsInline muted />
        <CameraCanvas source={videoRef} gameState={gameState} />

        {isMenu && (
          <>
            <MainMenu menu={gameState?.menu ?? null} onSelectAction={(action) => selectGame(action)} />
            <div className="menuPosePreview">
              <span>WEBCAM LIVE · POSE TRACKING</span>
              <CameraCanvas source={videoRef} gameState={gameState} />
            </div>
          </>
        )}

        <div className="topBar">
          <span className={connected ? "status ok" : "status"}>{connected ? "Pose activa" : "Conectando backend"}</span>
          <span>FPS {gameState?.fps ?? 0}</span>
          <span>Score {gameState?.score ?? 0}</span>
        </div>

        <div className="actions">
          <button type="button" onClick={exitToMenu}>Menu</button>
          <button type="button" onClick={() => dispatchCommand("reset")}>Reset</button>
        </div>

        {gameState?.module && (
          <div className="moduleBadge">
            <strong>{gameState.module.name}</strong>
            <span>Modulo {gameState.module.index + 1}/{gameState.module.total}</span>
          </div>
        )}

        {isBoxing && gameState?.module && (
          <div className="boxingHud">
            <div className="boxingHudCenter">
              <b>x{gameState.boxing?.combo ?? 0}</b>
              <span>COMBO</span>
            </div>
            <div className="boxingHudRight">
              <span>PRECISION</span>
              <strong>{gameState.boxing?.percent ?? 0}%</strong>
            </div>
            <i style={{ transform: `scaleX(${Math.max(0, Math.min((gameState.boxing?.percent ?? 0) / 100, 1))})` }} />
          </div>
        )}

        {isYoga && gameState?.activity && (
          <div className="yogaHud">
            <div className="yogaHudLeft">
              <strong>{(Math.max(0, Math.min(gameState.activity.progress, 1)) * 10).toFixed(1)}</strong>
              <span>/ 10.0s</span>
            </div>
            <div className="yogaHudRight">
              <span>ESTABILIDAD</span>
              <strong>
                {gameState.activity.success
                  ? "EXCELENTE"
                  : gameState.activity.total && gameState.activity.met === gameState.activity.total
                    ? "MANTEN"
                    : "AJUSTA"}
              </strong>
            </div>
            <div className="yogaHudCenter">
              <b>{gameState.yoga?.points ?? 0}</b>
              <span>PUNTOS</span>
            </div>
            <i style={{ transform: `scaleX(${Math.max(0, Math.min(gameState.activity.progress, 1))})` }} />
          </div>
        )}

        {isAerobics && gameState?.activity && (
          <div className="aerobicsHud">
            <div className="aerobicsHudTitle">
              <strong>{gameState.activity.title}</strong>
              <span>FLOW ACTIVO</span>
            </div>
            <div className="aerobicsHudMeter">
              <b>{String(gameState.activity.reps ?? 0).padStart(2, "0")}</b>
              <span>/ {gameState.activity.target ?? 0} reps</span>
            </div>
            <div className="aerobicsHudMatch">
              <span>ENERGIA</span>
              <strong>{Math.round(Math.max(0, Math.min(gameState.activity.progress, 1)) * 100)}%</strong>
            </div>
            <div className="aerobicsWave" aria-hidden="true">
              <small>{formatTime(aerobicsAudio.current)}</small>
              <div>
                {Array.from({ length: AEROBICS_WAVE_BARS }).map((_, index) => {
                  const ratio = aerobicsAudio.duration > 0 ? aerobicsAudio.current / aerobicsAudio.duration : 0;
                  return (
                    <i
                      key={index}
                      className={(index + 1) / AEROBICS_WAVE_BARS <= ratio ? "active" : ""}
                      style={{ "--wave": AEROBICS_WAVE_PATTERN[index % AEROBICS_WAVE_PATTERN.length] } as CSSProperties}
                    />
                  );
                })}
              </div>
              <small>{formatTime(aerobicsAudio.duration)}</small>
            </div>
            <div className="aerobicsProgressTrack" aria-hidden="true">
              {Array.from({ length: 36 }).map((_, index) => (
                <i key={index} />
              ))}
            </div>
            <em style={{ transform: `scaleX(${Math.max(0, Math.min(gameState.activity.progress, 1))})` }} />
          </div>
        )}

        {isAerobicsSummary && gameState?.aerobics?.summary && (
          <div className="aerobicsSummaryOverlay">
            <span>RUTINA COMPLETA</span>
            <h2>{gameState.aerobics.summary.message}</h2>
            <strong>{gameState.aerobics.summary.percent}%</strong>
            <p>{gameState.aerobics.summary.reps}/{gameState.aerobics.summary.target} pasos completados</p>
            <div className="aerobicsSummaryGrid">
              {gameState.aerobics.summary.results.map((result) => (
                <article key={result.id}>
                  <div>
                    <small>{result.name}</small>
                    <b>{result.reps}/{result.target}</b>
                  </div>
                  <i>
                    <span style={{ transform: `scaleX(${Math.max(0, Math.min(result.percent / 100, 1))})` }} />
                  </i>
                  <em>{result.percent}%</em>
                </article>
              ))}
            </div>
            {summaryClapPrompt}
          </div>
        )}

        {yogaPoseResult && (
          <div className="yogaResultOverlay">
            <span>MODULO {yogaPoseResult.index + 1}</span>
            <h2>{yogaPoseResult.message}</h2>
            <strong>{yogaPoseResult.percent}%</strong>
            <b className="yogaModulePoints">{yogaPoseResult.points}/{yogaPoseResult.maxPoints} PUNTOS</b>
            <p>{yogaPoseResult.name}</p>
            <div className="yogaSideScores">
              {yogaPoseResult.options.map((option) => (
                <em key={option.id}>
                  Lado {option.option}: {option.points}/{option.maxPoints} pts
                </em>
              ))}
            </div>
            <small>PORCENTAJE DEL MODULO - respira, integra y continua</small>
          </div>
        )}

        {isYogaSummary && gameState?.yoga?.summary && (
          <div className="yogaSummaryOverlay">
            <span>CIERRE DE PRACTICA</span>
            <h2>{gameState.yoga.summary.message}</h2>
            <strong>{gameState.yoga.summary.points} pts</strong>
            <div className="yogaSummaryGrid">
              {gameState.yoga.summary.results.map((result) => (
                <article key={result.id}>
                  <div>
                    <small>{result.name}</small>
                    <b>{result.points}/{result.maxPoints} pts</b>
                  </div>
                  <p>
                    {result.options.map((option) => (
                      <span key={option.id}>Lado {option.option}: {option.points}/{option.maxPoints}</span>
                    ))}
                  </p>
                  <i>
                    <span style={{ transform: `scaleX(${Math.max(0, Math.min(result.percent / 100, 1))})` }} />
                  </i>
                  <em>{result.message}</em>
                </article>
              ))}
            </div>
            {summaryClapPrompt}
          </div>
        )}

        {boxingResult && (
          <div className="boxingResultOverlay">
            <span>MODULO {boxingResult.index + 1}</span>
            <h2>{boxingResult.rating}</h2>
            <strong>{boxingResult.percent}%</strong>
            <p>{boxingResult.name}</p>
            <small>{boxingResult.correct}/{boxingResult.expected} movimientos correctos - mejor combo x{boxingResult.bestCombo}</small>
          </div>
        )}

        {isBoxingSummary && gameState?.boxing?.summary && (
          <div className="boxingSummaryOverlay">
            <span>RESUMEN FINAL</span>
            <h2>{gameState.boxing.summary.message}</h2>
            <strong>{gameState.boxing.summary.average}%</strong>
            <div className="boxingSummaryGrid">
              {gameState.boxing.summary.results.map((result) => (
                <article key={result.id}>
                  <div>
                    <small>{result.name}</small>
                    <b>{result.percent}%</b>
                  </div>
                  <i>
                    <span style={{ transform: `scaleX(${Math.max(0, Math.min(result.percent / 100, 1))})` }} />
                  </i>
                  <em>{result.rating}</em>
                </article>
              ))}
            </div>
            {summaryClapPrompt}
          </div>
        )}

        {isPreparing && gameState?.module && (
          <ExerciseTransition
            state={gameState.state}
            activity={gameState.activity}
            module={gameState.module}
            video={gameState.video ?? null}
            remaining={prep?.remaining ?? PREP_SECONDS}
          />
        )}

        {error && (
          <div className="cameraError">
            <strong>{error}</strong>
            <span>Revisa permisos del navegador, cierra apps que usen la webcam y recarga la pagina.</span>
          </div>
        )}
        {lastCommand && <span className="lastCommand">{lastCommand}</span>}
      </section>
    </main>
  );
}
