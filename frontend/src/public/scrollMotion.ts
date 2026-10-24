export const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

export function sceneProgress(top: number, height: number, heldHeight: number) {
  const travel = height - heldHeight;
  return travel > 0 ? clamp(-top / travel) : 0;
}

export function sceneStep(progress: number, count: number) {
  return Math.min(count - 1, Math.floor(clamp(progress) * count));
}

// One passive event burst schedules one frame. Never intercept wheel/touch input.
export function watchScroll(update: () => void) {
  let frame = 0;
  const run = () => { frame = 0; update(); };
  const schedule = () => {
    if (typeof requestAnimationFrame !== 'function') { update(); return; }
    if (!frame) frame = requestAnimationFrame(run);
  };
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  update();
  return {
    schedule,
    stop() {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) cancelAnimationFrame(frame);
    },
  };
}
