import { API_BASE_URL } from "../lib/env";

export interface HealthResponse {
  status: string;
  mongo: string;
  storage: string;
  chain: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}
