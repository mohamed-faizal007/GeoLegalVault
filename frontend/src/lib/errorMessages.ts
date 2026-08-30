/**
 * Maps the server's structured error codes (Plan Part 15: `{"error":{"code":
 * ..., "message": ...}}`) to plain-language explanations, so a denied action
 * always tells the user WHICH gate stopped them — auth, role, or location —
 * per Phase 9's brief. Falls back to the server's own message for anything
 * not in this table, so nothing is ever silently swallowed.
 */
import { ApiError } from "../api/http";

const CODE_MESSAGES: Record<string, string> = {
  GEOFENCE_DENIED: "This action isn't permitted from your current location.",
  LOCATION_LOW_CONFIDENCE:
    "Your location signal isn't accurate enough for this action. Try again somewhere with a clearer GPS/network signal.",
  LOCATION_STALE: "Your location reading is too old. Refresh your location and try again.",
  INVALID_LOCATION: "Location data is missing or invalid — location access may be blocked.",
  FORBIDDEN: "You don't have permission to do this.",
  MAKER_CHECKER_VIOLATION: "You can't approve or review a document you uploaded yourself.",
  ILLEGAL_TRANSITION: "This document isn't in a state that allows that action right now.",
  VALIDATION_REQUIRED: "Missing required information for this action.",
  NOT_FOUND: "That item couldn't be found.",
  STORAGE_UNAVAILABLE: "The file storage service is temporarily unavailable. Try again shortly.",
  VALIDATION_ERROR: "The submitted data didn't pass validation.",
};

export function describeError(error: unknown): { code: string; message: string } {
  if (error instanceof ApiError) {
    return {
      code: error.code,
      message: CODE_MESSAGES[error.code] ?? error.message,
    };
  }
  if (error instanceof Error) {
    return { code: "UNKNOWN", message: error.message };
  }
  return { code: "UNKNOWN", message: "Something went wrong." };
}
