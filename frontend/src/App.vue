<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import GraphCanvas from "./components/GraphCanvas.vue";
import ControlsPanel from "./components/ControlsPanel.vue";
import DetailPanel from "./components/DetailPanel.vue";
import VideosView from "./components/VideosView.vue";
import { fetchAccount, fetchGraph, labelAccount, syncGraph } from "./api";
import type { LayoutName } from "./graph/layout";
import { LABEL_COLORS, LABEL_TEXT } from "./graph/style";
import type { AccountDetail, GraphPayload, RelationshipType } from "./types";

const ALL_TYPES: RelationshipType[] = ["following", "reposted", "bookmarked_author"];

type Mode = "graph" | "videos";
const mode = ref<Mode>("graph");
const focusVideoId = ref<number | null>(null);

const payload = ref<GraphPayload | null>(null);
const activeTypes = ref<RelationshipType[]>([...ALL_TYPES]);
const layoutName = ref<LayoutName>("fcose");
const hideIsolated = ref(false);
const query = ref("");

const selectedHandle = ref<string | null>(null);
const account = ref<AccountDetail | null>(null);

const loadingGraph = ref(true);
const loadingAccount = ref(false);
const syncing = ref(false);
const savingLabel = ref(false);
const toast = ref("");
const error = ref("");

const canvas = ref<InstanceType<typeof GraphCanvas> | null>(null);

const stats = computed(
  () =>
    payload.value?.stats ?? {
      total_accounts: 0,
      visible_accounts: 0,
      total_edges: 0,
      visible_edges: 0,
      hidden_single_edge_nodes: 0,
      relationship_types: [],
    },
);

function flash(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    if (toast.value === message) toast.value = "";
  }, 2600);
}

async function loadGraph() {
  loadingGraph.value = true;
  error.value = "";
  try {
    payload.value = await fetchGraph(ALL_TYPES, false);
  } catch (err) {
    error.value = String(err);
  } finally {
    loadingGraph.value = false;
  }
}

async function onSelect(handle: string | null) {
  selectedHandle.value = handle;
  account.value = null;
  if (!handle) return;
  loadingAccount.value = true;
  try {
    account.value = await fetchAccount(handle);
  } catch (err) {
    error.value = String(err);
  } finally {
    loadingAccount.value = false;
  }
}

async function onFocus(handle: string) {
  await onSelect(handle);
  canvas.value?.focusNode(handle);
}

function openVideo(id: number) {
  focusVideoId.value = id;
  mode.value = "videos";
}

async function onSync() {
  syncing.value = true;
  try {
    const result = await syncGraph();
    flash(`已同步：作者 ${result.report_authors ?? 0}，关系 ${result.repost_edges ?? 0}`);
    await loadGraph();
    if (selectedHandle.value) account.value = await fetchAccount(selectedHandle.value);
  } catch (err) {
    error.value = String(err);
  } finally {
    syncing.value = false;
  }
}

async function onSaveLabel(label: string, notes: string | null) {
  if (!selectedHandle.value) return;
  savingLabel.value = true;
  try {
    account.value = await labelAccount(selectedHandle.value, label, notes);
    flash("已保存标签");
    await loadGraph();
  } catch (err) {
    error.value = String(err);
  } finally {
    savingLabel.value = false;
  }
}

onMounted(loadGraph);

const legendItems = (Object.keys(LABEL_COLORS) as (keyof typeof LABEL_COLORS)[]).map((key) => ({
  key,
  color: LABEL_COLORS[key],
  text: LABEL_TEXT[key],
}));

function onToast(message: string) {
  flash(message);
}
</script>

<template>
  <div class="app" :class="`mode-${mode}`">
    <header class="topbar">
      <div class="brand">
        <h1>video-hunter</h1>
        <span>X 书签作者知识图谱 · 视频来源与搬运链</span>
      </div>
      <div class="mode-toggle">
        <button :class="{ active: mode === 'graph' }" @click="mode = 'graph'">图谱</button>
        <button :class="{ active: mode === 'videos' }" @click="mode = 'videos'">视频</button>
      </div>
      <div class="stats">
        <div class="stat"><strong>{{ stats.total_accounts }}</strong><span>作者</span></div>
        <div class="stat"><strong>{{ stats.total_edges }}</strong><span>关系</span></div>
      </div>
    </header>

    <aside v-if="mode === 'graph'" class="sidebar">
      <ControlsPanel
        :stats="stats"
        :active-types="activeTypes"
        :layout-name="layoutName"
        :hide-isolated="hideIsolated"
        :query="query"
        :loading="syncing"
        @update:active-types="activeTypes = $event"
        @update:layout-name="layoutName = $event"
        @update:hide-isolated="hideIsolated = $event"
        @update:query="query = $event"
        @fit="canvas?.fit()"
        @relayout="canvas?.runLayout()"
        @sync="onSync"
      />

      <section class="panel">
        <h2>原创性图例</h2>
        <div class="legend">
          <div v-for="item in legendItems" :key="item.key" class="legend-row">
            <span><i class="dot" :style="{ background: item.color }" />{{ item.text }}</span>
          </div>
        </div>
      </section>

      <section v-if="error" class="panel">
        <div class="status error">{{ error }}</div>
      </section>
    </aside>

    <main class="main">
      <div v-if="mode === 'graph'" class="graph-shell">
        <div class="graph-bar">
          <strong>作者关系图</strong>
          <span class="muted">{{ loadingGraph ? "加载中…" : `${stats.visible_accounts} 节点 · ${stats.visible_edges} 边` }}</span>
        </div>
        <div class="graph-area">
          <GraphCanvas
            v-if="payload"
            ref="canvas"
            :payload="payload"
            :active-types="activeTypes"
            :layout-name="layoutName"
            :hide-isolated="hideIsolated"
            :query="query"
            :selected-handle="selectedHandle"
            @select="onSelect"
          />
          <div v-else-if="loadingGraph" class="status" style="padding: 24px">正在加载图谱…</div>
          <div v-else class="status error" style="padding: 24px">图谱加载失败：{{ error }}</div>
          <div v-if="toast" class="toast">{{ toast }}</div>
        </div>
      </div>

      <VideosView
        v-else
        :focus-video-id="focusVideoId"
        @toast="onToast"
      />
    </main>

    <aside v-if="mode === 'graph'" class="detailbar">
      <DetailPanel
        :account="account"
        :loading="loadingAccount"
        :saving="savingLabel"
        @save="onSaveLabel"
        @focus="onFocus"
        @open-video="openVideo"
      />
    </aside>
  </div>
</template>
