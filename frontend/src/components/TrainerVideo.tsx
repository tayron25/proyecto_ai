import { forwardRef, useEffect, useRef } from "react";

type Props = {
  src: string | null;
  playing?: boolean;
  onEnded: () => void;
};

export const TrainerVideo = forwardRef<HTMLVideoElement, Props>(({ src, playing = true, onEnded }, ref) => {
  const localRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = localRef.current;
    if (!video || !src) {
      return;
    }

    if (playing) {
      void video.play();
    } else {
      video.pause();
    }
  }, [playing, src]);

  const setRef = (node: HTMLVideoElement | null) => {
    localRef.current = node;
    if (typeof ref === "function") {
      ref(node);
    } else if (ref) {
      ref.current = node;
    }
  };

  if (!src) {
    return (
      <div className="trainerEmpty">
        <span>CONSOLA</span>
        <strong>MULTIJUEGOS</strong>
      </div>
    );
  }

  return (
    <video
      ref={setRef}
      className="trainerVideo"
      src={src}
      autoPlay={playing}
      muted
      playsInline
      onEnded={onEnded}
    />
  );
});

TrainerVideo.displayName = "TrainerVideo";
