<script setup lang="ts">
// Cytoscape wrapper. Elements are built once from the payload; all subsequent
// changes (relationship filters, search, selection) just toggle CSS classes —
// no element rebuild, no re-layout — so the graph stays smooth at scale.
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import fcose from "cytoscape-fcose";
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { buildLayout, type LayoutName } from "../graph/layout";
import { EDGE_COLORS, LABEL_COLORS, buildStylesheet } from "../graph/style";
import type { GraphPayload, RelationshipType } from "../types";

cytoscape.use(fcose);

const props = defineProps<{
  payload: GraphPayload;
  activeTypes: RelationshipType[];
  layoutName: LayoutName;
  hideIsolated: boolean;
  query: string;
  selectedHandle: string | null;
}>();

const emit = defineEmits<{ (e: "select", handle: string | null): void }>();

const container = ref<HTMLDivElement | null>(null);
const cy = shallowRef<Core | null>(null);

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function nodeSize(degree: number, videoCount: number): number {
  return clamp(16 + Math.sqrt(degree + videoCount) * 3.6, 16, 46);
}

function edgeWidth(weight: number): number {
  return clamp(1 + Math.min(weight, 8) * 0.6, 1, 6);
}

function nodeLabel(payload: GraphPayload["nodes"][number]): string {
  const name = payload.display_name || `@${payload.handle}`;
  return name.length > 16 ? name.slice(0, 15) + "…" : name;
}

function buildElements(payload: GraphPayload): ElementDefinition[] {
  const nodes: ElementDefinition[] = payload.nodes.map((node) => {
    const isHub = node.degree >= 6 || node.account_kind === "collection";
    return {
      classes: isHub ? "labeled" : undefined,
      data: {
        id: node.handle,
        label: nodeLabel(node),
        handle: node.handle,
        color: LABEL_COLORS[node.effective_label] || LABEL_COLORS.unknown,
        size: nodeSize(node.degree, node.video_count),
        degree: node.degree,
        kind: node.account_kind,
      },
    };
  });
  const edges: ElementDefinition[] = payload.edges.map((edge, index) => ({
    data: {
      id: `e${index}:${edge.source}->${edge.target}:${edge.type}`,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      weight: edge.weight,
      color: EDGE_COLORS[edge.type],
      width: edgeWidth(edge.weight),
    },
  }));
  return [...nodes, ...edges];
}

function applyFilter(): void {
  const instance = cy.value;
  if (!instance) return;
  const active = new Set<RelationshipType>(props.activeTypes);

  instance.edges().forEach((edge) => {
    const visible = active.has(edge.data("type") as RelationshipType);
    edge.toggleClass("hidden-elem", !visible);
  });

  const visibleEdges = instance.edges().filter((e) => !e.hasClass("hidden-elem"));
  const incident = new Set<string>();
  visibleEdges.forEach((e) => {
    incident.add(e.data("source"));
    incident.add(e.data("target"));
  });

  instance.nodes().forEach((node) => {
    const isCollection = node.data("kind") === "collection";
    const isolated = !incident.has(node.data("id"));
    node.toggleClass("hidden-elem", props.hideIsolated && isolated && !isCollection);
  });

  refreshVisualState();
}

function refreshVisualState(): void {
  const instance = cy.value;
  if (!instance) return;
  instance.elements().removeClass("faded selected highlighted");
  instance.nodes().removeClass("nb-label");

  if (props.selectedHandle) {
    const selected = instance.getElementById(props.selectedHandle);
    if (selected.nonempty()) {
      const neighborhood = selected.closedNeighborhood();
      instance.elements().not(neighborhood).addClass("faded");
      selected.addClass("selected");
      neighborhood.nodes().addClass("nb-label");
      neighborhood.edges().addClass("highlighted");
      return;
    }
  }

  const query = props.query.trim().toLowerCase();
  if (query) {
    instance.nodes().forEach((node) => {
      const label = String(node.data("label") || "").toLowerCase();
      const handle = String(node.data("id") || "").toLowerCase();
      if (!label.includes(query) && !handle.includes(query)) {
        node.addClass("faded");
      }
    });
    instance.edges().forEach((edge) => {
      if (edge.source().hasClass("faded") && edge.target().hasClass("faded")) {
        edge.addClass("faded");
      }
    });
  }
}

function runLayout(): void {
  const instance = cy.value;
  if (!instance) return;
  const visible = instance.elements().filter(":visible");
  const layout = visible.layout(buildLayout(props.layoutName));
  // Fit the viewport to whatever the layout produced, so the graph always fills
  // the canvas instead of bunching in the centre.
  layout.one("layoutstop", () => instance.fit(visible, 50));
  layout.run();
}

function fit(): void {
  cy.value?.animate({ fit: { eles: cy.value.elements().filter(":visible"), padding: 40 } }, { duration: 300 });
}

function focusNode(handle: string): void {
  const instance = cy.value;
  if (!instance) return;
  const node = instance.getElementById(handle);
  if (node.nonempty()) {
    instance.animate({ center: { eles: node }, zoom: 1.15 }, { duration: 300 });
  }
}

defineExpose({ fit, runLayout, focusNode });

onMounted(() => {
  if (!container.value) return;
  const instance = cytoscape({
    container: container.value,
    elements: buildElements(props.payload),
    style: buildStylesheet(),
    wheelSensitivity: 0.2,
    minZoom: 0.15,
    maxZoom: 3,
  });
  cy.value = instance;

  instance.on("tap", "node", (event) => {
    emit("select", event.target.data("id") as string);
  });
  instance.on("tap", (event) => {
    if (event.target === instance) emit("select", null);
  });
  instance.on("mouseover", "node", (event) => event.target.addClass("hovered"));
  instance.on("mouseout", "node", (event) => event.target.removeClass("hovered"));

  instance.ready(() => runLayout());

  // Expose for in-browser debugging (console) and headless verification.
  (window as unknown as { __cy?: Core }).__cy = instance;
});

onBeforeUnmount(() => {
  cy.value?.destroy();
  cy.value = null;
});

watch(() => props.layoutName, () => runLayout());
watch(
  () => [props.activeTypes, props.hideIsolated] as const,
  () => applyFilter(),
);
watch(
  () => [props.query, props.selectedHandle] as const,
  () => refreshVisualState(),
);
</script>

<template>
  <div ref="container" class="graph-canvas" />
</template>

<style scoped>
.graph-canvas {
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at 50% 40%, rgba(36, 103, 163, 0.05), transparent 60%),
    linear-gradient(rgba(29, 41, 53, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(29, 41, 53, 0.05) 1px, transparent 1px);
  background-size: auto, 28px 28px, 28px 28px;
}
</style>
