import { http } from "./http";

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface GeoJSONPoint {
  type: "Point";
  coordinates: number[];
}

export interface GeofenceOut {
  id: string;
  name: string;
  region: GeoJSONPolygon;
  center: GeoJSONPoint | null;
  radius_m: number | null;
  active: boolean;
  created_at: string;
}

export interface GeofenceListOut {
  items: GeofenceOut[];
  page: number;
  limit: number;
  total: number;
}

export interface GeofenceCreate {
  name: string;
  region: GeoJSONPolygon;
}

export interface GeofenceUpdate {
  name?: string;
  active?: boolean;
}

export function listGeofences(page = 1, limit = 50): Promise<GeofenceListOut> {
  return http.get<GeofenceListOut>("/geofences", { page, limit });
}

export function createGeofence(payload: GeofenceCreate): Promise<GeofenceOut> {
  return http.post<GeofenceOut>("/geofences", payload);
}

export function updateGeofence(id: string, payload: GeofenceUpdate): Promise<GeofenceOut> {
  return http.patch<GeofenceOut>(`/geofences/${id}`, payload);
}
