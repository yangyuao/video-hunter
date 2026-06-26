<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { LABEL_COLORS, LABEL_TEXT, RELATION_TEXT } from "../graph/style";
import type { AccountDetail } from "../types";

const props = defineProps<{
  account: AccountDetail | null;
  loading: boolean;
  saving: boolean;
}>();

const emit = defineEmits<{
  (e: "save", label: string, notes: string | null): void;
  (e: "focus", handle: string): void;
  (e: "openVideo", id: number): void;
}>();

const label = ref("unknown");
const notes = ref("");

watch(
  () => props.account?.handle,
  () => {
    label.value = props.account?.manual_label || props.account?.originality_label || "unknown";
    notes.value = props.account?.notes || "";
  },
  { immediate: true },
);

const labelPill = computed(() => LABEL_COLORS[props.account?.effective_label ?? "unknown"]);
const labelKey = computed(() => props.account?.effective_label ?? "unknown");

const relations = computed(() => {
  if (!props.account) return [] as { dir: string; type: string; weight: number; handle: string }[];
  const out = (props.account.outgoing || []).map((r) => ({
    dir: "→",
    type: r.relationship_type,
    weight: r.weight,
    handle: r.handle,
  }));
  const inc = (props.account.incoming || []).map((r) => ({
    dir: "←",
    type: r.relationship_type,
    weight: r.weight,
    handle: r.handle,
  }));
  return [...out, ...inc].slice(0, 24);
});

function relText(type: string): string {
  return RELATION_TEXT[type as keyof typeof RELATION_TEXT] || type;
}
</script>

<template>
  <section class="panel">
    <h2>作者详情</h2>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="!account" class="empty">点击图中节点查看作者</div>
    <div v-else class="account">
      <div class="account-head">
        <div class="account-name">{{ account.display_name || `@${account.handle}` }}</div>
        <div class="muted">@{{ account.handle }}</div>
        <div class="pills">
          <span class="pill" :style="{ color: labelPill, borderColor: labelPill }">
            {{ LABEL_TEXT[labelKey] }}
          </span>
          <span class="pill">{{ account.video_count }} 视频</span>
          <span class="pill">{{ account.in_degree }} 入 / {{ account.out_degree }} 出</span>
        </div>
        <a class="btn primary" :href="account.profile_url || `https://x.com/${account.handle}`" target="_blank" rel="noreferrer">
          打开主页
        </a>
      </div>

      <div class="metric-grid">
        <div class="metric"><span>书签</span><strong>{{ account.bookmarked_posts }}</strong></div>
        <div class="metric"><span>书签视频</span><strong>{{ account.bookmarked_video_posts }}</strong></div>
        <div class="metric"><span>近期贴文</span><strong>{{ account.timeline_posts }}</strong></div>
        <div class="metric"><span>近期视频</span><strong>{{ account.timeline_video_posts }}</strong></div>
        <div class="metric"><span>原创贴文</span><strong>{{ account.own_posts }}</strong></div>
        <div class="metric"><span>声明转发</span><strong>{{ account.declared_reposts }}</strong></div>
        <div class="metric"><span>疑似搬运</span><strong>{{ account.likely_non_original_posts }}</strong></div>
        <div class="metric"><span>待核验</span><strong>{{ account.possible_non_original_posts }}</strong></div>
      </div>

      <div class="subhead">打标</div>
      <select v-model="label">
        <option value="unknown">未知</option>
        <option value="likely_original">疑似原创</option>
        <option value="needs_review">待核验</option>
        <option value="likely_non_original">疑似搬运</option>
        <option value="reposter">转发型</option>
      </select>
      <textarea v-model="notes" placeholder="备注" />
      <button class="btn primary" :disabled="saving" @click="emit('save', label, notes || null)">
        {{ saving ? "保存中…" : "保存标签" }}
      </button>

      <div class="subhead">关系 ({{ relations.length }})</div>
      <div class="relation-list">
        <button v-for="(r, i) in relations" :key="i" class="relation-row" @click="emit('focus', r.handle)">
          <span class="dir">{{ r.dir }}</span>
          <span class="rel-handle">@{{ r.handle }}</span>
          <span class="pill small">{{ relText(r.type) }} {{ r.weight }}</span>
        </button>
      </div>

      <div class="subhead">作者视频 ({{ (account.videos || []).length }})</div>
      <div class="mini-list">
        <button
          v-for="v in (account.videos || []).slice(0, 18)"
          :key="v.id"
          class="mini-video"
          @click="emit('openVideo', v.id)"
        >
          <span class="video-title">{{ v.title || `#${v.id}` }}</span>
          <span class="pill small" :class="v.has_playback ? 'green' : 'amber'">
            {{ v.has_playback ? "可播" : "元数据" }}
          </span>
        </button>
        <div v-if="!(account.videos || []).length" class="empty">暂无视频</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.account { display: grid; gap: 10px; }
.account-head { display: grid; gap: 8px; }
.account-name { font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
.muted { color: var(--muted); font-size: 12px; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { display: inline-flex; align-items: center; min-height: 22px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--line); background: #f8faf9; color: var(--muted); font-size: 12px; }
.pill.small { font-size: 11px; min-height: 18px; padding: 1px 6px; }
.pill.green { color: var(--green); border-color: rgba(22,120,98,.28); background: #edf7f3; }
.pill.amber { color: var(--amber); border-color: rgba(165,104,24,.28); background: #fff8ed; }
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.metric { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fbfcfc; }
.metric span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 2px; }
.metric strong { font-size: 14px; }
.subhead { font-size: 13px; font-weight: 600; margin-top: 4px; }
select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 7px; padding: 8px 9px; background: #fff; }
textarea { min-height: 56px; resize: vertical; }
.btn { width: 100%; height: 34px; border: 1px solid var(--line); border-radius: 7px; background: #fff; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; text-decoration: none; }
.btn.primary { background: var(--green); color: #fff; border-color: var(--green); }
.btn:disabled { opacity: 0.6; cursor: progress; }
.relation-list, .mini-list { display: grid; gap: 6px; }
.relation-row { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 7px 9px; cursor: pointer; text-align: left; }
.relation-row:hover { border-color: var(--line-strong); }
.rel-handle { min-width: 0; overflow-wrap: anywhere; flex: 1; }
.dir { color: var(--muted); font-weight: 700; }
.mini-video { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 7px 9px; cursor: pointer; text-align: left; }
.video-title { flex: 1; min-width: 0; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { padding: 10px; color: var(--muted); font-size: 13px; }
</style>
