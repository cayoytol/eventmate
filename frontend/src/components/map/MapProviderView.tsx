"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import type { Service } from "@/types/catalog";
import MapView from "../../app/[locale]/(public)/catalog/MapView";
import type { MapServiceMarker } from "./2GISMap";
import type { ServiceId, GeoPoint, MapFocusCommand, MapServiceSelection } from "../../app/[locale]/(public)/catalog/CatalogClient";

// Dynamically import 2GISMap client-only
const DGISMap = dynamic(() => import("./2GISMap"), {
    ssr: false,
    loading: () => (
        <div className="w-full min-h-[420px] md:h-[500px] flex items-center justify-center bg-neutral-50 border border-neutral-200 rounded-2xl">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600 mx-auto mb-3"></div>
                <p className="text-sm text-neutral-400">Loading map shell...</p>
            </div>
        </div>
    ),
});

interface MapProviderViewProps {
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

// Coordinate validation helper (Task 1)
const validateCoordinates = (lat: any, lng: any): boolean => {
    const latitude = typeof lat === "string" ? parseFloat(lat) : lat;
    const longitude = typeof lng === "string" ? parseFloat(lng) : lng;

    return (
        latitude !== null &&
        latitude !== undefined &&
        longitude !== null &&
        longitude !== undefined &&
        Number.isFinite(latitude) &&
        Number.isFinite(longitude) &&
        latitude >= -90 &&
        latitude <= 90 &&
        longitude >= -180 &&
        longitude <= 180
    );
};

export default function MapProviderView({
    services,
    locale,
    selectedServiceId = null,
    hoveredServiceId = null,
    onSelectService,
    onBoundsChange,
    initialCenter,
    focusCommand
}: MapProviderViewProps) {
    const provider = (process.env.NEXT_PUBLIC_MAP_PROVIDER || "leaflet").toLowerCase();
    const apiKey = process.env.NEXT_PUBLIC_2GIS_MAP_KEY;

    // A) Filter services with coordinates for fallback check
    const servicesWithCoordinates = useMemo(() => {
        return services.filter(
            (service) =>
                service.latitude !== null &&
                service.latitude !== undefined &&
                service.longitude !== null &&
                service.longitude !== undefined
        );
    }, [services]);

    const hasCoordinates = servicesWithCoordinates.length > 0;

    // B) Build validated MapServiceMarker array (Task 1)
    const validatedMarkers: MapServiceMarker[] = useMemo(() => {
        return services
            .filter((s) => validateCoordinates(s.latitude, s.longitude))
            .map((s) => ({
                id: s.id,
                title: s.title,
                latitude: Number(s.latitude),
                longitude: Number(s.longitude),
                price: s.price_amount,
                city: s.city,
                providerName: typeof s.provider === "object" && s.provider !== null ? s.provider.username : null,
                cover: s.cover || null,
            }));
    }, [services]);

    // Fall back to Leaflet if provider is leaflet, if provider is unknown, or if 2GIS key is missing
    if (provider !== "2gis" || !apiKey) {
        return (
            <MapView
                services={services}
                locale={locale}
                selectedServiceId={selectedServiceId}
                hoveredServiceId={hoveredServiceId}
                onSelectService={onSelectService}
                onBoundsChange={onBoundsChange}
                initialCenter={initialCenter}
                focusCommand={focusCommand}
            />
        );
    }

    return (
        <DGISMap
            locale={locale}
            initialCenter={initialCenter}
            focusCommand={focusCommand}
            markers={validatedMarkers}
            totalServicesCount={services.length}
            selectedServiceId={selectedServiceId}
            hoveredServiceId={hoveredServiceId}
            onSelectService={onSelectService}
            onBoundsChange={onBoundsChange}
            className="w-full h-full"
        />
    );
}
