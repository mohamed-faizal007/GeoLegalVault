import { geoHeaders, http, type GeoCoords } from "./http";

export interface DocumentOut {
  id: string;
  title: string;
  doc_type: string;
  classification: string;
  owner_id: string;
  status: string;
  current_version_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  retention_until: string | null;
  integrity_flag: string | null;
}

export interface DocumentListOut {
  items: DocumentOut[];
  page: number;
  limit: number;
  total: number;
}

export interface UploadResponse {
  document_id: string;
  version_id: string;
  sha256: string;
  status: string;
}

export interface DownloadResponse {
  url: string;
  expires_in_sec: number;
}

export interface TransitionResponse {
  document_id: string;
  status: string;
  version_id?: string | null;
  anchor_status?: string | null;
  tx_hash?: string | null;
}

export interface VersionOut {
  id: string;
  document_id: string;
  version_no: number;
  sha256: string;
  prev_version_hash: string | null;
  storage_key: string;
  size_bytes: number;
  mime: string;
  status: string;
  uploaded_by: string;
  uploaded_at: string;
  anchored: boolean;
  anchor_id: string | null;
}

export interface VersionListOut {
  items: VersionOut[];
}

export interface DocumentSearchParams {
  query?: string;
  status?: string;
  doc_type?: string;
  owner?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}

export function listDocuments(params: DocumentSearchParams = {}): Promise<DocumentListOut> {
  return http.get<DocumentListOut>("/documents", { ...params });
}

export function getDocument(documentId: string): Promise<DocumentOut> {
  return http.get<DocumentOut>(`/documents/${documentId}`);
}

export function listVersions(documentId: string): Promise<VersionListOut> {
  return http.get<VersionListOut>(`/documents/${documentId}/versions`);
}

export function downloadDocument(documentId: string, coords: GeoCoords): Promise<DownloadResponse> {
  return http.get<DownloadResponse>(`/documents/${documentId}/download`, undefined, {
    headers: geoHeaders(coords),
  });
}

export interface UploadFields {
  title: string;
  doc_type: string;
  classification: string;
  tags: string;
  amend_of?: string;
}

export function uploadDocument(
  file: File,
  fields: UploadFields,
  coords: GeoCoords,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", fields.title);
  formData.append("doc_type", fields.doc_type);
  formData.append("classification", fields.classification);
  formData.append("tags", fields.tags);
  if (fields.amend_of) formData.append("amend_of", fields.amend_of);

  return http.postForm<UploadResponse>("/documents", formData, { headers: geoHeaders(coords) });
}

export function submitDocument(documentId: string): Promise<TransitionResponse> {
  return http.post<TransitionResponse>(`/documents/${documentId}/submit`);
}

export function reviewDocument(
  documentId: string,
  decision: "approve" | "changes_requested",
  comment?: string,
): Promise<TransitionResponse> {
  return http.post<TransitionResponse>(`/documents/${documentId}/review`, { decision, comment });
}

export function approveDocument(
  documentId: string,
  coords: GeoCoords,
): Promise<TransitionResponse> {
  return http.post<TransitionResponse>(`/documents/${documentId}/approve`, undefined, {
    headers: geoHeaders(coords),
  });
}

export function amendDocument(
  documentId: string,
  reason: string,
  coords: GeoCoords,
): Promise<TransitionResponse> {
  return http.post<TransitionResponse>(
    `/documents/${documentId}/amend`,
    { reason },
    { headers: geoHeaders(coords) },
  );
}

export function archiveDocument(documentId: string): Promise<TransitionResponse> {
  return http.post<TransitionResponse>(`/documents/${documentId}/archive`);
}
