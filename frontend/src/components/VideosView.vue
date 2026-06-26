<script setup lang="ts">
// Video explorer: searchable/filterable list on the left, player + provenance
// detail (occurrences, evidence, same-content group) + labeling on the right.
import { computed, onMounted, ref, watch } from "vue";
import { downloadXVideos, fetchVideoDetail, fetchVideos, labelVideo } from "../api";
import type { VideoDetail, VideoOriginLabel, VideoSummary } from "../types";

const props = defineProps<{ focusVideoId: number | null }>();
const emit = defineEmits<{ (e: "toast", message: string): void }>();

const videos = ref<VideoSummary[]>([]);
const loadingList = ref(true);
const search = ref("");
const platform = ref("all");
const playable = ref("all");
const selectedId = ref<number | null>(null);
const detail = ref<VideoDetail | null>(null);
const loadingDetail = ref(false);
const label = ref<VideoOriginLabel>("unknown");
const notes = ref("");
const saving = ref(false);
const downloading = ref(false);

const ORIGIN_TEXT: Record<VideoOriginLabel, string> = {
  unknown: "未知",
  likely_original: "疑似原创",
  needs_review: "待核验",
  likely_non_original: "疑似搬运",
  repost: "明确转载",
};

function pillClass(label: string): string {
  if (label === "likely_original") return "green";
  if (label === "needs_review") return "amber";
  if (label === "likely_non_original" || label === "repost") return "red";
  return "";
}

function titleOf(v: VideoSummary | VideoDetail): string {
  return v.title || (v.platform === "91porn" ? `91视频 #${v.id}` : `Video #${v.id}`);
}

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
  return date.toLocaleString("zh-CN", { hour12: false });
}

const platforms = computed(() =>
  Array.from(new Set(videos.value.map((v) => v.platform).filter(Boolean) as string[])).sort(),
);

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return videos.value.filter((v) => {
    if (platform.value !== "all" && v.platform !== platform.value) return false;
    if (playable.value === "playable" && !v.has_playback) return false;
    if (playable.value === "metadata" && v.has_playback) return false;
    if (!q) return true;
    return [v.title, v.author_name, v.author_handle, v.platform, v.topic_label]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
});

async function loadList() {
  loadingList.value = true;
  try {
    videos.value = await fetchVideos(500);
    if (!selectedId.value && videos.value.length) {
      const first = videos.value.find((v) => v.has_playback) || videos.value[0];
      await select(first.id);
    }
  } finally {
    loadingList.value = false;
  }
}

async function select(id: number) {
  selectedId.value = id;
  detail.value = null;
  loadingDetail.value = true;
  try {
    detail.value = await fetchVideoDetail(id);
    label.value = (detail.value.origin_label as VideoOriginLabel) || "unknown";
    notes.value = detail.value.origin_notes || "";
  } finally {
    loadingDetail.value = false;
  }
}

async function saveLabel() {
  if (!selectedId.value) return;
  saving.value = true;
  try {
    detail.value = await labelVideo(selectedId.value, label.value, notes.value || null);
    const idx = videos.value.findIndex((v) => v.id === selectedId.value);
    if (idx >= 0) videos.value[idx] = { ...videos.value[idx], origin_label: label.value };
    emit("toast", "已保存视频标签");
  } finally {
    saving.value = false;
  }
}

async function download(limit: number) {
  downloading.value = true;
  try {
    const r = await downloadXVideos(limit, true);
    emit("toast", `解析 ${r.resolved ?? 0}，下载 ${r.downloaded ?? 0}，失败 ${r.failed ?? 0}`);
    await loadList();
  } finally {
    downloading.value = false;
  }
}

watch(
  () => props.focusVideoId,
  (id) => {
    if (id != null) select(id);
  },
);

onMounted(loadList);
</script>

<template>
  <div class="videos-shell">
    <div class="videos-bar">
      <input v-model="search" class="grow" placeholder="搜索标题 / 作者 / 平台" />
      <select v-model="platform">
        <option value="all">全部平台</option>
        <option v-for="p in platforms" :key="p" :value="p">{{ p }}</option>
      </select>
      <select v-model="playable">
        <option value="all">全部</option>
        <option value="playable">可播放</option>
        <option value="metadata">仅元数据</option>
      </select>
      <button class="btn" :disabled="downloading" @click="download(10)">
        {{ downloading ? "下载中…" : "下载 10 条 X 视频" }}
      </button>
    </div>

    <div class="videos-body">
      <div class="video-list">
        <div v-if="loadingList" class="empty">加载中…</div>
        <button
          v-for="v in filtered"
          :key="v.id"
          class="video-item"
          :class="{ active: v.id === selectedId }"
          @click="select(v.id)"
        >
          <div class="thumb">
            <img v-if="v.thumbnail_url" :src="v.thumbnail_url" loading="lazy" />
          </div>
          <div class="meta">
            <div class="item-title">{{ titleOf(v) }}</div>
            <div class="pills">
              <span class="pill">{{ v.platform || "" }}</span>
              <span class="pill" :class="v.has_playback ? 'green' : 'amber'">
                {{ v.has_playback ? "可播放" : "仅元数据" }}
              </span>
              <span v-if="v.origin_label && v.origin_label !== 'unknown'" class="pill" :class="pillClass(v.origin_label)">
                {{ ORIGIN_TEXT[v.origin_label as VideoOriginLabel] || v.origin_label }}
              </span>
            </div>
          </div>
        </button>
        <div v-if="!loadingList && !filtered.length" class="empty">没有匹配的视频</div>
      </div>

      <div class="player-pane">
        <div v-if="loadingDetail" class="empty">加载中…</div>
        <template v-else-if="detail">
          <div class="player-frame">
            <video v-if="detail.has_playback && detail.playback_url" controls preload="metadata" :poster="detail.thumbnail_url || undefined">
              <source :src="detail.playback_url" />
            </video>
            <div v-else class="poster">
              <img v-if="detail.thumbnail_url" :src="detail.thumbnail_url" />
              <span>该条目没有稳定视频直链，已保存封面和来源证据。</span>
            </div>
          </div>

          <h2 class="player-title">{{ titleOf(detail) }}</h2>
          <div class="pills">
            <span class="pill">{{ detail.platform || "" }}</span>
            <span class="pill" :class="detail.has_playback ? 'green' : 'amber'">
              {{ detail.has_playback ? "网页播放器" : "仅元数据" }}
            </span>
            <span class="pill">{{ formatDate(detail.display_time) || "未知时间" }}</span>
            <span v-if="detail.author_handle" class="pill">@{{ detail.author_handle }}</span>
            <span v-if="detail.topic_label" class="pill">{{ detail.topic_label }}</span>
            <span v-if="detail.duplicate_count && detail.duplicate_count > 1" class="pill red">
              同内容 {{ detail.duplicate_count }} 条
            </span>
          </div>

          <div class="actions">
            <a v-if="detail.source_url" class="btn primary" :href="detail.source_url" target="_blank" rel="noreferrer">打开来源</a>
            <a v-if="detail.author_profile_url" class="btn" :href="detail.author_profile_url" target="_blank" rel="noreferrer">作者主页</a>
            <a v-if="detail.media_url" class="btn" :href="detail.media_url" target="_blank" rel="noreferrer">媒体直链</a>
          </div>

          <section v-if="detail.occurrences.length" class="sub">
            <h3>出现位置 ({{ detail.occurrences.length }})</h3>
            <div class="occ-list">
              <div v-for="(o, i) in detail.occurrences" :key="i" class="occ">
                <div class="occ-head">
                  <span class="pill">{{ o.platform }}</span>
                  <span class="muted">{{ formatDate(o.published_at || o.first_seen_at) }}</span>
                  <a v-if="o.author_profile_url" class="link" :href="o.author_profile_url" target="_blank" rel="noreferrer">@{{ o.author_handle }}</a>
                </div>
                <a v-if="o.source_url" class="link break" :href="o.source_url" target="_blank" rel="noreferrer">{{ o.source_url }}</a>
              </div>
            </div>
          </section>

          <section v-if="detail.evidence.length" class="sub">
            <h3>来源证据 ({{ detail.evidence.length }})</h3>
            <div class="occ-list">
              <div v-for="(e, i) in detail.evidence" :key="i" class="occ">
                <div class="occ-head">
                  <span class="pill">{{ e.evidence_type }}</span>
                  <span class="muted">{{ e.extracted_time || "—" }}</span>
                  <span class="pill">置信 {{ (e.confidence_score ?? 0).toFixed(2) }}</span>
                </div>
                <a v-if="e.evidence_url" class="link break" :href="e.evidence_url" target="_blank" rel="noreferrer">{{ e.evidence_url }}</a>
              </div>
            </div>
          </section>

          <section v-if="detail.group_videos.length > 1" class="sub">
            <h3>同内容组 ({{ detail.group_videos.length }})</h3>
            <div class="occ-list">
              <button v-for="g in detail.group_videos" :key="g.id" class="group-row" @click="select(g.id)">
                <span class="group-title">{{ g.title || `#${g.id}` }}</span>
                <span class="pill">{{ g.platform || "" }}</span>
                <span class="pill" :class="g.has_playback ? 'green' : 'amber'">{{ g.has_playback ? "可播" : "元数据" }}</span>
              </button>
            </div>
          </section>

          <section class="sub panel-label">
            <h3>视频打标</h3>
            <select v-model="label">
              <option value="unknown">未知</option>
              <option value="likely_original">疑似原创</option>
              <option value="needs_review">待核验</option>
              <option value="likely_non_original">疑似搬运</option>
              <option value="repost">明确转载</option>
            </select>
            <textarea v-model="notes" placeholder="备注" />
            <button class="btn primary" :disabled="saving" @click="saveLabel">
              {{ saving ? "保存中…" : "保存视频标签" }}
            </button>
          </section>
        </template>
        <div v-else class="empty">选择一个视频</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.videos-shell { height: 100%; min-height: 0; display: grid; grid-template-rows: 50px minmax(0,1fr); border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: var(--shadow); overflow: hidden; }
.videos-bar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--line); background: #fbfcfc; }
.videos-bar .grow { flex: 1; }
.videos-bar input, .videos-bar select { border: 1px solid var(--line); border-radius: 7px; padding: 7px 9px; background: #fff; }
.videos-body { min-height: 0; display: grid; grid-template-columns: 340px minmax(0,1fr); }
.video-list { min-height: 0; overflow: auto; border-right: 1px solid var(--line); padding: 10px; display: grid; gap: 8px; align-content: start; }
.video-item { display: grid; grid-template-columns: 96px minmax(0,1fr); gap: 10px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: #fff; cursor: pointer; text-align: left; align-items: center; }
.video-item:hover { border-color: var(--line-strong); }
.video-item.active { border-color: var(--green); box-shadow: inset 3px 0 0 var(--green); }
.thumb { width: 96px; aspect-ratio: 16/10; border-radius: 6px; background: linear-gradient(135deg,#dae3e0,#b8c8c4); overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.meta { min-width: 0; }
.item-title { font-size: 13px; line-height: 1.3; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; }
.pills { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.pill { display: inline-flex; align-items: center; min-height: 20px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--line); background: #f8faf9; color: var(--muted); font-size: 11px; }
.pill.green { color: var(--green); border-color: rgba(22,120,98,.28); background: #edf7f3; }
.pill.amber { color: var(--amber); border-color: rgba(165,104,24,.28); background: #fff8ed; }
.pill.red { color: var(--red); border-color: rgba(175,63,74,.28); background: #fff1f3; }

.player-pane { min-width: 0; min-height: 0; overflow: auto; padding: 14px; display: grid; gap: 12px; align-content: start; }
.player-frame { background: #101417; border-radius: 8px; overflow: hidden; aspect-ratio: 16/9; }
.player-frame video { width: 100%; height: 100%; display: block; background: #101417; }
.poster { width: 100%; height: 100%; position: relative; display: grid; place-items: center; color: #fff; }
.poster img { width: 100%; height: 100%; object-fit: cover; opacity: .7; }
.poster span { position: absolute; left: 14px; right: 14px; bottom: 14px; padding: 10px; border-radius: 8px; background: rgba(16,20,23,.84); font-size: 12px; }
.player-title { margin: 0; font-size: 19px; line-height: 1.25; overflow-wrap: anywhere; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.btn { height: 32px; padding: 0 12px; border: 1px solid var(--line); border-radius: 7px; background: #fff; cursor: pointer; display: inline-flex; align-items: center; text-decoration: none; }
.btn.primary { background: var(--green); color: #fff; border-color: var(--green); }
.btn:disabled { opacity: .6; cursor: progress; }
.link { color: var(--blue); }
.link.break { overflow-wrap: anywhere; font-size: 12px; display: block; }
.sub h3 { margin: 0 0 8px; font-size: 13px; }
.occ-list { display: grid; gap: 7px; }
.occ { border: 1px solid var(--line); border-radius: 8px; padding: 8px 9px; background: #fff; }
.occ-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.muted { color: var(--muted); font-size: 11px; }
.group-row { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 7px 9px; cursor: pointer; }
.group-row:hover { border-color: var(--line-strong); }
.group-title { flex: 1; min-width: 0; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.panel-label select, .panel-label textarea { width: 100%; border: 1px solid var(--line); border-radius: 7px; padding: 8px 9px; background: #fff; }
.panel-label textarea { min-height: 56px; resize: vertical; }
.panel-label .btn { width: 100%; justify-content: center; }
.empty { padding: 14px; color: var(--muted); font-size: 13px; }

@media (max-width: 900px) { .videos-body { grid-template-columns: 1fr; } .video-list { max-height: 320px; border-right: 0; border-bottom: 1px solid var(--line); } }
</style>
