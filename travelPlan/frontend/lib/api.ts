export type TripCreatePayload = {
  city: string;
  days: number;
  budget_level: "low" | "mid" | "high";
  preferences: string[];
  avoid: string[];
  pace: "slow" | "balanced" | "fast";
  travel_note?: string;
};

export type TripEventPayload = {
  event_type: "weather" | "crowd" | "user_status";
  payload: Record<string, unknown>;
  source?: "manual" | "system";
  occurred_at?: string;
  location?: {
    lat: number;
    lng: number;
  };
};

export type ItineraryItem = {
  slot_id: string;
  poi_id: string;
  name: string;
  category: string;
  start_time: string;
  end_time: string;
  duration_minutes?: number;
  queue_minutes: number;
  crowd_index: number;
  ticket_left: number;
  booking_status: string;
  indoor: boolean;
  notes: string;
};

export type ItineraryDay = {
  day: number;
  date: string;
  items: ItineraryItem[];
};

export type Itinerary = {
  city: string;
  days: ItineraryDay[];
  meta: Record<string, unknown>;
};

export type TripCreateResponse = {
  trip_id: string;
  itinerary: Itinerary;
  rationale: string;
  agent_log_id: string;
};

export type TripResponse = {
  trip_id: string;
  itinerary: Itinerary;
  rationale: string;
};

export type ReplanDecision = {
  should_replan: boolean;
  primary_reason: string;
  selected_poi_id: string | null;
  alternatives: string[];
  tradeoffs: string[];
  user_message: string;
  confidence: number;
};

export type ReplanMeta = {
  // llm: 采用模型决策；fallback_rule: 采用规则兜底决策
  decision_source: "llm" | "fallback_rule";
  // 标记“本次是否发生过 LLM -> fallback”的降级路径
  fallback_used: boolean;
  // 以下字段用于可观测性（性能/排障/评估）
  latency_ms?: number | null;
  model?: string | null;
  error?: string | null;
  critic_passed?: boolean | null;
  itinerary_version?: number | null;
  prompt_variant?: string | null;
};

export type TripEventResponse = {
  updated_itinerary: Itinerary;
  alerts: string[];
  agent_log_id: string;
  decision?: ReplanDecision | null;
  meta?: ReplanMeta | null;
};

export type AgentLog = {
  id: string;
  stage: string;
  tool_name?: string;
  message: string;
  payload?: Record<string, unknown>;
  created_at: string;
};

export type AgentLogsResponse = {
  trip_id: string;
  logs: AgentLog[];
};

export type DecisionFeedbackPayload = {
  accepted: boolean;
  reason?: string;
};

export type DecisionFeedbackResponse = {
  trip_id: string;
  decision_id: string;
  accepted: boolean;
  reason?: string | null;
  decision_source?: string | null;
  event_type?: string | null;
  latency_ms?: number | null;
  created_at: string;
};

export type ItineraryVersion = {
  version_id: number;
  diff_summary: string;
  created_at: string;
};

export type TripVersionsResponse = {
  trip_id: string;
  current_version: number;
  versions: ItineraryVersion[];
};

export type TripRollbackResponse = {
  trip_id: string;
  restored_version: number;
  active_version: number;
  itinerary: Itinerary;
  rationale: string;
};

export type ReplanConfigResponse = {
  active_city: string;
  policy: Record<string, unknown>;
  prompt_variant: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createTrip(payload: TripCreatePayload): Promise<TripCreateResponse> {
  return request<TripCreateResponse>("/api/trips", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTrip(tripId: string): Promise<TripResponse> {
  return request<TripResponse>(`/api/trips/${tripId}`);
}

export async function sendTripEvent(
  tripId: string,
  payload: TripEventPayload,
): Promise<TripEventResponse> {
  // 事件驱动重规划：后端会返回更新后的 itinerary + 决策解释信息。
  return request<TripEventResponse>(`/api/trips/${tripId}/events`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTripLogs(tripId: string): Promise<AgentLogsResponse> {
  return request<AgentLogsResponse>(`/api/trips/${tripId}/logs`);
}

export async function sendDecisionFeedback(
  tripId: string,
  decisionId: string,
  payload: DecisionFeedbackPayload,
): Promise<DecisionFeedbackResponse> {
  return request<DecisionFeedbackResponse>(`/api/trips/${tripId}/decisions/${decisionId}/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTripVersions(tripId: string): Promise<TripVersionsResponse> {
  return request<TripVersionsResponse>(`/api/trips/${tripId}/versions`);
}

export async function rollbackTripVersion(tripId: string, versionId: number): Promise<TripRollbackResponse> {
  return request<TripRollbackResponse>(`/api/trips/${tripId}/versions/${versionId}/rollback`, {
    method: "POST",
  });
}

export async function getReplanConfig(city?: string): Promise<ReplanConfigResponse> {
  const query = city ? `?city=${encodeURIComponent(city)}` : "";
  return request<ReplanConfigResponse>(`/api/config/replan${query}`);
}
