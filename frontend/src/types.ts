// Types mirroring the FastAPI graph payload (see video_hunter/db.list_x_account_graph).

export type RelationshipType = "following" | "reposted" | "bookmarked_author";

export type OriginalityLabel =
  | "likely_original"
  | "needs_review"
  | "likely_non_original"
  | "reposter"
  | "unknown";

export interface GraphNode {
  id: number;
  handle: string;
  display_name: string | null;
  profile_url: string | null;
  avatar_url: string | null;
  account_kind: string;
  bookmarked_posts: number;
  bookmarked_video_posts: number;
  timeline_posts: number;
  timeline_video_posts: number;
  own_posts: number;
  declared_reposts: number;
  likely_non_original_posts: number;
  possible_non_original_posts: number;
  originality_label: OriginalityLabel;
  manual_label: string | null;
  effective_label: OriginalityLabel;
  risk_score: number;
  video_count: number;
  in_degree: number;
  out_degree: number;
  degree: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: RelationshipType;
  weight: number;
  sample_evidence_url: string | null;
}

export interface GraphStats {
  total_accounts: number;
  visible_accounts: number;
  total_edges: number;
  visible_edges: number;
  hidden_single_edge_nodes: number;
  relationship_types: string[];
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export interface RelationRow {
  relationship_type: string;
  weight: number;
  sample_evidence_url: string | null;
  handle: string;
  display_name: string | null;
  profile_url: string | null;
}

export interface AccountVideo {
  id: number;
  title: string | null;
  has_playback: boolean;
  platform: string | null;
}

export interface VideoSummary {
  id: number;
  title: string | null;
  description: string | null;
  status: string;
  platform: string | null;
  source_url: string | null;
  media_url: string | null;
  published_at: string | null;
  first_seen_at: string | null;
  author_name: string | null;
  author_handle: string | null;
  author_profile_url: string | null;
  thumbnail_url: string | null;
  topic_label: string | null;
  has_playback: boolean;
  playback_url: string | null;
  display_time: string | null;
  origin_label: string;
  origin_notes: string | null;
  duplicate_count: number | null;
  earliest_platform: string | null;
  earliest_source_url: string | null;
  earliest_published_at: string | null;
}

export interface VideoOccurrence {
  id: number;
  platform: string;
  source_url: string;
  media_url: string | null;
  platform_item_id: string;
  author_handle: string | null;
  author_profile_url: string | null;
  published_at: string | null;
  first_seen_at: string;
  thumbnail_url: string | null;
  has_playback: boolean;
  raw_metadata: Record<string, unknown>;
}

export interface VideoEvidence {
  evidence_type: string;
  evidence_url: string | null;
  extracted_time: string | null;
  confidence_score: number;
  raw_payload: Record<string, unknown>;
}

export interface GroupVideo {
  id: number;
  title: string | null;
  status: string;
  platform: string | null;
  source_url: string | null;
  media_url: string | null;
  published_at: string | null;
  has_playback: boolean;
  playback_url: string | null;
}

export interface VideoDetail extends VideoSummary {
  occurrences: VideoOccurrence[];
  evidence: VideoEvidence[];
  group_videos: GroupVideo[];
}

export type VideoOriginLabel =
  | "unknown"
  | "likely_original"
  | "needs_review"
  | "likely_non_original"
  | "repost";

export interface AccountDetail {
  handle: string;
  display_name: string | null;
  profile_url: string | null;
  account_kind: string;
  effective_label: OriginalityLabel;
  manual_label: string | null;
  originality_label: OriginalityLabel;
  notes: string | null;
  risk_score: number;
  video_count: number;
  in_degree: number;
  out_degree: number;
  bookmarked_posts: number;
  bookmarked_video_posts: number;
  timeline_posts: number;
  timeline_video_posts: number;
  own_posts: number;
  declared_reposts: number;
  likely_non_original_posts: number;
  possible_non_original_posts: number;
  outgoing: RelationRow[];
  incoming: RelationRow[];
  videos: AccountVideo[];
}
