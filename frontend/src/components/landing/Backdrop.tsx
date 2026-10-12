import { useEffect, useRef } from 'react';

/* ponytail: akashml-warm ambience — faint dot grid + two slow-breathing
   radial glows (warm ivory upper-left, slate blue lower-right). Canvas 2D
   alpha fills only, DPR capped, pauses off-tab, static frame for reduced
   motion. */

export default function Backdrop() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = 0, h = 0, raf = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.25);

    const resize = () => {
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t0 = performance.now();
    const GAP = 32;

    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      ctx.clearRect(0, 0, w, h);

      // soft glows: warm ivory upper-left, slate lower-right, slow breathing
      const b1 = 0.08 + 0.02 * Math.sin(t * 0.4);
      const b2 = 0.06 + 0.02 * Math.sin(t * 0.33 + 2);
      let g = ctx.createRadialGradient(w * 0.22, h * 0.12, 0, w * 0.22, h * 0.12, Math.max(w, h) * 0.5);
      g.addColorStop(0, `rgba(245,245,240,${b1})`);
      g.addColorStop(1, 'rgba(245,245,240,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      g = ctx.createRadialGradient(w * 0.85, h * 0.75, 0, w * 0.85, h * 0.75, Math.max(w, h) * 0.45);
      g.addColorStop(0, `rgba(60,90,149,${b2})`);
      g.addColorStop(1, 'rgba(60,90,149,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      // faint dot grid, gently drifting downward
      ctx.fillStyle = 'rgba(255,255,255,0.06)';
      const off = (t * 6) % GAP;
      for (let y = -GAP + off; y < h + GAP; y += GAP) {
        for (let x = 0; x < w + GAP; x += GAP) {
          ctx.fillRect(x, y, 1.5, 1.5);
        }
      }
    };

    if (reduced) {
      draw(t0 + 5000); // ponytail: one static frame, no loop
    } else {
      const loop = (now: number) => { draw(now); raf = requestAnimationFrame(loop); };
      raf = requestAnimationFrame(loop);
      const onVis = () => {
        if (document.hidden) cancelAnimationFrame(raf);
        else raf = requestAnimationFrame(loop);
      };
      document.addEventListener('visibilitychange', onVis);
      return () => {
        cancelAnimationFrame(raf);
        document.removeEventListener('visibilitychange', onVis);
        window.removeEventListener('resize', resize);
      };
    }
    return () => window.removeEventListener('resize', resize);
  }, []);

  return <canvas ref={ref} aria-hidden className="fixed inset-0 -z-10 pointer-events-none" />;
}
