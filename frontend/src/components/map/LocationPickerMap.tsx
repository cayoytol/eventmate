"use client";

import { useEffect, useRef, useState } from "react";
import { load } from "@2gis/mapgl";

interface LocationPickerMapProps {
    latitude: number | null;
    longitude: number | null;
    onChangeLocation: (latitude: number, longitude: number) => void;
    disabled?: boolean;
}

const PIN_ICON = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23db2777" width="40" height="40"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;

export default function LocationPickerMap({
    latitude,
    longitude,
    onChangeLocation,
    disabled = false
}: LocationPickerMapProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapInstanceRef = useRef<any>(null);
    const mapglAPIRef = useRef<any>(null);
    const markerRef = useRef<any>(null);
    const isInitializingRef = useRef<boolean>(false);
    const [loadError, setLoadError] = useState<boolean>(false);

    const defaultLat = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LAT || "43.238949");
    const defaultLng = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LNG || "76.889709");
    const defaultZoom = parseInt(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_ZOOM || "12", 10);
    const apiKey = process.env.NEXT_PUBLIC_2GIS_MAP_KEY;

    useEffect(() => {
        if (typeof window === "undefined" || !containerRef.current) return;
        if (isInitializingRef.current || mapInstanceRef.current) return;

        if (!apiKey) {
            setLoadError(true);
            return;
        }

        isInitializingRef.current = true;
        let isUnmounted = false;

        const initMap = async () => {
            try {
                const mapglAPI = await load();
                if (isUnmounted) return;
                mapglAPIRef.current = mapglAPI;

                const centerCoords: [number, number] = (latitude !== null && longitude !== null)
                    ? [longitude, latitude]
                    : [defaultLng, defaultLat];

                const map = new mapglAPI.Map(containerRef.current!, {
                    center: centerCoords,
                    zoom: defaultZoom,
                    key: apiKey,
                });

                mapInstanceRef.current = map;

                // Handle click events
                map.on("click", (e: any) => {
                    if (disabled) return;
                    if (e && e.lngLat) {
                        const [lng, lat] = e.lngLat;
                        onChangeLocation(lat, lng);
                    }
                });

            } catch (err) {
                console.error("Failed to load 2GIS MapGL inside picker:", err);
                if (!isUnmounted) {
                    setLoadError(true);
                }
            } finally {
                isInitializingRef.current = false;
            }
        };

        initMap();

        return () => {
            isUnmounted = true;
            if (markerRef.current) {
                markerRef.current.destroy();
                markerRef.current = null;
            }
            if (mapInstanceRef.current) {
                mapInstanceRef.current.destroy();
                mapInstanceRef.current = null;
            }
            isInitializingRef.current = false;
        };
    }, [apiKey, defaultLat, defaultLng, defaultZoom, disabled]);

    // Handle marker position update
    useEffect(() => {
        const map = mapInstanceRef.current;
        const mapglAPI = mapglAPIRef.current;
        if (!map || !mapglAPI) return;

        if (latitude === null || longitude === null) {
            if (markerRef.current) {
                markerRef.current.destroy();
                markerRef.current = null;
            }
            return;
        }

        const coords: [number, number] = [longitude, latitude];

        if (markerRef.current) {
            markerRef.current.setCoordinates(coords);
        } else {
            markerRef.current = new mapglAPI.Marker(map, {
                coordinates: coords,
                icon: PIN_ICON,
                size: [40, 40],
                anchor: [20, 40],
            });
        }
    }, [latitude, longitude]);

    // Pan map to location on coordinate updates
    useEffect(() => {
        const map = mapInstanceRef.current;
        if (!map || latitude === null || longitude === null) return;
        map.setCenter([longitude, latitude], { duration: 500 });
    }, [latitude, longitude]);

    if (loadError) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-slate-50 border border-slate-200 rounded-2xl p-4 text-center">
                <span className="text-xs text-slate-400 font-semibold">
                    Map picker is unavailable (API key missing or WebGL unsupported).
                </span>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full h-full rounded-2xl overflow-hidden border border-slate-200 shadow-3xs" />
    );
}
