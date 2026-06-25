"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

// Dynamically import LocationPickerMap client-side only
const LocationPickerMap = dynamic(() => import("./LocationPickerMap"), {
    ssr: false,
    loading: () => (
        <div className="w-full h-[300px] flex items-center justify-center bg-slate-50 border border-slate-200 rounded-2xl">
            <div className="text-center">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-600 mx-auto mb-2"></div>
                <p className="text-xs text-slate-400">Loading map picker...</p>
            </div>
        </div>
    ),
});

export type ProviderLocationValue = {
    address: string;
    city: string;
    latitude: number | null;
    longitude: number | null;
};

interface ProviderLocationPickerProps {
    value: ProviderLocationValue;
    onChange: (value: ProviderLocationValue) => void;
    locale: string;
    disabled?: boolean;
}

export default function ProviderLocationPicker({
    value,
    onChange,
    locale,
    disabled = false
}: ProviderLocationPickerProps) {
    const t = useTranslations("provider.services");
    
    const [suggestions, setSuggestions] = useState<any[]>([]);
    const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
    const [isSearching, setIsSearching] = useState<boolean>(false);
    const [notice, setNotice] = useState<{ type: "success" | "warning" | "error"; message: string } | null>(null);

    const debounceTimerRef = useRef<any>(null);
    const activeRequestRef = useRef<AbortController | null>(null);

    const hasGeocoding = parseFloat(process.env.NEXT_PUBLIC_2GIS_MAP_DEFAULT_LAT || "0") !== 0;

    // Trigger address search suggestions on input change
    const handleAddressInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const queryVal = e.target.value;
        onChange({ ...value, address: queryVal });

        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        if (queryVal.trim().length < 3) {
            setSuggestions([]);
            setShowSuggestions(false);
            return;
        }

        debounceTimerRef.current = setTimeout(() => {
            fetchSuggestions(queryVal);
        }, 500); // 500ms debounce
    };

    const fetchSuggestions = async (queryStr: string) => {
        // Cancel stale requests
        if (activeRequestRef.current) {
            activeRequestRef.current.abort();
        }

        const controller = new AbortController();
        activeRequestRef.current = controller;

        setIsSearching(true);
        setNotice(null);

        try {
            const res = await api.post("/geo/geocode/", {
                query: queryStr,
                city: value.city,
                locale: locale
            }, {
                signal: controller.signal
            });

            if (res.data && Array.isArray(res.data.results)) {
                setSuggestions(res.data.results);
                setShowSuggestions(res.data.results.length > 0);
            }
        } catch (err: any) {
            if (err.name === "CanceledError" || err.name === "AbortError") {
                return; // Stale request ignored
            }
            console.error("Geocoding failed:", err);
            
            // Check for geocoder service disabled (503)
            if (err.response?.status === 503) {
                setNotice({ type: "warning", message: "Geocoding is disabled on this server. Manual input is available." });
            } else {
                setNotice({ type: "error", message: "Failed to search address. Please try again." });
            }
        } finally {
            setIsSearching(false);
        }
    };

    const handleSelectSuggestion = (s: any) => {
        onChange({
            address: s.address || s.name || value.address,
            city: s.city || value.city,
            latitude: s.latitude,
            longitude: s.longitude
        });
        setSuggestions([]);
        setShowSuggestions(false);
        setNotice(null);
    };

    // Handle pin placement on Map Click
    const handleMapClick = async (lat: number, lng: number) => {
        setNotice(null);
        
        // Temporarily set coordinates
        onChange({
            ...value,
            latitude: lat,
            longitude: lng
        });

        // Call reverse geocoder
        try {
            const res = await api.post("/geo/reverse-geocode/", {
                latitude: lat,
                longitude: lng,
                locale: locale
            });

            if (res.data && res.data.result) {
                const item = res.data.result;
                onChange({
                    address: item.address || item.name || value.address,
                    city: item.city || value.city,
                    latitude: lat,
                    longitude: lng
                });
            }
        } catch (err: any) {
            console.error("Reverse geocoding failed:", err);
            // Non-blocking warning: keep coordinates, let provider edit text manually
            setNotice({ 
                type: "warning", 
                message: "Reverse geocoding failed. Coordinates updated, please type address manually." 
            });
        }
    };

    const handleClearLocation = () => {
        onChange({
            address: "",
            city: "",
            latitude: null,
            longitude: null
        });
        setSuggestions([]);
        setShowSuggestions(false);
        setNotice(null);
    };

    // Cleanup effects on unmount
    useEffect(() => {
        return () => {
            if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
            if (activeRequestRef.current) activeRequestRef.current.abort();
        };
    }, []);

    // Localized labels with fallbacks
    const labels = {
        locationTitle: t("location.locationTitle") || "Service Location",
        locationDescription: t("location.locationDescription") || "Provide coordinate markers to show your service on the catalog map.",
        city: t("form.city") || "City",
        address: t("location.address") || "Street Address",
        addressPlaceholder: t("location.addressPlaceholder") || "e.g. Abaya avenue, 10a",
        latitude: t("location.latitude") || "Latitude",
        longitude: t("location.longitude") || "Longitude",
        clearLocation: t("location.clearLocation") || "Clear Location",
        manualCoordinates: t("location.manualCoordinates") || "Coordinates Overrides (Optional)",
        searchAddress: t("location.searchAddress") || "Search Address",
        searching: t("location.searching") || "Searching...",
        clickMapToPlace: t("location.clickMapToPlace") || "Or click on the map to drop a location pin:",
    };

    return (
        <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
            <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">5</span>
                <span>{labels.locationTitle}</span>
            </h3>

            <p className="text-xs text-slate-400 font-semibold leading-relaxed">
                {labels.locationDescription}
            </p>

            {notice && (
                <div className={`p-3 text-xs font-bold border rounded-xl flex items-center gap-2 ${
                    notice.type === "warning"
                        ? "bg-amber-50 border-amber-100 text-amber-700"
                        : notice.type === "error"
                        ? "bg-rose-50 border-rose-100 text-rose-700"
                        : "bg-emerald-50 border-emerald-100 text-emerald-700"
                }`}>
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>{notice.message}</span>
                </div>
            )}

            <div className="space-y-4 relative">
                {/* City Name Input */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                        label={`${labels.city} *`}
                        value={value.city}
                        onChange={(e) => onChange({ ...value, city: e.target.value })}
                        required
                        disabled={disabled}
                        placeholder="e.g. Almaty"
                    />

                    {/* Street Address Search Input */}
                    <div className="relative">
                        <Input
                            label={labels.address}
                            value={value.address}
                            onChange={handleAddressInputChange}
                            disabled={disabled}
                            placeholder={labels.addressPlaceholder}
                        />
                        {isSearching && (
                            <div className="absolute right-3 bottom-3 flex items-center">
                                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-violet-600"></div>
                            </div>
                        )}
                        
                        {/* Auto-suggest dropdown */}
                        {showSuggestions && suggestions.length > 0 && (
                            <div className="absolute left-0 right-0 z-30 mt-1 max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg divide-y divide-slate-100">
                                {suggestions.map((s, idx) => (
                                    <button
                                        key={s.id || idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(s)}
                                        className="w-full text-left px-4 py-2.5 hover:bg-slate-50 text-xs font-bold text-slate-700 transition cursor-pointer"
                                    >
                                        <div className="truncate font-black text-slate-900">{s.name}</div>
                                        <div className="truncate text-slate-400 font-semibold mt-0.5">{s.address}</div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Map Picker Visual Area */}
                <div className="space-y-2">
                    <label className="text-xs font-extrabold text-slate-800">
                        {labels.clickMapToPlace}
                    </label>
                    <div className="w-full h-[300px]">
                        <LocationPickerMap
                            latitude={value.latitude}
                            longitude={value.longitude}
                            onChangeLocation={handleMapClick}
                            disabled={disabled}
                        />
                    </div>
                </div>

                {/* Coordinates Info Manual Fallback */}
                <div className="bg-slate-50/50 p-4 border border-slate-200 rounded-2xl space-y-3">
                    <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                        {labels.manualCoordinates}
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Input
                            label={labels.latitude}
                            type="number"
                            step="any"
                            value={value.latitude !== null ? value.latitude : ""}
                            onChange={(e) => {
                                const lat = e.target.value === "" ? null : parseFloat(e.target.value);
                                onChange({ ...value, latitude: lat });
                            }}
                            disabled={disabled}
                            placeholder="e.g. 43.238949"
                        />
                        <Input
                            label={labels.longitude}
                            type="number"
                            step="any"
                            value={value.longitude !== null ? value.longitude : ""}
                            onChange={(e) => {
                                const lng = e.target.value === "" ? null : parseFloat(e.target.value);
                                onChange({ ...value, longitude: lng });
                            }}
                            disabled={disabled}
                            placeholder="e.g. 76.889709"
                        />
                    </div>

                    {(value.latitude !== null || value.longitude !== null || value.address !== "") && (
                        <div className="pt-2 flex justify-end">
                            <button
                                type="button"
                                onClick={handleClearLocation}
                                className="inline-flex items-center gap-1.5 text-xs font-bold text-rose-600 hover:text-rose-700 hover:underline transition cursor-pointer"
                            >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                                <span>{labels.clearLocation}</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </Card>
    );
}
