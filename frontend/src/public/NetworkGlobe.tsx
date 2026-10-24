import { useEffect, useRef, useState } from 'react';
import type { Language } from './content';
import { pageCopy } from './pageCopy';
import { clamp, watchScroll } from './scrollMotion';
import { animateGlobe } from './globeMotion';

type Point = { x: number; y: number; z: number };
const point = (latitude: number, longitude: number): Point => ({
  x: Math.cos(latitude) * Math.sin(longitude), y: -Math.sin(latitude), z: Math.cos(latitude) * Math.cos(longitude),
});
const nodes = Array.from({ length: 72 }, (_, index) => point(Math.asin(1 - 2 * (index + .5) / 72), index * Math.PI * (3 - Math.sqrt(5))));
const rings: Point[][] = [];
for (const latitude of [-60, -30, 0, 30, 60]) rings.push(Array.from({ length: 81 }, (_, i) => point(latitude * Math.PI / 180, i / 80 * Math.PI * 2)));
for (let longitude = 0; longitude < 180; longitude += 20) rings.push(Array.from({ length: 81 }, (_, i) => point(-Math.PI / 2 + i / 80 * Math.PI * 2, longitude * Math.PI / 180)));
const routes = Array.from({ length: 13 }, (_, index) => {
  const start = nodes[(index * 5 + 3) % nodes.length];
  const end = nodes[(index * 5 + 24) % nodes.length];
  return Array.from({ length: 37 }, (_, i) => {
    const t = i / 36;
    const mixed = { x: start.x * (1 - t) + end.x * t, y: start.y * (1 - t) + end.y * t, z: start.z * (1 - t) + end.z * t };
    const scale = (1 + Math.sin(t * Math.PI) * .15) / Math.hypot(mixed.x, mixed.y, mixed.z);
    return { x: mixed.x * scale, y: mixed.y * scale, z: mixed.z * scale };
  });
});

function draw(context: CanvasRenderingContext2D, size: number, turn: number, progress: number, ink: string) {
  const radius = size * .37;
  const center = size / 2;
  const project = (p: Point) => {
    const x = p.x * Math.cos(turn) + p.z * Math.sin(turn);
    const z = p.z * Math.cos(turn) - p.x * Math.sin(turn);
    return { x: center + x * radius, y: center + (p.y * Math.cos(.16) - z * Math.sin(.16)) * radius, z: p.y * Math.sin(.16) + z * Math.cos(.16) };
  };
  context.clearRect(0, 0, size, size);
  context.strokeStyle = ink;
  context.fillStyle = ink;
  context.lineWidth = .8;
  for (const ring of rings) {
    const points = ring.map(project);
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      context.globalAlpha = (a.z + b.z) / 2 < 0 ? .08 : .24;
      context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y); context.stroke();
    }
  }
  context.lineWidth = 1.4;
  routes.forEach((route, index) => {
    const points = route.map(project);
    const length = Math.max(7, Math.round(points.length * (.55 + progress * .45)));
    for (let i = 1; i < length; i++) {
      const a = points[i - 1], b = points[i];
      context.globalAlpha = (a.z + b.z) / 2 < 0 ? .1 : .58;
      context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y); context.stroke();
    }
    const active = points[(index * 3 + Math.round(progress * 20)) % length];
    if (active.z > 0) { context.globalAlpha = .95; context.beginPath(); context.arc(active.x, active.y, 2.6, 0, Math.PI * 2); context.fill(); }
  });
  for (const node of nodes.map(project)) {
    context.globalAlpha = node.z < 0 ? .14 : .85;
    context.beginPath(); context.arc(node.x, node.y, node.z < 0 ? 1.2 : 2, 0, Math.PI * 2); context.fill();
  }
  context.globalAlpha = .35;
  context.lineWidth = .8;
  context.beginPath(); context.arc(center, center, radius, 0, Math.PI * 2); context.stroke();
  context.globalAlpha = 1;
}

export default function NetworkGlobe({ language }: { language: Language }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const figure = useRef<HTMLElement>(null);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  const refreshRef = useRef<(() => void) | null>(null);
  const copy = pageCopy[language];
  useEffect(() => {
    const element = canvas.current!;
    const context = element.getContext('2d');
    if (!context) return;
    const motion = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;
    const hero = element.closest('.home-hero')!;
    const ink = getComputedStyle(hero).getPropertyValue('--home-hero-action').trim() || '#f4e7ea';
    const bounds = hero.getBoundingClientRect();
    let visible = bounds.bottom > 0 && bounds.top < window.innerHeight;
    let lastTurn = Number.NaN, lastSize = 0;
    const paint = (turn: number, progress: number) => {
      const size = Math.round(element.getBoundingClientRect().width);
      if (!size || (lastTurn === turn && lastSize === size)) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (lastSize !== size) { element.width = Math.round(size * dpr); element.height = Math.round(size * dpr); }
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(context, size, turn, progress, ink);
      if (figure.current) figure.current.dataset.rendered = 'true';
      figure.current?.style.setProperty('--network-turn', turn.toFixed(4));
      lastTurn = turn; lastSize = size;
    };
    const animation = animateGlobe({
      readProgress: () => { const bounds = hero.getBoundingClientRect(); return clamp(-bounds.top / Math.max(bounds.height, 1)); },
      isMoving: () => !pausedRef.current && !motion?.matches && !document.hidden && visible,
      paint,
    });
    refreshRef.current = animation.refresh;
    const watcher = watchScroll(animation.refresh);
    const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(watcher.schedule) : null;
    resize?.observe(element);
    const visibility = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => { visible = entries[0].isIntersecting; animation.refresh(); }) : null;
    visibility?.observe(hero);
    document.addEventListener('visibilitychange', animation.refresh);
    motion?.addEventListener('change', watcher.schedule);
    return () => { refreshRef.current = null; watcher.stop(); animation.stop(); resize?.disconnect(); visibility?.disconnect(); document.removeEventListener('visibilitychange', animation.refresh); motion?.removeEventListener('change', watcher.schedule); };
  }, []);
  useEffect(() => { refreshRef.current?.(); }, [paused]);
  return <figure ref={figure} className="network-globe" aria-label={copy.networkLabel}>
    <div className="network-viewport">
      <canvas ref={canvas} width="600" height="600" aria-hidden="true" />
      <svg className="network-fallback" viewBox="0 0 600 600" aria-hidden="true" fill="none" stroke="currentColor">
        <circle cx="300" cy="300" r="220" /><ellipse cx="300" cy="300" rx="110" ry="220" /><ellipse cx="300" cy="300" rx="190" ry="220" /><ellipse cx="300" cy="300" rx="220" ry="80" /><ellipse cx="300" cy="300" rx="220" ry="160" />
        <path d="M110 220Q310 50 475 350M150 440Q240 180 475 210M150 170Q420 140 410 450" strokeWidth="2" />
        {[['110','220'],['475','350'],['150','440'],['475','210'],['150','170'],['410','450']].map(([cx, cy]) => <circle key={`${cx}:${cy}`} cx={cx} cy={cy} r="4" fill="currentColor" />)}
      </svg>
    </div>
    <figcaption><strong>{copy.networkCaption}</strong><span>{copy.networkNote}</span><button className="network-motion-control" type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? copy.resumeMotion : copy.pauseMotion}</button></figcaption>
  </figure>;
}
