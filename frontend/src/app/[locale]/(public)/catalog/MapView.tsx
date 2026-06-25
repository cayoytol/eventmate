"use client";

import { useEffect, useRef, useMemo } from "react";
import { useTranslations } from "next-intl";
import L from "leaflet";
import type { Service } from "@/types/catalog";
import type { ServiceId, GeoPoint, MapFocusCommand, MapServiceSelection } from "./CatalogClient";

// Import Leaflet CSS directly inside the MapView component to keep it self-contained
import "leaflet/dist/leaflet.css";

// Import default marker assets to override paths broken by Webpack compilation in Next.js
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

// Apply default Leaflet marker workaround
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconUrl: markerIcon.src,
    iconRetinaUrl: markerIcon2x.src,
    shadowUrl: markerShadow.src,
});

// Safe pre-encoded SVG icons for markers to avoid user input HTML injection
const VIOLET_PIN = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%238b5cf6" width="32" height="32"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;
const SELECTED_PIN = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23db2777" width="40" height="40"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;

const violetIcon = L.icon({
    iconUrl: VIOLET_PIN,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
});

const selectedIcon = L.icon({
    iconUrl: SELECTED_PIN,
    iconSize: [40, 40],
    iconAnchor: [20, 40],
    popupAnchor: [0, -40],
});

interface MapViewProps {
    services: Service[];
    locale: string;
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
    initialCenter?: GeoPoint;
    focusCommand?: MapFocusCommand | null;
}

export default function MapView({
    services,
    locale,
    selectedServiceId = null,
    hoveredServiceId = null,
    onSelectService,
    onBoundsChange,
    initialCenter,
    focusCommand
}: MapViewProps) {
    const t = useTranslations("catalog");
    const mapRef = useRef<HTMLDivElement>(null);
    const mapInstance = useRef<L.Map | null>(null);
    const markersLayerRef = useRef<L.LayerGroup | null>(null);
    const markersRef = useRef<Map<number, L.Marker>>(new Map());
    const suppressNextBoundsChangeRef = useRef(false);

    const selectedServiceIdRef = useRef(selectedServiceId);
    useEffect(() => {
        selectedServiceIdRef.current = selectedServiceId;
    }, [selectedServiceId]);

    // Filter services that have valid coordinate fields
    const servicesWithCoordinates = useMemo(() => {
        return services.filter(
            (service) =>
                service.latitude !== null &&
                service.latitude !== undefined &&
                service.longitude !== null &&
                service.longitude !== undefined &&
                Number.isFinite(Number(service.latitude)) &&
                Number.isFinite(Number(service.longitude))
        );
    }, [services]);

    const hasCoordinates = servicesWithCoordinates.length > 0;

    // 1. Initialize Leaflet Map Instance
    useEffect(() => {
        if (!mapRef.current || !hasCoordinates) return;

        // Determine initial map center
        const firstService = servicesWithCoordinates[0];
        const mapCenter: L.LatLngTuple = initialCenter
            ? [initialCenter.latitude, initialCenter.longitude]
            : firstService
                ? [Number(firstService.latitude), Number(firstService.longitude)]
                : [43.238949, 76.889709];

        // Create Leaflet map instance
        suppressNextBoundsChangeRef.current = true;
        const map = L.map(mapRef.current, {
            center: mapCenter,
            zoom: 12,
            zoomControl: true,
        });

        // Add OpenStreetMap tile layer
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        // Create a LayerGroup for markers
        const markersLayer = L.layerGroup().addTo(map);
        markersLayerRef.current = markersLayer;
        mapInstance.current = map;

        const handleMoveEnd = () => {
            if (!onBoundsChange) return;
            try {
                const b = map.getBounds();
                const west = b.getWest();
                const south = b.getSouth();
                const east = b.getEast();
                const north = b.getNorth();
                
                const isProgrammatic = suppressNextBoundsChangeRef.current;
                onBoundsChange(
                    { west, south, east, north },
                    { isUser: !isProgrammatic }
                );
            } catch (err) {
                console.error("Error getting Leaflet bounds:", err);
            }
        };

        map.on("moveend", handleMoveEnd);

        // Emit initial bounds
        handleMoveEnd();

        const currentMarkers = markersRef.current;
        // Cleanup on unmount
        return () => {
            if (mapInstance.current) {
                mapInstance.current.off("moveend", handleMoveEnd);
                mapInstance.current.remove();
                mapInstance.current = null;
            }
            currentMarkers.clear();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hasCoordinates]);

    // 2. Manage marker instances lifecycle (Task 4 Parity)
    useEffect(() => {
        const map = mapInstance.current;
        const markersLayer = markersLayerRef.current;
        if (!map || !markersLayer) return;

        // A) Remove obsolete markers
        const currentMarkerIds = new Set(servicesWithCoordinates.map((s) => s.id));
        markersRef.current.forEach((markerInstance, id) => {
            if (!currentMarkerIds.has(id)) {
                markersLayer.removeLayer(markerInstance);
                markersRef.current.delete(id);
            }
        });

        // B) Create or update markers
        servicesWithCoordinates.forEach((service) => {
            const isSelected = service.id === selectedServiceId;
            const isHovered = service.id === hoveredServiceId;
            const isHighlighted = isSelected || isHovered;
            const markerIcon = isHighlighted ? selectedIcon : violetIcon;

            let markerInstance = markersRef.current.get(service.id);

            if (!markerInstance) {
                const latlng: L.LatLngTuple = [Number(service.latitude), Number(service.longitude)];
                markerInstance = L.marker(latlng, { icon: markerIcon });
                
                // Click listener (Task 3 & 12)
                markerInstance.on("click", (e) => {
                    L.DomEvent.stopPropagation(e);
                    if (onSelectService) {
                        onSelectService({
                            serviceId: service.id,
                            latitude: Number(service.latitude),
                            longitude: Number(service.longitude),
                        });
                    }
                });

                markersLayer.addLayer(markerInstance);
                markersRef.current.set(service.id, markerInstance);
            } else {
                // Update icon
                markerInstance.setIcon(markerIcon);
            }

            // Update zIndex
            if (isHighlighted) {
                markerInstance.setZIndexOffset(1000);
            } else {
                markerInstance.setZIndexOffset(0);
            }
        });
    }, [servicesWithCoordinates, selectedServiceId, hoveredServiceId, onSelectService]);

    const lastResultSignatureRef = useRef<string>("");

    // 3. Fit bounds on meaningful result changes (Task 10)
    useEffect(() => {
        const map = mapInstance.current;
        if (!map || servicesWithCoordinates.length === 0) return;

        // Build stable signature of sorted service IDs + coordinates
        const signature = servicesWithCoordinates
            .map((s) => `${s.id}:${Number(s.latitude).toFixed(6)}:${Number(s.longitude).toFixed(6)}`)
            .sort()
            .join(",");

        if (lastResultSignatureRef.current === signature) return;
        lastResultSignatureRef.current = signature;

        // If selected service still exists, do not move the camera (Task 10 requirement)
        const currentSelectedId = selectedServiceIdRef.current;
        if (currentSelectedId !== null) {
            const exists = servicesWithCoordinates.some((s) => s.id === currentSelectedId);
            if (exists) {
                return;
            }
        }

        // Fit map bounds to show all markers if multiple exist
        const bounds = servicesWithCoordinates.map((s) => [Number(s.latitude), Number(s.longitude)] as L.LatLngTuple);
        if (bounds.length > 1) {
            suppressNextBoundsChangeRef.current = true;
            map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
        } else if (bounds.length === 1) {
            suppressNextBoundsChangeRef.current = true;
            map.setView(bounds[0], 13);
        }
    }, [servicesWithCoordinates]);

    const lastFocusRequestIdRef = useRef<number | null>(null);
    const suppressionTimeoutRef = useRef<any>(null);

    // 4. React to explicit focus commands using requestId protocol (Task 8 & 11)
    useEffect(() => {
        const map = mapInstance.current;
        if (!map || !focusCommand) return;

        if (lastFocusRequestIdRef.current === focusCommand.requestId) return;

        const lat = Number(focusCommand.latitude);
        const lng = Number(focusCommand.longitude);

        if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            return;
        }

        lastFocusRequestIdRef.current = focusCommand.requestId;

        // Diagnostic logs (Task 14)
        if (process.env.NODE_ENV === "development") {
            console.info("[Map focus Leaflet]", {
                serviceId: focusCommand.serviceId,
                latitude: focusCommand.latitude,
                longitude: focusCommand.longitude,
                requestId: focusCommand.requestId,
                source: focusCommand.source,
            });
        }

        // Suppress programmatic move from triggering "Search this area" button
        suppressNextBoundsChangeRef.current = true;
        if (suppressionTimeoutRef.current) {
            clearTimeout(suppressionTimeoutRef.current);
        }

        map.setView([lat, lng], map.getZoom());

        suppressionTimeoutRef.current = setTimeout(() => {
            suppressNextBoundsChangeRef.current = false;
        }, 1000); // 1s timeout to clear suppression
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [focusCommand?.requestId]);

    useEffect(() => {
        return () => {
            if (suppressionTimeoutRef.current) {
                clearTimeout(suppressionTimeoutRef.current);
            }
        };
    }, []);

    // Render empty state if no services have coordinate data
    if (!hasCoordinates) {
        return (
            <div className="py-16 text-center rounded-2xl bg-neutral-50 border border-neutral-200 p-6 min-h-[420px] flex flex-col justify-center items-center">
                <div className="w-16 h-16 bg-neutral-100 text-neutral-400 rounded-full flex items-center justify-center mb-4">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </div>
                <h3 className="text-lg font-bold text-neutral-900 mb-2">
                    {t("map.noCoordinates") || "No services on map"}
                </h3>
                <p className="text-neutral-500 max-w-md mx-auto text-sm">
                    {t("map.noCoordinatesDescription") || "None of the currently matching services have coordinates set."}
                </p>
            </div>
        );
    }

    const selectedService = services.find((s) => s.id === selectedServiceId);

    return (
        <div className="relative border border-neutral-200 rounded-2xl overflow-hidden shadow-sm bg-neutral-50 w-full min-h-[420px] md:h-[500px] flex flex-col">
            {/* Map title bar */}
            <div className="bg-white border-b border-neutral-100 px-6 py-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></span>
                    <span className="text-sm font-bold text-neutral-700">
                        {t("map.markersShown", { count: servicesWithCoordinates.length, total: services.length }) || `Showing ${servicesWithCoordinates.length} of ${services.length} services on map`}
                    </span>
                </div>
            </div>

            {/* Leaflet map container element */}
            <div
                ref={mapRef}
                className="w-full min-h-[420px] md:h-[500px] z-0 flex-1"
                style={{ outline: "none", width: "100%", height: "100%" }}
            />

            {/* React-controlled Preview Card */}
            {selectedService && (
                <div className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-white border border-neutral-200 rounded-3xl p-5 shadow-xl z-10 transition-all duration-200 font-sans">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                            <span className="inline-block px-2.5 py-0.5 text-[9px] font-extrabold uppercase tracking-widest text-violet-750 bg-violet-50 border border-violet-100 rounded-full mb-2">
                                {selectedService.city}
                            </span>
                            <h4 className="font-extrabold text-neutral-900 text-sm truncate mb-0.5" title={selectedService.title}>
                                {selectedService.title}
                            </h4>
                            <p className="text-xs text-neutral-500 font-semibold mb-3">
                                {t("map.selectedService") || "Provider"}: {typeof selectedService.provider === "object" && selectedService.provider !== null ? selectedService.provider.username : "—"}
                            </p>
                            <div className="text-base font-black text-neutral-955 mb-4">
                                ₸ {parseInt(String(selectedService.price_amount || 0)).toLocaleString()}
                            </div>
                            <div className="flex gap-2">
                                <a
                                    href={`/${locale}/service/${selectedService.id}/`}
                                    className="bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-xs hover:shadow-sm transition decoration-none text-center flex-1"
                                >
                                    {t("map.viewService") || "View service"}
                                </a>
                                <button
                                    onClick={() => onSelectService && onSelectService(null)}
                                    className="border border-neutral-200 text-neutral-600 hover:bg-neutral-50 font-bold text-xs px-4 py-2.5 rounded-xl transition"
                                >
                                    {t("map.closePreview") || "Close"}
                                </button>
                            </div>
                        </div>
                        <button
                            onClick={() => onSelectService && onSelectService(null)}
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
