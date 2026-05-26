import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// next/dynamic returns a synchronous stub so jsdom doesn't try to mount the
// real WebGL/canvas backends. The primitive's contract (container mounts +
// data-mode reflects the prop) is what we're verifying.
vi.mock("next/dynamic", () => ({
  default: () =>
    function DynamicStub(props: { graphData?: { nodes: unknown[] } }) {
      const count = props.graphData?.nodes?.length ?? 0;
      return <div data-testid="dynamic-fg" data-node-count={count} />;
    },
}));

import { ForceGraphCanvas } from "../ForceGraphCanvas";

interface N {
  id: string;
  label?: string;
  val?: number;
  color?: string;
}
interface L {
  source: string;
  target: string;
}

const sample = {
  nodes: [
    { id: "a", label: "A", color: "#fff", val: 4 },
    { id: "b", label: "B", color: "#fff", val: 4 },
    { id: "c", label: "C", color: "#fff", val: 4 },
  ] as N[],
  links: [
    { source: "a", target: "b" },
    { source: "b", target: "c" },
  ] as L[],
};

describe("ForceGraphCanvas", () => {
  it("mounts with mode=2d by default", () => {
    render(<ForceGraphCanvas<N, L> nodes={sample.nodes} links={sample.links} />);
    const container = screen.getByTestId("force-graph-canvas");
    expect(container).toBeInTheDocument();
    expect(container.getAttribute("data-mode")).toBe("2d");
    expect(screen.getByTestId("dynamic-fg")).toBeInTheDocument();
  });

  it("reflects mode=3d on the container", () => {
    render(
      <ForceGraphCanvas<N, L>
        nodes={sample.nodes}
        links={sample.links}
        mode="3d"
      />,
    );
    expect(screen.getByTestId("force-graph-canvas").getAttribute("data-mode")).toBe(
      "3d",
    );
  });

  it("does not mount the force-graph engine when nodes is empty", () => {
    render(<ForceGraphCanvas<N, L> nodes={[]} links={[]} />);
    expect(screen.getByTestId("force-graph-canvas")).toBeInTheDocument();
    expect(screen.queryByTestId("dynamic-fg")).not.toBeInTheDocument();
  });

  it("does not render hover card without a hovered node", () => {
    render(
      <ForceGraphCanvas<N, L>
        nodes={sample.nodes}
        links={sample.links}
        hoverCard={(n) => <div data-testid="hover-card">{n.id}</div>}
      />,
    );
    // No hover dispatched in this test environment — card should not render.
    expect(screen.queryByTestId("hover-card")).not.toBeInTheDocument();
  });

  it("passes graphData with the right node count to the engine", () => {
    render(<ForceGraphCanvas<N, L> nodes={sample.nodes} links={sample.links} />);
    expect(screen.getByTestId("dynamic-fg").getAttribute("data-node-count")).toBe(
      "3",
    );
  });
});
