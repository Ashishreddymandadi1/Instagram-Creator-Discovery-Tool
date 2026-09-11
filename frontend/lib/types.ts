// Mirrors backend/app/models/schemas.py

export type DataStatus = "live" | "cached" | "partial" | "demo";

export interface Evidence {
  source_provider: string;
  source_url: string;
  title: string | null;
  snippet: string | null;
  retrieved_at: string;
  synthetic: boolean;
}

export interface ScoreBreakdown {
  geo_search_relevance: number;
  topic_relevance: number;
  content_relevance: number;
  creator_fit: number;
}

export interface CreatorResult {
  id: number;
  name: string | null;
  handle: string;
  instagram_url: string;
  relevant_topics: string[];
  geo_concepts: string[];
  content_summary: string;
  bio_or_summary: string | null;
  score: number;
  score_breakdown: ScoreBreakdown;
  explanation: string;
  confidence: number;
  data_status: DataStatus;
  last_updated: string;
  evidence: Evidence[];
  warnings: string[];
  follower_count: number | null;
  engagement_rate: number | null;
  verified: boolean | null;
  location: string | null;
}

export interface SearchCriteria {
  topics: string[];
  geo_related_topics: string[];
  creator_types: string[];
  search_queries: string[];
}

export interface SearchResponse {
  brief: string;
  criteria: SearchCriteria;
  results: CreatorResult[];
  candidate_count: number;
  returned_count: number;
  data_status: DataStatus;
  warnings: string[];
}

export interface RefreshResponse {
  creator: CreatorResult;
  warnings: string[];
}

export interface HealthResponse {
  status: string;
  llm_configured: boolean;
  llm_model: string;
  search_providers: string[];
  cache_ttl_hours: number;
}

export const SCORE_WEIGHTS: { key: keyof ScoreBreakdown; label: string; weight: number }[] = [
  { key: "geo_search_relevance", label: "GEO / Search Relevance", weight: 35 },
  { key: "topic_relevance", label: "Topic Relevance", weight: 30 },
  { key: "content_relevance", label: "Content Relevance", weight: 25 },
  { key: "creator_fit", label: "Creator Fit", weight: 10 },
];
