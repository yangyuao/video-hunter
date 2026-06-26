// Layout presets. fcose gives the nicest community-style clusters; the others
// are useful fallbacks / for different read tasks (concentric = hubs in center).
import type { LayoutOptions } from "cytoscape";

export type LayoutName = "fcose" | "concentric" | "circle" | "grid" | "cose";

export function buildLayout(name: LayoutName): LayoutOptions {
  switch (name) {
    case "fcose":
      return {
        name: "fcose",
        animate: true,
        animationDuration: 700,
        nodeRepulsion: () => 14000,
        idealEdgeLength: () => 130,
        edgeElasticity: () => 0.4,
        gravity: 0.2,
        gravityRangeCompound: 1.5,
        numIter: 3000,
        tile: true,
        padding: 50,
        randomize: true,
      } as LayoutOptions;
    case "concentric":
      return {
        name: "concentric",
        animate: true,
        animationDuration: 500,
        concentric: (ele) => ele.data("degree"),
        levelWidth: () => 2,
        padding: 40,
        minNodeSpacing: 30,
      } as LayoutOptions;
    case "circle":
      return { name: "circle", animate: true, padding: 40 } as LayoutOptions;
    case "grid":
      return { name: "grid", animate: true, padding: 40 } as LayoutOptions;
    case "cose":
    default:
      return {
        name: "cose",
        animate: true,
        idealEdgeLength: 100,
        nodeRepulsion: 8000,
        padding: 40,
        randomize: true,
      } as LayoutOptions;
  }
}

export const LAYOUT_OPTIONS: { value: LayoutName; label: string }[] = [
  { value: "fcose", label: "力导向 (fcose)" },
  { value: "concentric", label: "同心圆 (核心居中)" },
  { value: "circle", label: "环形" },
  { value: "grid", label: "网格" },
  { value: "cose", label: "力导向 (cose)" },
];
