"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { load } from "@2gis/mapgl";
import type { ServiceId, GeoPoint, MapFocusCommand, MapServiceSelection } from "../../app/[locale]/(public)/catalog/CatalogClient";

export type MapServiceMarker = {
    id: number;
    title: string;
    latitude: number;
    longitude: number;
    price?: string | number | null;
    city?: string | null;
    providerName?: string | null;
    cover?: string | null;
};

interface DGISMapProps {
    locale: string;
    initialCenter?: GeoPoint;
    focusCommand?: MapFocusCommand | null;
    zoom?: number;
    className?: string;
    markers?: MapServiceMarker[];
    totalServicesCount?: number;
    selectedServiceId?: ServiceId | null;
    hoveredServiceId?: ServiceId | null;
    onSelectService?: (selection: MapServiceSelection | null) => void;
    onBoundsChange?: (
        bounds: {
            west: number;
            south: number;
            east: number;
            north: number;
        },
        meta?: {
            isUser: boolean;
        }
    ) => void;
    onReady?: (mapInstance: any) => void;
    onError?: (err: Error) => void;
}

// Safe pre-encoded SVG icons for markers to avoid user input HTML injection
const VIOLET_PIN = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%238b5cf6" width="32" height="32"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;
const SELECTED_PIN = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23db2777" width="40" height="40"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;

export default function DGISMap({
    locale,
    initialCenter,
    focusCommand,
    zoom,
    className = "w-full h-full",
    markers = [],
    totalServicesCount = 0,
    selectedServiceId = null,
    hoveredServiceId = null,
    onSelectService,
    onBoundsChange,
    onReady,
    onError
}: DGISMapProps) {
    const t = useTranslations("catalog");
    const containerRef = useRef<HTMLDivElement>(null);
    const mapInstanceRef = useRef<any>(null);
    const mapglAPIRef = useRef<any>(null);
    const markersRef = useRef<Map<number, any>>(new Map());
    const isInitializingRef = useRef<boolean>(false);
    
    const onBoundsChangeRef = useRef(onBoundsChange);
    useEffect(() => {
        onBoundsChangeRef.current = onBoundsChange;
    }, [onBoundsChange]);

    const [loadError, setLoadError] = useState<string | null>(null);
    const [mapInstanceReady, setMapInstanceReady] = useState<boolean>(false);

    // Load environment default settings
    const defaultLat = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LAT || "43.238949");
    const defaultLng = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LNG || "76.889709");
    const defaultZoom = parseInt(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_ZOOM || "12", 10);
    const apiKey = process.env.NEXT_PUBLIC_2GIS_MAP_KEY;

    // 1. Initialize MapGL core instance using initialCenter only once (Task 6)
    useEffect(() => {
        if (typeof window === "undefined" || !containerRef.current) return;
        if (isInitializingRef.current || mapInstanceRef.current) return;

        if (!apiKey) {
            const err = new Error("NEXT_PUBLIC_2GIS_MAP_KEY is missing");
            setLoadError("missingKey");
            if (onError) onError(err);
            return;
        }

        isInitializingRef.current = true;
        let isUnmounted = false;

        const initMap = async () => {
            try {
                const mapglAPI = await load();
                if (isUnmounted) return;
                mapglAPIRef.current = mapglAPI;

                const mapCenter: [number, number] = initialCenter 
                    ? [initialCenter.longitude, initialCenter.latitude] 
                    : [defaultLng, defaultLat];
                
                const mapZoom = zoom ?? defaultZoom;

                const map = new mapglAPI.Map(containerRef.current!, {
                    center: mapCenter,
                    zoom: mapZoom,
                    key: apiKey,
                });

                mapInstanceRef.current = map;
                setMapInstanceReady(true);

                if (onReady) {
                    onReady(map);
                }
            } catch (err: any) {
                console.error("Failed to initialize 2GIS MapGL JS:", err);
                if (!isUnmounted) {
                    setLoadError("unavailable");
                }
                if (onError) {
                    onError(err instanceof Error ? err : new Error(String(err)));
                }
            } finally {
                isInitializingRef.current = false;
            }
        };

        initMap();

        const currentMarkers = markersRef.current;
        return () => {
            isUnmounted = true;
            // Clean up all markers
            currentMarkers.forEach((marker) => marker.destroy());
            currentMarkers.clear();

            if (mapInstanceRef.current) {
                mapInstanceRef.current.destroy();
                mapInstanceRef.current = null;
            }
            setMapInstanceReady(false);
            isInitializingRef.current = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiKey, defaultLat, defaultLng, defaultZoom, onError, onReady]);

    // 2. Render and manage marker instances lifecycle (Task 4)
    useEffect(() => {
        const map = mapInstanceRef.current;
        const mapglAPI = mapglAPIRef.current;
        if (!map || !mapglAPI || !mapInstanceReady) return;

        const currentMarkerIds = new Set(markers.map((m) => m.id));

        // A) Remove obsolete markers
        markersRef.current.forEach((markerInstance, id) => {
            if (!currentMarkerIds.has(id)) {
                markerInstance.destroy();
                markersRef.current.delete(id);
            }
        });

        // B) Create or update current markers
        markers.forEach((markerData) => {
            const isSelected = markerData.id === selectedServiceId;
            const isHovered = markerData.id === hoveredServiceId;
            const isHighlighted = isSelected || isHovered;
            const markerIcon = isHighlighted ? SELECTED_PIN : VIOLET_PIN;
            const markerSize: [number, number] = isHighlighted ? [40, 40] : [32, 32];
            const markerAnchor: [number, number] = isHighlighted ? [20, 40] : [16, 32];

            let markerInstance = markersRef.current.get(markerData.id);

            if (!markerInstance) {
                // Instantiate new MapGL marker
                markerInstance = new mapglAPI.Marker(map, {
                    coordinates: [markerData.longitude, markerData.latitude],
                    icon: markerIcon,
                    size: markerSize,
                    anchor: markerAnchor,
                    zIndex: isHighlighted ? 1000 : 0,
                });

                // Attach click handler (Task 6 & 12)
                markerInstance.on("click", () => {
                    if (onSelectService) {
                        onSelectService({
                            serviceId: markerData.id,
                            latitude: markerData.latitude,
                            longitude: markerData.longitude,
                        });
                    }
                });

                markersRef.current.set(markerData.id, markerInstance);
            } else {
                // Update existing marker's icon option dynamically
                markerInstance.setIcon({
                    url: markerIcon,
                    size: markerSize,
                    anchor: markerAnchor,
                });
            }
        });
    }, [markers, selectedServiceId, hoveredServiceId, mapInstanceReady, onSelectService]);

    const lastFocusRequestIdRef = useRef<number | null>(null);
    const suppressProgrammaticMoveRef = useRef<boolean>(false);
    const suppressionTimeoutRef = useRef<any>(null);

    // 3. React to explicit focus commands using requestId protocol (Task 7 & 10 & 11)
    useEffect(() => {
        const map = mapInstanceRef.current;
        if (!map || !mapInstanceReady || !focusCommand) return;

        if (lastFocusRequestIdRef.current === focusCommand.requestId) return;

        const lat = Number(focusCommand.latitude);
        const lng = Number(focusCommand.longitude);

        if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 185) {
            return;
        }

        lastFocusRequestIdRef.current = focusCommand.requestId;

        // Diagnostic logs (Task 14)
        if (process.env.NODE_ENV === "development") {
            console.info("[Map focus 2GIS]", {
                serviceId: focusCommand.serviceId,
                latitude: focusCommand.latitude,
                longitude: focusCommand.longitude,
                requestId: focusCommand.requestId,
                source: focusCommand.source,
            });
        }

        // Suppress programmatic move from triggering "Search this area" button
        suppressProgrammaticMoveRef.current = true;
        if (suppressionTimeoutRef.current) {
            clearTimeout(suppressionTimeoutRef.current);
        }

        map.setCenter([lng, lat]);

        suppressionTimeoutRef.current = setTimeout(() => {
            suppressProgrammaticMoveRef.current = false;
        }, 1000); // 1s timeout to clear suppression

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [focusCommand?.requestId, mapInstanceReady]);

    useEffect(() => {
        return () => {
            if (suppressionTimeoutRef.current) {
                clearTimeout(suppressionTimeoutRef.current);
            }
        };
    }, []);

    // 4. Listen to bounds change events and propagate them (Task 11)
    useEffect(() => {
        const map = mapInstanceRef.current;
        if (!map || !mapInstanceReady || !onBoundsChangeRef.current) return;

        const handleMoveEnd = (e: any) => {
            try {
                const b = map.getBounds();
                if (b && b.southWest && b.northEast) {
                    // If programmatic move is active, treat isUser as false
                    const isUser = suppressProgrammaticMoveRef.current ? false : (e && typeof e.isUser === "boolean" ? e.isUser : true);
                    if (onBoundsChangeRef.current) {
                        onBoundsChangeRef.current(
                            {
                                west: b.southWest[0],
                                south: b.southWest[1],
                                east: b.northEast[0],
                                north: b.northEast[1],
                            },
                            { isUser }
                        );
                    }
                }
            } catch (err) {
                console.error("Error getting map bounds in 2GIS:", err);
            }
        };

        map.on("moveend", handleMoveEnd);

        // Emit initial bounds
        handleMoveEnd({ isUser: false });

        return () => {
            if (mapInstanceRef.current) {
                mapInstanceRef.current.off("moveend", handleMoveEnd);
            }
        };
    }, [mapInstanceReady]);

    const handleDismiss = () => {
        if (onSelectService) {
            onSelectService(null);
        }
    };

    if (loadError) {
        const titleKey = loadError === "missingKey" ? "map.missingKey" : "map.unavailableTitle";
        const descKey = "map.unavailableDescription";
        const fallbackKey = "map.listStillAvailable";

        return (
            <div className="flex flex-col items-center justify-center bg-neutral-50 border border-neutral-200 rounded-2xl p-6 min-h-[420px] text-center">
                <div className="w-16 h-16 bg-neutral-100 text-neutral-400 rounded-full flex items-center justify-center mb-4">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <h3 className="text-lg font-bold text-neutral-900 mb-2">
                    {t(titleKey) || "Map Unavailable"}
                </h3>
                <p className="text-neutral-500 max-w-md mx-auto text-sm mb-4">
                    {t(descKey) || "The interactive map is temporarily unavailable."}
                </p>
                <p className="text-neutral-400 max-w-md mx-auto text-xs italic">
                    {t(fallbackKey) || "The service list remains fully functional."}
                </p>
            </div>
        );
    }

    // Empty state if results exist but none have coordinates
    if (markers.length === 0) {
        return (
            <div className="py-16 text-center rounded-2xl bg-neutral-50 border border-neutral-200 p-6 min-h-[420px] flex flex-col justify-center items-center">
                <div className="w-16 h-16 bg-neutral-100 text-neutral-400 rounded-full flex items-center justify-center mb-4">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </div>
                <h3 className="text-lg font-bold text-neutral-900 mb-2">
                    {t("map.noLocationsTitle") || "No locations available"}
                </h3>
                <p className="text-neutral-500 max-w-md mx-auto text-sm">
                    {t("map.noLocationsDescription") || "None of the currently matching services have coordinates set."}
                </p>
            </div>
        );
    }

    const selectedMarker = markers.find((m) => m.id === selectedServiceId);

    return (
        <div className="relative border border-neutral-200 rounded-2xl overflow-hidden shadow-sm bg-neutral-50 w-full min-h-[420px] md:h-[500px] flex flex-col">
            {/* Map Header Title / Count Bar */}
            <div className="bg-white border-b border-neutral-100 px-6 py-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></span>
                    <span className="text-sm font-bold text-neutral-700">
                        {t("map.markersShown", { count: markers.length, total: totalServicesCount }) || `Showing ${markers.length} of ${totalServicesCount} services on map`}
                    </span>
                </div>
            </div>

            {/* 2GIS Map Container */}
            <div ref={containerRef} className={className} style={{ width: "100%", height: "100%", flex: 1 }} />

            {/* React-controlled Preview Card */}
            {selectedMarker && (
                <div className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-white border border-neutral-200 rounded-3xl p-5 shadow-xl z-10 transition-all duration-200">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                            <span className="inline-block px-2.5 py-0.5 text-[9px] font-extrabold uppercase tracking-widest text-violet-750 bg-violet-50 border border-violet-100 rounded-full mb-2">
                                {selectedMarker.city}
                            </span>
                            <h4 className="font-extrabold text-neutral-900 text-sm truncate mb-0.5" title={selectedMarker.title}>
                                {selectedMarker.title}
                            </h4>
                            <p className="text-xs text-neutral-500 font-semibold mb-3">
                                {t("map.selectedService") || "Provider"}: {selectedMarker.providerName || "—"}
                            </p>
                            <div className="text-base font-black text-neutral-955 mb-4">
                                ₸ {parseInt(String(selectedMarker.price || 0)).toLocaleString()}
                            </div>
                            <div className="flex gap-2">
                                <a
                                    href={`/${locale}/service/${selectedMarker.id}/`}
                                    className="bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-xs hover:shadow-sm transition decoration-none text-center flex-1"
                                >
                                    {t("map.viewService") || "View service"}
                                </a>
                                <button
                                    onClick={handleDismiss}
                                    className="border border-neutral-200 text-neutral-600 hover:bg-neutral-50 font-bold text-xs px-4 py-2.5 rounded-xl transition"
                                >
                                    {t("map.closePreview") || "Close"}
                                </button>
                            </div>
                        </div>
                        <button
                            onClick={handleDismiss}
                            className="text-neutral-400 hover:text-neutral-600 transition p-1 shrink-0"
                            aria-label="Close Preview"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
