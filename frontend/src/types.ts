export type Landmark = {
  x: number;
  y: number;
  z: number;
  visibility: number;
};

export type Target = {
  id: number;
  x: number;
  y: number;
  radius: number;
  type: string;
  label: string;
  color: [number, number, number];
  hit: boolean;
  hitCorrect: boolean;
  lifeRatio: number;
  entryScale?: number;
};

export type GameMessage = {
  text: string;
  x: number;
  y: number;
  kind: "good" | "bad" | "dodge" | string;
};

export type GameState = {
  state: "menu" | "boxing" | "pose_challenge" | "aerobics";
  landmarks: Landmark[];
  connections: [number, number][];
  fps: number;
  score: number;
  targets: Target[];
  wrists: { hand: string; x: number; y: number }[];
  video?: string | null;
  messages: GameMessage[];
  nextState?: string | null;
  module?: {
    index: number;
    total: number;
    name: string;
  };
  activity?: {
    kind: "yoga" | "aerobics";
    title: string;
    description: string;
    option?: string;
    conditions?: { label: string; met: boolean }[];
    met?: number;
    total?: number;
    labels?: { label: string; active: boolean }[];
    reps?: number;
    target?: number;
    progress: number;
    success?: boolean;
    successPoints?: number;
    formOk?: boolean | null;
    flash?: boolean;
  };
  boxing?: {
    percent: number;
    combo: number;
    bestCombo: number;
    correct: number;
    failed: number;
    expected: number;
    lastResult?: BoxingModuleResult | null;
    summary?: BoxingSummary | null;
  };
  yoga?: {
    heldSeconds?: number;
    targetSeconds?: number;
    points?: number;
    lastResult?: YogaOptionResult | null;
    poseResult?: YogaPoseResult | null;
    summary?: YogaSummary | null;
  };
  aerobics?: {
    summary?: AerobicsSummary | null;
  };
  menu?: {
    title: string;
    hint: string;
    clapRatio: number;
    hoveredIndex: number;
    buttons: {
      label: string;
      action: string;
      rect: [number, number, number, number];
      hovered: boolean;
    }[];
    wrists: { x: number; y: number }[];
  } | null;
};

export type ClientCommand = "menu" | "reset" | "videoEnded";

export type BoxingModuleResult = {
  id: string;
  index: number;
  name: string;
  percent: number;
  rating: string;
  correct: number;
  failed: number;
  expected: number;
  bestCombo: number;
};

export type BoxingSummary = {
  average: number;
  message: string;
  results: BoxingModuleResult[];
};

export type YogaOptionResult = {
  id: string;
  poseIndex: number;
  optionIndex: number;
  poseName: string;
  option: string;
  heldSeconds: number;
  targetSeconds: number;
  points: number;
  maxPoints: number;
  percent: number;
  message: string;
  breath: string;
};

export type YogaPoseResult = {
  id: string;
  index: number;
  name: string;
  points: number;
  maxPoints: number;
  percent: number;
  message: string;
  options: YogaOptionResult[];
};

export type YogaSummary = {
  points: number;
  maxPoints: number;
  percent: number;
  message: string;
  results: YogaPoseResult[];
};

export type AerobicsModuleResult = {
  id: string;
  index: number;
  name: string;
  reps: number;
  target: number;
  percent: number;
  rating: string;
};

export type AerobicsSummary = {
  reps: number;
  target: number;
  percent: number;
  message: string;
  results: AerobicsModuleResult[];
};
