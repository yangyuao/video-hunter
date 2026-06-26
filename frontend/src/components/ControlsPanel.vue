<script setup lang="ts">
import { RELATION_TEXT, EDGE_COLORS } from "../graph/style";
import { LAYOUT_OPTIONS, type LayoutName } from "../graph/layout";
import type { GraphStats, RelationshipType } from "../types";

const props = defineProps<{
  stats: GraphStats;
  activeTypes: RelationshipType[];
  layoutName: LayoutName;
  hideIsolated: boolean;
  query: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "update:activeTypes", value: RelationshipType[]): void;
  (e: "update:layoutName", value: LayoutName): void;
  (e: "update:hideIsolated", value: boolean): void;
  (e: "update:query", value: string): void;
  (e: "fit"): void;
  (e: "relayout"): void;
  (e: "sync"): void;
}>();

const ALL_TYPES: RelationshipType[] = ["following", "reposted", "bookmarked_author"];

function toggleType(type: RelationshipType, checked: boolean) {
  const next = new Set(props.activeTypes);
  if (checked) next.add(type);
  else next.delete(type);
  // keep canonical order
  emit("update:activeTypes", ALL_TYPES.filter((t) => next.has(t)));
}
</script>

<template>
  <section class="panel">
    <h2>图谱范围</h2>
    <div class="control">
      <span>关系类型</span>
      <div class="checks">
        <label v-for="type in ALL_TYPES" :key="type" class="check">
          <input
            type="checkbox"
            :checked="activeTypes.includes(type)"
            @change="toggleType(type, ($event.target as HTMLInputElement).checked)"
          />
          <i class="swatch" :style="{ background: EDGE_COLORS[type] }" />
          <span>{{ RELATION_TEXT[type] }}</span>
        </label>
      </div>
    </div>
    <div class="control">
      <span>搜索节点</span>
      <input
        :value="query"
        placeholder="显示名 / handle"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
      />
    </div>
    <div class="control">
      <span>布局</span>
      <select
        :value="layoutName"
        @change="emit('update:layoutName', ($event.target as HTMLSelectElement).value as LayoutName)"
      >
        <option v-for="opt in LAYOUT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
    </div>
    <label class="check row">
      <input
        type="checkbox"
        :checked="hideIsolated"
        @change="emit('update:hideIsolated', ($event.target as HTMLInputElement).checked)"
      />
      <span>隐藏孤立节点</span>
    </label>
    <div class="actions">
      <button class="btn" @click="emit('fit')">适应屏幕</button>
      <button class="btn" @click="emit('relayout')">重新布局</button>
    </div>
    <div class="actions">
      <button class="btn primary" :disabled="loading" @click="emit('sync')">
        {{ loading ? "同步中…" : "同步采集数据" }}
      </button>
    </div>
    <div class="stats-line muted">
      {{ stats.visible_accounts }} / {{ stats.total_accounts }} 节点 ·
      {{ stats.visible_edges }} / {{ stats.total_edges }} 边
    </div>
  </section>
</template>

<style scoped>
.control { display: grid; gap: 6px; margin-bottom: 10px; }
.control span { color: var(--muted); font-size: 12px; }
.checks { display: grid; gap: 6px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.check.row { color: var(--muted); margin: 4px 0; }
.check input { width: 16px; height: 16px; }
.swatch { width: 12px; height: 4px; border-radius: 2px; display: inline-block; }
select, input { width: 100%; border: 1px solid var(--line); border-radius: 7px; padding: 8px 9px; background: #fff; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.btn { flex: 1; height: 34px; border: 1px solid var(--line); border-radius: 7px; background: #fff; cursor: pointer; }
.btn.primary { background: var(--green); color: #fff; border-color: var(--green); }
.btn:disabled { opacity: 0.6; cursor: progress; }
.stats-line { margin-top: 8px; font-size: 12px; }
.muted { color: var(--muted); }
</style>
