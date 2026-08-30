import { http } from "./http";

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in_min: number;
}

export function login(email: string, password: string): Promise<AccessTokenResponse> {
  return http.anonymousPost<AccessTokenResponse>("/auth/login", { email, password });
}

export function refresh(): Promise<AccessTokenResponse> {
  return http.anonymousPost<AccessTokenResponse>("/auth/refresh");
}

export function logout(): Promise<void> {
  return http.post<void>("/auth/logout");
}
