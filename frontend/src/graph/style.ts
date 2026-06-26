// Cytoscape visual style + color maps. Node color encodes originality label,
// node size encodes degree/video volume; edge color encodes relationship type.
import type { StylesheetStyle } from "cytoscape";
import type { OriginalityLabel, RelationshipType } from "../types";

export const LABEL_COLORS: Record<OriginalityLabel, string> = {
  likely_original: "#167862",
  needs_review: "#a56818",
  likely_non_original: "#af3f4a",
  reposter: "#2467a3",
  unknown: "#8b99a6",
};

export const EDGE_COLORS: Record<RelationshipType, string> = {
  following: "#2f8f78",
  reposted: "#2467a3",
  bookmarked_author: "#c08a3e",
};

export const LABEL_TEXT: Record<OriginalityLabel, string> = {
  likely_original: "疑似原创",
  needs_review: "待核验",
  likely_non_original: "疑似搬运",
  reposter: "转发型",
  unknown: "未知",
};

export const RELATION_TEXT: Record<RelationshipType, string> = {
  following: "关注",
  reposted: "转发",
  bookmarked_author: "书签作者",
};

export function buildStylesheet(): StylesheetStyle[] {
  // @types/cytoscape declares several numeric style values (font-size, widths,
  // margins) as string, but Cytoscape accepts numbers at runtime. Build the
  // stylesheet as plain objects and cast once, instead of per-property casts.
  const stylesheet = [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        width: "data(size)",
        height: "data(size)",
        label: "data(label)",
        color: "#18212a",
        "font-size": 10,
        "text-opacity": 0,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 4,
        "text-max-width": 90,
        "text-wrap": "ellipsis",
        "text-outline-color": "#ffffff",
        "text-outline-width": 2.5,
        "border-width": 0,
        "overlay-opacity": 0,
      },
    },
    // Labels: only hub nodes (high degree) are labeled by default. Every other
    // node reveals its label on hover, on selection, or when a selected node's
    // neighborhood is in focus — keeping dense graphs readable.
    { selector: "node.labeled", style: { "text-opacity": 1 } },
    { selector: "node.nb-label", style: { "text-opacity": 1 } },
    { selector: "node.hovered", style: { "text-opacity": 1, "font-size": 12, "z-index": 99 } },
    {
      selector: "node[kind='collection']",
      style: { shape: "round-rectangle", "background-color": "#3a4a5a" },
    },
    {
      selector: "node.faded",
      style: { opacity: 0.07 },
    },
    {
      selector: "node.selected",
      style: {
        "border-width": 4,
        "border-color": "#18212a",
        "border-opacity": 0.9,
        "text-opacity": 1,
        "font-size": 12,
      },
    },
    {
      selector: "edge",
      style: {
        "line-color": "data(color)",
        "target-arrow-color": "data(color)",
        width: "data(width)",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.8,
        opacity: 0.55,
        "loop-direction": "0deg",
      },
    },
    {
      selector: "edge.faded",
      style: { opacity: 0.03 },
    },
    {
      selector: "edge.highlighted",
      style: { opacity: 0.95, width: "data(width)" },
    },
    {
      selector: ".hidden-elem",
      style: { display: "none" },
    },
  ];
  return stylesheet as unknown as StylesheetStyle[];
}
