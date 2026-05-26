// Shared types for the <ForceGraphCanvas> primitive.
// Generic over node and link shapes so KG, agent runs, workbench, and project
// snapshots can reuse the same plumbing while keeping their own renderers.

export type GraphMode = "2d" | "3d";

export interface BaseGraphNode {
  id: string;
  val?: number;
  color?: string;
}

export interface BaseGraphLink {
  source: string;
  target: string;
}

export interface NodeRenderState {
  isHovered: boolean;
  isHighlighted: boolean;
  isIncident: boolean;
  hoveredId: string | null;
}

export interface LinkRenderState {
  hoveredId: string | null;
  highlightedIds?: Set<string>;
}

export interface ForceGraphPhysics {
  chargeStrength?: number;
  linkDistance?: number;
  linkStrength?: number;
  centerStrength?: number;
  warmupTicks?: number;
  cooldownTicks?: number;
  cooldownTime?: number;
  alphaDecay?: number;
  velocityDecay?: number;
}
