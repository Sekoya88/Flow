"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 90;
const MAX_LINK_DIST = 140;
const SPEED = 0.18;
const GLOW_SIZE = 5.5;
const MOUSE_PULL = 0.0012;
const MOUSE_RANGE = 220;

export function HeroCanvas({ className }: { className?: string }) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    /* ── renderer ── */
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);

    const camera = new THREE.OrthographicCamera(0, 1, 1, 0, -1, 1);
    const scene = new THREE.Scene();

    /* ── node positions / velocities ── */
    type Node = { x: number; y: number; vx: number; vy: number };
    let nodes: Node[] = [];

    function buildNodes(w: number, h: number) {
      const count = Math.min(NODE_COUNT, Math.floor((w * h) / 10000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * SPEED,
        vy: (Math.random() - 0.5) * SPEED,
      }));
    }

    /* ── point cloud (glow sprites) ── */
    const pointGeo = new THREE.BufferGeometry();
    const ptPositions = new Float32Array(NODE_COUNT * 3);
    pointGeo.setAttribute("position", new THREE.BufferAttribute(ptPositions, 3));

    const pointMat = new THREE.PointsMaterial({
      color: 0xc4b5fd,
      size: GLOW_SIZE,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const pointCloud = new THREE.Points(pointGeo, pointMat);
    scene.add(pointCloud);

    /* ── line segments ── */
    const MAX_LINKS = NODE_COUNT * NODE_COUNT;
    const linePositions = new Float32Array(MAX_LINKS * 6);
    const lineColors = new Float32Array(MAX_LINKS * 6);
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    lineGeo.setAttribute("color", new THREE.BufferAttribute(lineColors, 3));

    const lineMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 1,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const lineSegs = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lineSegs);

    /* ── secondary faint halo layer ── */
    const haloMat = new THREE.PointsMaterial({
      color: 0xa78bfa,
      size: GLOW_SIZE * 2.8,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const haloCloud = new THREE.Points(pointGeo, haloMat);
    scene.add(haloCloud);

    /* ── resize ── */
    let W = 0;
    let H = 0;

    function resize() {
      if (!el) return;
      W = el.clientWidth;
      H = el.clientHeight;
      renderer.setSize(W, H);
      camera.right = W;
      camera.top = H;
      camera.updateProjectionMatrix();
      buildNodes(W, H);
    }

    resize();

    /* ── mouse ── */
    const mouse = { x: -99999, y: -99999 };
    function onMove(e: MouseEvent) {
      const r = el.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
    }
    function onLeave() {
      mouse.x = -99999;
      mouse.y = -99999;
    }

    /* ── animate ── */
    let raf = 0;
    let active = true;

    const io = new IntersectionObserver(([entry]) => {
      active = entry.isIntersecting;
    });
    io.observe(el);

    function frame() {
      raf = requestAnimationFrame(frame);
      if (!active) return;

      /* update node positions */
      for (const n of nodes) {
        // mouse pull
        const mdx = mouse.x - n.x;
        const mdy = mouse.y - n.y;
        const md2 = mdx * mdx + mdy * mdy;
        if (md2 < MOUSE_RANGE * MOUSE_RANGE) {
          n.x += mdx * MOUSE_PULL;
          n.y += mdy * MOUSE_PULL;
        }
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
      }

      /* write point positions */
      for (let i = 0; i < nodes.length; i++) {
        ptPositions[i * 3] = nodes[i].x;
        ptPositions[i * 3 + 1] = nodes[i].y;
        ptPositions[i * 3 + 2] = 0;
      }
      // Zero out unused slots
      for (let i = nodes.length; i < NODE_COUNT; i++) {
        ptPositions[i * 3] = ptPositions[i * 3 + 1] = ptPositions[i * 3 + 2] = 0;
      }
      pointGeo.attributes.position.needsUpdate = true;

      /* build line segments */
      let li = 0;
      for (let a = 0; a < nodes.length; a++) {
        for (let b = a + 1; b < nodes.length; b++) {
          const dx = nodes[a].x - nodes[b].x;
          const dy = nodes[a].y - nodes[b].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MAX_LINK_DIST) {
            const t = 1 - dist / MAX_LINK_DIST;
            const r = 0.54 * t;  // violet R
            const g = 0.39 * t;  // violet G
            const bv = 0.98 * t; // violet B
            linePositions[li * 6 + 0] = nodes[a].x;
            linePositions[li * 6 + 1] = nodes[a].y;
            linePositions[li * 6 + 2] = 0;
            linePositions[li * 6 + 3] = nodes[b].x;
            linePositions[li * 6 + 4] = nodes[b].y;
            linePositions[li * 6 + 5] = 0;
            lineColors[li * 6 + 0] = r;
            lineColors[li * 6 + 1] = g;
            lineColors[li * 6 + 2] = bv;
            lineColors[li * 6 + 3] = r;
            lineColors[li * 6 + 4] = g;
            lineColors[li * 6 + 5] = bv;
            li++;
            if (li >= MAX_LINKS) break;
          }
        }
        if (li >= MAX_LINKS) break;
      }
      lineGeo.setDrawRange(0, li * 2);
      lineGeo.attributes.position.needsUpdate = true;
      lineGeo.attributes.color.needsUpdate = true;

      renderer.render(scene, camera);
    }

    frame();

    const ro = new ResizeObserver(resize);
    ro.observe(el);
    window.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      window.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
      renderer.dispose();
      if (renderer.domElement.parentNode === el) {
        el.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={mountRef} aria-hidden className={className} />;
}
