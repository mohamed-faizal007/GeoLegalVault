import { useCallback, useEffect, useState } from "react";

import type { GeoCoords } from "../api/http";

export class GeoLocationError extends Error {
  kind: "unsupported" | "denied" | "unavailable" | "timeout";

  constructor(kind: GeoLocationError["kind"], message: string) {
    super(message);
    this.kind = kind;
  }
}

/** One-shot geolocation read: {lat,lng,accuracy,timestamp}. Never decides
 * allow/deny — that's a server-side call (Guardrail #5/#6); this only
 * obtains the raw reading to attach to the next sensitive request. */
export function getCurrentLocation(): Promise<GeoCoords> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new GeoLocationError("unsupported", "This browser doesn't support geolocation."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp / 1000,
        });
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          reject(
            new GeoLocationError(
              "denied",
              "Location access was denied. Allow location access in your browser to continue.",
            ),
          );
        } else if (error.code === error.TIMEOUT) {
          reject(new GeoLocationError("timeout", "Getting your location timed out. Try again."));
        } else {
          reject(new GeoLocationError("unavailable", "Your location could not be determined."));
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  });
}

interface UseGeoLocationState {
  coords: GeoCoords | null;
  error: GeoLocationError | null;
  loading: boolean;
}

/** Reactive variant for pages that display/refresh the current reading
 * (Upload, Geofence Status) rather than just needing it once inline. */
export function useGeoLocation(autoStart = true) {
  const [state, setState] = useState<UseGeoLocationState>({
    coords: null,
    error: null,
    loading: autoStart,
  });

  const refresh = useCallback(() => {
    setState({ coords: null, error: null, loading: true });
    getCurrentLocation()
      .then((coords) => setState({ coords, error: null, loading: false }))
      .catch((error: GeoLocationError) => setState({ coords: null, error, loading: false }));
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (autoStart) refresh();
  }, []);

  return { ...state, refresh };
}
