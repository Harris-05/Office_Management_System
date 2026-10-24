import { useEffect, useRef, useState } from 'react';
import { content } from './content';
import type { Language } from './content';
import { pageCopy } from './pageCopy';
import { clamp, sceneProgress, sceneStep, watchScroll } from './scrollMotion';

function hashStep() {
  const match = window.location.hash.match(/^#participation-([1-3])$/);
  return match ? Number(match[1]) - 1 : null;
}

export default function ProgramStory({ language }: { language: Language }) {
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(() => hashStep() ?? 0);
  const activeRef = useRef(active);
  const pinned = useRef(false);
  const copy = content[language].programs;
  const extra = pageCopy[language];
  const count = copy.items.length;

  const setStep = (index: number) => {
    const next = clamp(index, 0, count - 1);
    if (next === activeRef.current) return;
    if (root.current) root.current.dataset.direction = next > activeRef.current ? 'forward' : 'backward';
    activeRef.current = next;
    if (!pinned.current) root.current?.style.setProperty('--story-progress', String((next + 1) / count));
    setActive(next);
  };
  const choose = (index: number, behavior: ScrollBehavior = 'instant') => {
    setStep(index);
    if (!pinned.current || !root.current || !stage.current) return;
    const bounds = root.current.getBoundingClientRect();
    const travel = bounds.height - stage.current.getBoundingClientRect().height;
    window.scrollTo({ top: window.scrollY + bounds.top + travel * ((index + .5) / count), behavior });
  };
  const chooseRef = useRef(choose);
  chooseRef.current = choose;

  useEffect(() => {
    const node = root.current!;
    const held = stage.current!;
    const motion = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;
    const update = () => {
      const stageHeight = held.getBoundingClientRect().height;
      // innerHeight is rounded to an integer; svh/layout measurements can be fractional.
      // Without this tolerance, pinning changes the measured height and oscillates every frame.
      pinned.current = !motion?.matches && stageHeight > 0 && stageHeight <= window.innerHeight + 1;
      if (node.dataset.pinned !== String(pinned.current)) node.dataset.pinned = String(pinned.current);
      if (!pinned.current) {
        node.style.setProperty('--story-lift', '0px');
        node.style.setProperty('--story-progress', String((activeRef.current + 1) / count));
        return;
      }
      const bounds = node.getBoundingClientRect();
      const progress = sceneProgress(bounds.top, bounds.height, stageHeight);
      node.style.setProperty('--story-progress', String(progress));
      setStep(sceneStep(progress, count));
    };
    const watcher = watchScroll(update);
    const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(watcher.schedule) : null;
    resize?.observe(held);
    const readHash = () => { const index = hashStep(); if (index !== null) chooseRef.current(index, 'instant'); };
    readHash();
    window.addEventListener('hashchange', readHash);
    motion?.addEventListener('change', watcher.schedule);
    return () => { watcher.stop(); resize?.disconnect(); window.removeEventListener('hashchange', readHash); motion?.removeEventListener('change', watcher.schedule); };
  }, [language, count]);

  const selected = copy.items[active];
  return <section ref={root} id="programs" className="program-scene" aria-labelledby="programs-title" data-direction="forward">
    <div ref={stage} className="program-scene-stage home-section">
      <div className="program-scene-intro">
        <h2 id="programs-title">{copy.title}</h2><p className="program-scene-summary">{copy.intro}</p>
        <div className="program-scene-steps" role="group" aria-label={copy.title}>{copy.items.map((item, index) => <button id={`participation-${index + 1}`} key={index} type="button" aria-pressed={active === index} aria-controls="program-panel" onClick={() => choose(index)}><span className="story-step-dot" aria-hidden="true" /><span>{item.title}</span></button>)}</div>
        <p className="program-scroll-hint">{extra.scrollHint}</p>
      </div>
      <div className="program-scene-presentation">
        <article id="program-panel" className="story-panel" aria-labelledby="program-step-title">
          <div className="story-copy-frame">
            {copy.items.map((item, index) => <div key={index} className="story-measure" aria-hidden="true"><span className="story-measure-title">{item.title}</span><span className="story-measure-body">{item.body}</span></div>)}
            <div className="story-panel-motion" aria-live="polite" aria-atomic="true"><div className="story-panel-copy" key={`${language}:${active}`}><h3 id="program-step-title">{selected.title}</h3><p>{selected.body}</p></div></div>
          </div>
          <a className="home-text-link" href="/get-involved">{content[language].hero.action}<span aria-hidden="true"> ↗</span></a>
        </article>
        <div className="story-controls"><span className="story-position" aria-hidden="true">{active + 1} / {count}</span><div><button type="button" aria-label={extra.previousStep} disabled={active === 0} onClick={() => choose(active - 1)}><span aria-hidden="true">←</span></button><button type="button" aria-label={extra.nextStep} disabled={active === count - 1} onClick={() => choose(active + 1)}><span aria-hidden="true">→</span></button></div></div>
        <div className="story-progress" aria-hidden="true"><span /></div>
      </div>
    </div>
  </section>;
}
