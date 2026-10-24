import { useEffect } from 'react';
import type { RefObject } from 'react';

function motionPreference() {
  return typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : null;
}

export default function useScrollMotion(root: RefObject<HTMLElement | null>, revision: string) {
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    const motion = motionPreference();
    let observer: IntersectionObserver | null = null;
    let targets: HTMLElement[] = [];

    const reset = () => {
      observer?.disconnect();
      for (const target of targets) {
        target.classList.remove('home-reveal-pending');
        target.style.removeProperty('--home-reveal-delay');
      }
      targets = [];
    };
    const prepare = () => {
      reset();
      if (motion?.matches || typeof IntersectionObserver === 'undefined') return;
      const currentObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.remove('home-reveal-pending');
          entry.target.classList.add('home-seen');
          currentObserver.unobserve(entry.target);
        }
      }, { threshold: 0.12, rootMargin: '0px 0px -4% 0px' });
      observer = currentObserver;
      const groups = new Map<Element, number>();
      targets = [...node.querySelectorAll<HTMLElement>('[data-home-reveal]')]
        .filter(target => !target.classList.contains('home-seen'));
      for (const target of targets) {
        const section = target.closest('section') ?? node;
        const order = groups.get(section) ?? 0;
        groups.set(section, order + 1);
        target.style.setProperty('--home-reveal-delay', `${Math.min(order, 4) * 70}ms`);
        // Only prepare offscreen content after a working observer has been created.
        if (target.getBoundingClientRect().top >= window.innerHeight * .9) {
          target.classList.add('home-reveal-pending');
        }
        currentObserver.observe(target);
      }
    };
    prepare();
    motion?.addEventListener('change', prepare);
    return () => { motion?.removeEventListener('change', prepare); reset(); };
  }, [root, revision]);

  useEffect(() => {
    const node = root.current;
    if (!node || typeof window.requestAnimationFrame !== 'function') return;
    const motion = motionPreference();
    let frame = 0;

    const update = () => {
      frame = 0;
      const range = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, window.scrollY / range));
      node.style.setProperty('--home-page-progress', String(progress));
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    schedule();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    motion?.addEventListener('change', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      motion?.removeEventListener('change', schedule);
      window.cancelAnimationFrame(frame);
      node.style.removeProperty('--home-page-progress');
    };
  }, [root]);
}
