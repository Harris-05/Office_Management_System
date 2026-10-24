import { clamp } from './scrollMotion';

type Options = { readProgress: () => number; isMoving: () => boolean; paint: (turn: number, progress: number) => void };

export function animateGlobe({ readProgress, isMoving, paint }: Options) {
  let angle = -.4;
  let progress = clamp(readProgress());
  let target = progress;
  let frame = 0;
  let previous: number | null = null;
  let lastPaint = -Infinity;
  let stopped = false;
  const draw = () => paint(angle + progress * 1.6, progress);
  const tick = (time: number) => {
    frame = 0;
    if (stopped || !isMoving()) { previous = null; return; }
    const seconds = previous === null ? 0 : Math.min(64, Math.max(0, time - previous)) / 1000;
    previous = time;
    angle += seconds * .075;
    progress += (target - progress) * (1 - Math.exp(-seconds / .12));
    if (time - lastPaint >= 32) { draw(); lastPaint = time; }
    frame = requestAnimationFrame(tick);
  };
  const refresh = () => {
    if (stopped) return;
    if (isMoving() && typeof requestAnimationFrame === 'function') {
      target = clamp(readProgress());
      if (!frame) frame = requestAnimationFrame(tick);
    } else {
      if (frame) cancelAnimationFrame(frame);
      frame = 0; previous = null;
    }
    draw();
  };
  refresh();
  return { refresh, stop() { stopped = true; if (frame) cancelAnimationFrame(frame); frame = 0; } };
}
