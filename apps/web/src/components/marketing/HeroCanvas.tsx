"use client";

import { useEffect, useRef } from "react";

/**
 * Animated knowledge-graph background — drifting nodes linked by fading edges,
 * with a soft cursor-reactive pull. Pure canvas 2D (no WebGL deps), capped node
 * count, pauses when off-screen, and honours prefers-reduced-motion.
 */
export function HeroCanvas({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const cv = ref.current;
    const rawCtx = cv.getContext("2d");
    if (!rawCtx) return;
    // Non-null binding for use inside the animation closures (TS does not carry
    // the null-guard narrowing into nested functions).
    const c: CanvasRenderingContext2D = rawCtx;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let width = 0;
    let height = 0;
    type Node = { x: number; y: number; vx: number; vy: number; r: number };
    let nodes: Node[] = [];
    const mouse = { x: -9999, y: -9999 };

    function resize() {
      const parent = cv.parentElement;
      width = parent?.clientWidth ?? window.innerWidth;
      height = parent?.clientHeight ?? 420;
      cv.width = width * dpr;
      cv.height = height * dpr;
      cv.style.width = `${width}px`;
      cv.style.height = `${height}px`;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.min(70, Math.floor((width * height) / 16000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        r: 1.2 + Math.random() * 1.8,
      }));
    }

    const LINK_DIST = 130;

    function frame() {
      c.clearRect(0, 0, width, height);

      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > width) n.vx *= -1;
        if (n.y < 0 || n.y > height) n.vy *= -1;

        // gentle cursor attraction
        const dx = mouse.x - n.x;
        const dy = mouse.y - n.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < 24000) {
          n.x += dx * 0.0009;
          n.y += dy * 0.0009;
        }
      }

      // edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < LINK_DIST) {
            const alpha = (1 - dist / LINK_DIST) * 0.32;
            c.strokeStyle = `rgba(167, 139, 250, ${alpha})`;
            c.lineWidth = 1;
            c.beginPath();
            c.moveTo(a.x, a.y);
            c.lineTo(b.x, b.y);
            c.stroke();
          }
        }
      }

      // nodes
      for (const n of nodes) {
        c.beginPath();
        c.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        c.fillStyle = "rgba(196, 181, 253, 0.9)";
        c.fill();
      }
    }

    let raf = 0;
    let running = true;
    function loop() {
      if (running) frame();
      raf = requestAnimationFrame(loop);
    }

    function onMove(e: MouseEvent) {
      const rect = cv.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    }
    function onLeave() {
      mouse.x = -9999;
      mouse.y = -9999;
    }

    const io = new IntersectionObserver(([entry]) => {
      running = entry.isIntersecting && !reduce;
    });

    resize();
    if (reduce) {
      frame(); // single static render
    } else {
      io.observe(cv);
      raf = requestAnimationFrame(loop);
    }
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseleave", onLeave);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return <canvas ref={ref} aria-hidden className={className} />;
}
