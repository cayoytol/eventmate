"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import FilterForm from "./FilterForm";
import { ServiceCard } from "@/components/shared/ServiceCard";
import type { Service, Category } from "@/types/catalog";

// Dynamically import MapProviderView with ssr: false to prevent document/window ReferenceErrors during SSR
const MapProviderView = dynamic(() => import("@/components/map/MapProviderView"), {
    ssr: false,
    loading: () => (
        <div className="w-full min-h-[420px] md:h-[500px] flex items-center justify-center bg-neutral-50 border border-neutral-200 rounded-2xl">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600 mx-auto mb-3"></div>
                <p className="text-sm text-neutral-400">Loading map...</p>
            </div>
        </div>
    ),
});
export type ServiceId = string | number;

export type GeoPoint = {
    latitude: number;
    longitude: number;
};

export type MapFocusSource =
    | "marker-click"
    | "show-on-map"
    | "browser-location";

export type MapFocusCommand = {
    serviceId?: ServiceId;
    latitude: number;
    longitude: number;
    requestId: number;
    source: MapFocusSource;
};

export type MapServiceSelection = {
    serviceId: ServiceId;
    latitude: number;
    longitude: number;
};

const DEFAULT_LAT = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LAT || "43.238949");
const DEFAULT_LNG = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LNG || "76.889709");

const deriveInitialCenter = (
    filters: Record<string, string | undefined>,
    services: Service[]
): GeoPoint => {
    // 1. Valid active radius center
    if (filters.lat && filters.lng && filters.radius) {
        const lat = parseFloat(filters.lat);
        const lng = parseFloat(filters.lng);
        if (Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
            return { latitude: lat, longitude: lng };
        }
    }
    // 2. First valid service coordinate
    const firstWithCoords = services.find(
        (s) =>
            s.latitude !== null &&
            s.latitude !== undefined &&
            s.longitude !== null &&
            s.longitude !== undefined &&
            Number.isFinite(Number(s.latitude)) &&
            Number.isFinite(Number(s.longitude))
    );
    if (firstWithCoords) {
        return {
            latitude: Number(firstWithCoords.latitude),
            longitude: Number(firstWithCoords.longitude),
        };
    }
    // 3. Configured default city center
    return { latitude: DEFAULT_LAT, longitude: DEFAULT_LNG };
};
interface CatalogClientProps {
    categories: Category[];
    services: Service[];
    count: number;
    next: string | null;
    previous: string | null;
    currentPage: number;
    locale: string;
    filters: Record<string, string | undefined>;
}

type GeoSearchMode = "none" | "radius" | "bbox";

export default function CatalogClient({
    categories,
    services,
    count,
    next,
    previous,
    currentPage,
    locale,
    filters,
}: CatalogClientProps) {
    const t = useTranslations("catalog");
    const router = useRouter();
    const pathname = usePathname();

    const [viewMode, setViewMode] = useState<"list" | "map">("list");
    const [selectedServiceId, setSelectedServiceId] = useState<ServiceId | null>(null);
    const [hoveredServiceId, setHoveredServiceId] = useState<ServiceId | null>(null);
    const [focusCommand, setFocusCommand] = useState<MapFocusCommand | null>(null);
    const nextRequestIdRef = useRef(0);

    const [initialCenter] = useState<GeoPoint>(() =>
        deriveInitialCenter(filters, services)
    );

    const triggerFocus = useCallback(
        (
            point: GeoPoint,
            source: MapFocusSource,
            serviceId?: ServiceId
        ) => {
            nextRequestIdRef.current += 1;
            setFocusCommand({
                serviceId,
                latitude: point.latitude,
                longitude: point.longitude,
                source,
                requestId: nextRequestIdRef.current,
            });
        },
        []
    );

    const handleSelectService = useCallback((selection: MapServiceSelection | null) => {
        if (selection === null) {
            setSelectedServiceId(null);
            return;
        }
        const lat = Number(selection.latitude);
        const lng = Number(selection.longitude);
        if (
            Number.isFinite(lat) &&
            Number.isFinite(lng) &&
            lat >= -90 &&
            lat <= 90 &&
            lng >= -180 &&
            lng <= 180
        ) {
            setSelectedServiceId(selection.serviceId);
            triggerFocus(
                { latitude: lat, longitude: lng },
                "marker-click",
                selection.serviceId
            );
        }
    }, [triggerFocus]);

    // 1. Safe URL Parsing & Validation (Task 3)
    let validatedRadius: { latitude: number; longitude: number; radiusM: number } | null = null;
    let validatedBbox: { west: number; south: number; east: number; north: number } | null = null;
    let hasGeoConflict = false;
    let hasMalformedGeo = false;

    // Validate Radius
    if (filters.lat !== undefined || filters.lng !== undefined || filters.radius !== undefined) {
        if (filters.lat && filters.lng && filters.radius) {
            const lat = parseFloat(filters.lat);
            const lng = parseFloat(filters.lng);
            const rad = parseFloat(filters.radius);

            if (
                Number.isFinite(lat) &&
                Number.isFinite(lng) &&
                Number.isFinite(rad) &&
                lat >= -90 &&
                lat <= 90 &&
                lng >= -180 &&
                lng <= 180 &&
                rad >= 100 &&
                rad <= 100000
            ) {
                validatedRadius = { latitude: lat, longitude: lng, radiusM: rad };
            } else {
                hasMalformedGeo = true;
            }
        } else {
            hasMalformedGeo = true;
        }
    }

    // Validate Bbox
    if (filters.bbox !== undefined) {
        if (filters.bbox) {
            const parts = filters.bbox.split(",").map((p) => parseFloat(p));
            if (parts.length === 4 && parts.every(Number.isFinite)) {
                const [west, south, east, north] = parts;
                if (
                    west >= -180 &&
                    west <= 180 &&
                    east >= -180 &&
                    east <= 180 &&
                    south >= -90 &&
                    south <= 90 &&
                    north >= -90 &&
                    north <= 90 &&
                    west <= east &&
                    south <= north
                ) {
                    validatedBbox = { west, south, east, north };
                } else {
                    hasMalformedGeo = true;
                }
            } else {
                hasMalformedGeo = true;
            }
        } else {
            hasMalformedGeo = true;
        }
    }

    // Conflict resolution
    if (validatedRadius && validatedBbox) {
        hasGeoConflict = true;
        // Radius takes precedence; omit bbox
        validatedBbox = null;
    }

    const geoMode: GeoSearchMode = validatedRadius ? "radius" : (validatedBbox ? "bbox" : "none");

    // 2. Geo States
    const [radiusM, setRadiusM] = useState<number>(
        validatedRadius ? validatedRadius.radiusM : 5000
    );
    const [center, setCenter] = useState<{ latitude: number; longitude: number } | null>(
        validatedRadius
            ? { latitude: validatedRadius.latitude, longitude: validatedRadius.longitude }
            : null
    );

    const [browserLocation, setBrowserLocation] = useState<{ latitude: number; longitude: number } | null>(null);
    const [isRequestingLocation, setIsRequestingLocation] = useState<boolean>(false);
    const [locationError, setLocationError] = useState<string | null>(null);

    // Map bounds states for bbox search
    const [pendingBbox, setPendingBbox] = useState<{
        west: number;
        south: number;
        east: number;
        north: number;
    } | null>(null);
    const [showSearchAreaButton, setShowSearchAreaButton] = useState<boolean>(false);
    const [latestMapBounds, setLatestMapBounds] = useState<typeof pendingBbox>(null);

    const safeServices = useMemo(() => Array.isArray(services) ? services : [], [services]);
    const isEmpty = safeServices.length === 0;

    // 3. Pagination calculation
    const PAGE_SIZE = 12;
    const totalPages = Math.ceil(count / PAGE_SIZE) || 1;
    const hasPrevious = currentPage > 1;
    const hasNext = currentPage < totalPages;

    // Scroll to card on marker selection
    useEffect(() => {
        if (selectedServiceId !== null) {
            const cardElement = document.getElementById(`service-card-${selectedServiceId}`);
            if (cardElement) {
                cardElement.scrollIntoView({
                    behavior: "smooth",
                    block: "nearest",
                });
            }
        }
    }, [selectedServiceId]);

    // Cleanup selection if selected/hovered service is no longer in current catalog results (Task 13)
    useEffect(() => {
        if (selectedServiceId !== null) {
            const exists = safeServices.some((s) => s.id === selectedServiceId);
            if (!exists) {
                setSelectedServiceId(null);
            }
        }
        if (hoveredServiceId !== null) {
            const exists = safeServices.some((s) => s.id === hoveredServiceId);
            if (!exists) {
                setHoveredServiceId(null);
            }
        }
    }, [services, selectedServiceId, hoveredServiceId, safeServices]);

    // 4. URL Update Helper maintaining existing non-geo parameters (Task 4)
    const updateUrlParams = (newParams: Record<string, string | null>) => {
        const params = new URLSearchParams();

        // Copy allowed existing filters (Mandatory correction 1)
        const ALLOWED = [
            "search",
            "category_id",
            "city",
            "provider",
            "price_min",
            "price_max",
            "ordering",
        ];

        ALLOWED.forEach((key) => {
            if (filters[key]) {
                params.set(key, filters[key]!);
            }
        });

        // Apply new parameters
        Object.entries(newParams).forEach(([key, val]) => {
            if (val === null) {
                params.delete(key);
            } else {
                params.set(key, val);
            }
        });

        router.push(`${pathname}?${params.toString()}`);
    };

    // Safe Page Navigation (Mandatory correction 3)
    const handlePageChange = (newPage: number) => {
        const params = new URLSearchParams();

        const ALL_CURRENT = [
            "search",
            "category_id",
            "city",
            "provider",
            "price_min",
            "price_max",
            "ordering",
            "lat",
            "lng",
            "radius",
            "bbox"
        ];

        ALL_CURRENT.forEach((key) => {
            if (filters[key]) {
                params.set(key, filters[key]!);
            }
        });

        params.set("page", String(newPage));
        router.push(`${pathname}?${params.toString()}`);
    };

    // 5. Browser Geolocation (Task 6)
    const handleUseMyLocation = () => {
        if (typeof window === "undefined" || !navigator.geolocation) {
            setLocationError(t("geo.locationUnavailable") || "Geolocation is not supported by your browser.");
            return;
        }

        setIsRequestingLocation(true);
        setLocationError(null);

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;

                if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                    // Round to 5 decimal places for privacy and shorter URL query strings
                    const roundedLat = parseFloat(lat.toFixed(5));
                    const roundedLng = parseFloat(lng.toFixed(5));

                    setBrowserLocation({ latitude: roundedLat, longitude: roundedLng });
                    setCenter({ latitude: roundedLat, longitude: roundedLng });
                    triggerFocus(
                        { latitude: roundedLat, longitude: roundedLng },
                        "browser-location"
                    );
                } else {
                    setLocationError(t("geo.geoFilterInvalid") || "Invalid coordinates received.");
                }
                setIsRequestingLocation(false);
            },
            (error) => {
                console.warn("Geolocation warning (non-blocking):", error);
                setIsRequestingLocation(false);
                if (error.code === error.PERMISSION_DENIED) {
                    setLocationError(t("geo.locationPermissionDenied") || "Location permission denied.");
                } else {
                    setLocationError(t("geo.locationUnavailable") || "Location unavailable or timed out.");
                }
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    };

    // 6. Apply radius search (Task 5)
    const handleApplyRadiusSearch = () => {
        const targetCenter = center || browserLocation;
        if (!targetCenter) {
            setLocationError(t("geo.chooseRadius") || "Please select a location first.");
            return;
        }

        if (radiusM < 100 || radiusM > 100000 || !Number.isFinite(radiusM)) {
            setLocationError(t("geo.geoFilterInvalid") || "Invalid radius value.");
            return;
        }

        setLocationError(null);
        setShowSearchAreaButton(false);

        updateUrlParams({
            lat: String(targetCenter.latitude),
            lng: String(targetCenter.longitude),
            radius: String(radiusM),
            bbox: null,
            page: null,
        });
    };

    // 7. Clear geo filters (Task 10 & 13)
    const handleClearGeoFilter = () => {
        setLocationError(null);
        setCenter(null);
        setBrowserLocation(null);
        setShowSearchAreaButton(false);
        setPendingBbox(null);

        updateUrlParams({
            lat: null,
            lng: null,
            radius: null,
            bbox: null,
            page: null,
        });
    };

    // 8. Bbox search callback (Task 7 & 8)
    const handleBoundsChange = useCallback((
        bounds: typeof pendingBbox,
        meta?: { isUser: boolean }
    ) => {
        setLatestMapBounds(bounds);
        if (meta?.isUser && bounds) {
            setPendingBbox(bounds);
            setShowSearchAreaButton(true);
        }
    }, []);

    // Apply Bbox area search (Task 10)
    const handleApplyBboxSearch = () => {
        if (!pendingBbox) return;

        setShowSearchAreaButton(false);

        updateUrlParams({
            bbox: `${pendingBbox.west.toFixed(6)},${pendingBbox.south.toFixed(6)},${pendingBbox.east.toFixed(6)},${pendingBbox.north.toFixed(6)}`,
            lat: null,
            lng: null,
            radius: null,
            page: null,
        });
    };

    return (
        <div className="space-y-6">
            {/* Header section */}
            <div className="flex flex-col space-y-2 pb-4">
                <h1 className="text-3xl font-black tracking-tight text-neutral-900 md:text-4xl">
                    {t("title")}
                </h1>
                <p className="text-sm text-neutral-500 max-w-2xl leading-relaxed">{t("description")}</p>
            </div>

            {/* Filter Form */}
            <FilterForm categories={categories} initialFilters={filters} />

            {/* Radius and Geolocation Panel (Task 5) */}
            <div className="bg-white border border-neutral-200 rounded-2xl p-5 shadow-sm space-y-3">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <h3 className="text-sm font-black text-neutral-800 uppercase tracking-wider flex items-center gap-2">
                            <svg className="w-4 h-4 text-violet-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {t("geo.geoSearch") || "Geographic Search"}
                        </h3>
                        <p className="text-xs text-neutral-500">
                            {t("geo.chooseRadius") || "Filter services within a chosen radius from your location."}
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        {/* Use my location */}
                        <button
                            type="button"
                            disabled={isRequestingLocation}
                            onClick={handleUseMyLocation}
                            className={`flex items-center gap-1.5 px-4 py-2 border rounded-xl text-xs font-bold transition active:scale-95 ${
                                browserLocation
                                    ? "bg-violet-50 border-violet-200 text-violet-750"
                                    : "bg-neutral-50 border-neutral-200 text-neutral-600 hover:bg-neutral-100"
                            }`}
                        >
                            <svg className={`w-3.5 h-3.5 ${isRequestingLocation ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>
                                {isRequestingLocation
                                    ? (t("geo.requestingLocation") || "Locating...")
                                    : browserLocation
                                        ? (t("geo.useMyLocation") || "Located")
                                        : (t("geo.useMyLocation") || "My location")}
                            </span>
                        </button>

                        {/* Radius options */}
                        <select
                            value={radiusM}
                            onChange={(e) => setRadiusM(parseInt(e.target.value, 10))}
                            className="bg-neutral-50 border border-neutral-200 text-neutral-700 px-3 py-2 rounded-xl text-xs font-bold focus:outline-none focus:ring-2 focus:ring-violet-500"
                        >
                            <option value="1000">1 {t("geo.radius1km") || "km"}</option>
                            <option value="5000">5 {t("geo.radius5km") || "km"}</option>
                            <option value="10000">10 {t("geo.radius10km") || "km"}</option>
                            <option value="20000">20 {t("geo.radius20km") || "km"}</option>
                            <option value="50000">50 {t("geo.radius50km") || "km"}</option>
                        </select>

                        {/* Apply button */}
                        <button
                            type="button"
                            onClick={handleApplyRadiusSearch}
                            className="bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-xs transition active:scale-95"
                        >
                            {t("geo.applyRadius") || "Apply radius"}
                        </button>

                        {/* Clear button */}
                        {geoMode !== "none" && (
                            <button
                                type="button"
                                onClick={handleClearGeoFilter}
                                className="border border-neutral-200 hover:bg-neutral-50 text-neutral-600 font-bold text-xs px-4 py-2 rounded-xl transition active:scale-95"
                            >
                                {t("geo.clearGeoFilter") || "Clear filter"}
                            </button>
                        )}
                    </div>
                </div>

                {/* Location Error Display */}
                {locationError && (
                    <div className="text-xs font-semibold text-red-700 bg-red-50 px-3 py-2 rounded-xl border border-red-100">
                        {locationError}
                    </div>
                )}

                {/* Malformed/Conflicting URL Geo Parameters Warning (Task 3 & 14) */}
                {(hasMalformedGeo || hasGeoConflict) && (
                    <div className="text-xs font-semibold text-amber-700 bg-amber-50 px-3 py-2 rounded-xl border border-amber-100 flex items-center gap-1.5 w-fit">
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <span>
                            {t("geo.geoFilterInvalid") || "Invalid geographic filter query in URL."}
                        </span>
                    </div>
                )}

                {/* Search Summaries / Removable Chips (Task 10 & 13) */}
                {geoMode === "radius" && (
                    <div className="text-xs font-bold text-violet-750 bg-violet-50 px-3 py-2 rounded-xl border border-violet-100 flex items-center gap-1.5 w-fit">
                        <span className="w-1.5 h-1.5 bg-violet-500 rounded-full"></span>
                        <span>
                            {t("geo.withinRadius", { radius: radiusM / 1000 }) || `Within ${radiusM / 1000} km`}
                        </span>
                        <span className="text-neutral-400 font-medium">|</span>
                        <span>
                            {t("geo.nearestFirst") || "Nearest first"}
                        </span>
                    </div>
                )}

                {geoMode === "bbox" && (
                    <div className="text-xs font-bold text-indigo-750 bg-indigo-50 px-3 py-2 rounded-xl border border-indigo-100 flex items-center gap-1.5 w-fit">
                        <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
                        <span>
                            {t("geo.visibleMapArea") || "Visible map area"}
                        </span>
                    </div>
                )}
            </div>

            {/* View Toggle and Results Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    {!isEmpty && (
                        <div className="text-xs font-bold text-neutral-500 bg-neutral-50 inline-block px-4 py-2 rounded-full border border-neutral-200">
                            {t("filters.results", { count }) || `${count} results found`}
                        </div>
                    )}
                </div>

                {/* List/Map view toggle switches */}
                <div className="flex items-center bg-neutral-100 p-0.5 rounded-xl self-end sm:self-auto border border-neutral-200">
                    <button
                        type="button"
                        onClick={() => setViewMode("list")}
                        className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition active:scale-95 ${
                            viewMode === "list"
                                ? "bg-white text-violet-600 shadow-xs"
                                : "text-neutral-500 hover:text-neutral-800"
                        }`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                        </svg>
                        {t("view.list") || "List"}
                    </button>
                    <button
                        type="button"
                        onClick={() => setViewMode("map")}
                        className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition active:scale-95 ${
                            viewMode === "map"
                                ? "bg-white text-violet-600 shadow-xs"
                                : "text-neutral-500 hover:text-neutral-800"
                        }`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                        </svg>
                        {t("view.map") || "Map"}
                    </button>
                </div>
            </div>

            {/* List and Map Views */}
            {viewMode === "list" ? (
                isEmpty ? (
                    <EmptyState geoMode={geoMode} t={t} onClear={handleClearGeoFilter} />
                ) : (
                    <div className="space-y-6">
                        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                            {safeServices.map((service) => (
                                <div
                                    key={service.id}
                                    id={`service-card-${service.id}`}
                                    className="transition-all duration-200"
                                >
                                    <ServiceCard
                                        id={service.id}
                                        title={service.title}
                                        description={service.description}
                                        city={service.city}
                                        address={service.address}
                                        price_amount={service.price_amount}
                                        price_type={service.price_type}
                                        category_name={service.category_name}
                                        provider={service.provider}
                                        cover={service.cover}
                                        isFavorite={!!service.is_favorite}
                                        distance_m={service.distance_m}
                                        locale={locale}
                                        onShowOnMap={() => {
                                            const lat = Number(service.latitude);
                                            const lng = Number(service.longitude);
                                            if (
                                                Number.isFinite(lat) &&
                                                Number.isFinite(lng) &&
                                                lat >= -90 &&
                                                lat <= 90 &&
                                                lng >= -180 &&
                                                lng <= 180
                                            ) {
                                                setSelectedServiceId(service.id);
                                                setViewMode("map");
                                                triggerFocus(
                                                    { latitude: lat, longitude: lng },
                                                    "show-on-map",
                                                    service.id
                                                );
                                            }
                                        }}
                                        isSelected={selectedServiceId === service.id}
                                    />
                                </div>
                            ))}
                        </div>

                        {/* List Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-center gap-4 border-t border-neutral-100 pt-6">
                                <button
                                    onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                                    disabled={!hasPrevious}
                                    className={`flex items-center gap-1 px-4 py-2 border rounded-xl text-xs font-bold transition active:scale-95 ${
                                        hasPrevious
                                            ? "bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50 shadow-2xs"
                                            : "bg-neutral-50 border-neutral-100 text-neutral-300 cursor-not-allowed"
                                    }`}
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                                    </svg>
                                    <span>Previous</span>
                                </button>

                                <span className="text-xs font-bold text-neutral-500">
                                    Page {currentPage} of {totalPages}
                                </span>

                                <button
                                    onClick={() => handlePageChange(currentPage + 1)}
                                    disabled={!hasNext}
                                    className={`flex items-center gap-1 px-4 py-2 border rounded-xl text-xs font-bold transition active:scale-95 ${
                                        hasNext
                                            ? "bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50 shadow-2xs"
                                            : "bg-neutral-50 border-neutral-100 text-neutral-300 cursor-not-allowed"
                                    }`}
                                >
                                    <span>Next</span>
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>
                        )}
                    </div>
                )
            ) : (
                isEmpty ? (
                    <EmptyState geoMode={geoMode} t={t} onClear={handleClearGeoFilter} />
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Map Area */}
                        <div className="lg:col-span-2 h-[450px] lg:h-[600px] sticky top-6 z-0 relative">
                            <MapProviderView
                                services={safeServices}
                                locale={locale}
                                selectedServiceId={selectedServiceId}
                                hoveredServiceId={hoveredServiceId}
                                onSelectService={handleSelectService}
                                onBoundsChange={handleBoundsChange}
                                initialCenter={initialCenter}
                                focusCommand={focusCommand}
                            />
                            {showSearchAreaButton && pendingBbox && (
                                <button
                                    onClick={handleApplyBboxSearch}
                                    className="absolute top-16 left-1/2 -translate-x-1/2 bg-violet-600 hover:bg-violet-750 text-white font-extrabold text-xs px-4 py-2.5 rounded-full shadow-lg z-20 flex items-center gap-1.5 transition active:scale-95 border border-violet-500 animate-fade-in"
                                >
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                    <span>{t("geo.searchThisArea") || "Search this area"}</span>
                                </button>
                            )}
                        </div>

                        {/* List Area side scrollable */}
                        <div className="lg:col-span-1 space-y-4 max-h-[450px] lg:max-h-[600px] overflow-y-auto pr-2">
                            {safeServices.map((service) => (
                                <div
                                    key={service.id}
                                    id={`service-card-${service.id}`}
                                    onMouseEnter={() => {
                                        setHoveredServiceId(service.id);
                                    }}
                                    onMouseLeave={() => {
                                        setHoveredServiceId(null);
                                    }}
                                    className="transition-all duration-200"
                                >
                                    <ServiceCard
                                        id={service.id}
                                        title={service.title}
                                        description={service.description}
                                        city={service.city}
                                        address={service.address}
                                        price_amount={service.price_amount}
                                        price_type={service.price_type}
                                        category_name={service.category_name}
                                        provider={service.provider}
                                        cover={service.cover}
                                        isFavorite={!!service.is_favorite}
                                        distance_m={service.distance_m}
                                        locale={locale}
                                        onShowOnMap={() => {
                                            const lat = Number(service.latitude);
                                            const lng = Number(service.longitude);
                                            if (
                                                Number.isFinite(lat) &&
                                                Number.isFinite(lng) &&
                                                lat >= -90 &&
                                                lat <= 90 &&
                                                lng >= -180 &&
                                                lng <= 180
                                            ) {
                                                setSelectedServiceId(service.id);
                                                triggerFocus(
                                                    { latitude: lat, longitude: lng },
                                                    "show-on-map",
                                                    service.id
                                                );
                                            }
                                        }}
                                        isSelected={selectedServiceId === service.id}
                                    />
                                </div>
                            ))}

                            {/* Side panel pagination */}
                            {totalPages > 1 && (
                                <div className="flex items-center justify-between gap-2 border-t border-neutral-100 pt-4 mt-4">
                                    <button
                                        onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                                        disabled={!hasPrevious}
                                        className={`px-3 py-1.5 border rounded-xl text-[10px] font-bold transition active:scale-95 ${
                                            hasPrevious
                                                ? "bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50 shadow-3xs"
                                                : "bg-neutral-50 border-neutral-100 text-neutral-300 cursor-not-allowed"
                                        }`}
                                    >
                                        Prev
                                    </button>

                                    <span className="text-[10px] font-bold text-neutral-500">
                                        {currentPage} / {totalPages}
                                    </span>

                                    <button
                                        onClick={() => handlePageChange(currentPage + 1)}
                                        disabled={!hasNext}
                                        className={`px-3 py-1.5 border rounded-xl text-[10px] font-bold transition active:scale-95 ${
                                            hasNext
                                                ? "bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50 shadow-3xs"
                                                : "bg-neutral-50 border-neutral-100 text-neutral-300 cursor-not-allowed"
                                        }`}
                                    >
                                        Next
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                )
            )}
        </div>
    );
}

function EmptyState({ geoMode, t, onClear }: { geoMode: GeoSearchMode; t: any; onClear: () => void }) {
    let title = t("filters.noResults") || "No results found";
    let desc = t("filters.noResultsDescription") || "Try changing your filter settings or search query.";

    if (geoMode === "radius") {
        title = t("geo.noNearbyServicesTitle") || "No services nearby";
        desc = t("geo.noNearbyServicesDescription") || "No services were found within the selected radius.";
    } else if (geoMode === "bbox") {
        title = t("geo.noServicesInAreaTitle") || "No services in this area";
        desc = t("geo.noServicesInAreaDescription") || "Move the map or zoom out to see services in other areas.";
    }

    return (
        <div className="py-16 text-center rounded-2xl bg-neutral-50 border border-neutral-200 p-6 flex flex-col items-center justify-center w-full min-h-[300px]">
            <div className="w-16 h-16 bg-neutral-100 text-neutral-400 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <h3 className="text-lg font-bold text-neutral-900 mb-2">
                {title}
            </h3>
            <p className="text-neutral-500 max-w-md mx-auto text-sm mb-6">
                {desc}
            </p>
            {geoMode !== "none" && (
                <button
                    onClick={onClear}
                    className="px-5 py-2.5 bg-violet-600 hover:bg-violet-755 text-white font-bold text-xs rounded-xl transition active:scale-95 shadow-md shadow-violet-100"
                >
                    {t("geo.clearGeoFilter") || "Clear Geo Filter"}
                </button>
            )}
        </div>
    );
}
