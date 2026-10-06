import { http } from "./http";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  role: string;
  assigned_geofence_ids: string[];
  /** Which documents this user may open: this level and below (D-051). */
  clearance: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface UserListOut {
  items: UserOut[];
  page: number;
  limit: number;
  total: number;
}

export interface UserCreate {
  email: string;
  password: string;
  name: string;
  role: string;
  assigned_geofence_ids?: string[];
  clearance?: string;
}

export interface UserUpdate {
  name?: string;
  role?: string;
  assigned_geofence_ids?: string[];
  /** Send only when it changed: the server refuses any clearance change to one's own account. */
  clearance?: string;
  is_active?: boolean;
}

export function listUsers(page = 1, limit = 50): Promise<UserListOut> {
  return http.get<UserListOut>("/users", { page, limit });
}

export function createUser(payload: UserCreate): Promise<UserOut> {
  return http.post<UserOut>("/users", payload);
}

export function updateUser(id: string, payload: UserUpdate): Promise<UserOut> {
  return http.patch<UserOut>(`/users/${id}`, payload);
}
