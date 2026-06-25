"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Category } from "@/types/catalog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";

interface FilterFormProps {
    categories: Category[];
    initialFilters: {
        search?: string;
        city?: string;
        category_id?: string;
        price_min?: string;
        price_max?: string;
        ordering?: string;
    };
}

export default function FilterForm({ categories, initialFilters }: FilterFormProps) {
    const t = useTranslations("catalog");
    const router = useRouter();
    const pathname = usePathname();

    // Form state
    const [search, setSearch] = useState(initialFilters.search || "");
    const [city, setCity] = useState(initialFilters.city || "");
    const [categoryId, setCategoryId] = useState(initialFilters.category_id || "");
    const [priceMin, setPriceMin] = useState(initialFilters.price_min || "");
    const [priceMax, setPriceMax] = useState(initialFilters.price_max || "");
    const [ordering, setOrdering] = useState(initialFilters.ordering || "-created_at");

    // Collapsible filters state for mobile
    const [isExpanded, setIsExpanded] = useState(false);

    // Flatten category tree for select options
    const getFlattenedCategories = () => {
        const list: Array<{ id: number; name: string }> = [];
        const traverse = (cats: Category[], depth = 0) => {
            cats.forEach((cat) => {
                list.push({ id: cat.id, name: "\u00A0\u00A0".repeat(depth) + cat.name });
                if (cat.children && cat.children.length > 0) {
                    traverse(cat.children, depth + 1);
                }
            });
        };
        traverse(categories);
        return list;
    };
    const flattenedCategories = getFlattenedCategories();

    const handleApply = (e: React.FormEvent) => {
        e.preventDefault();
        const params = new URLSearchParams();

        if (search.trim()) params.append("search", search.trim());
        if (city.trim()) params.append("city", city.trim());
        if (categoryId) params.append("category_id", categoryId);
        if (priceMin) params.append("price_min", priceMin);
        if (priceMax) params.append("price_max", priceMax);
        if (ordering) params.append("ordering", ordering);

        router.push(`${pathname}?${params.toString()}`);
    };

    const handleReset = () => {
        setSearch("");
        setCity("");
        setCategoryId("");
        setPriceMin("");
        setPriceMax("");
        setOrdering("-created_at");
        router.push(pathname);
    };

    return (
        <form onSubmit={handleApply} className="bg-white border border-neutral-200 rounded-2xl p-4 shadow-sm mb-6">
            {/* Title & Mobile Toggle */}
            <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-black text-neutral-800 flex items-center gap-2">
                    <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 8.293A1 1 0 013 7.586V4z" />
                    </svg>
                    {t("filters.title")}
                </h2>

                {/* Mobile expand button */}
                <button
                    type="button"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="md:hidden flex items-center gap-1.5 px-3 py-1.5 border border-neutral-200 bg-neutral-50 text-neutral-600 rounded-xl text-xs font-bold hover:bg-neutral-100 transition duration-150 active:scale-95"
                >
                    <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    </svg>
                    <span>
                        {isExpanded ? t("filters.hide") : t("filters.show")}
                    </span>
                </button>
            </div>

            {/* Collapsible Container */}
            <div className={`${isExpanded ? "block" : "hidden"} md:block mt-4`}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Search */}
                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.search")}
                        </label>
                        <Input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder={t("filters.searchPlaceholder")}
                        />
                    </div>

                    {/* City */}
                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.city")}
                        </label>
                        <Input
                            type="text"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            placeholder={t("filters.cityPlaceholder")}
                        />
                    </div>

                    {/* Category */}
                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.category")}
                        </label>
                        <Select
                            value={categoryId}
                            onChange={(e) => setCategoryId(e.target.value)}
                        >
                            <option value="">{t("filters.allCategories")}</option>
                            {flattenedCategories.map((category) => (
                                <option key={category.id} value={category.id}>
                                    {category.name}
                                </option>
                            ))}
                        </Select>
                    </div>

                    {/* Price Range */}
                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.priceMin")}
                        </label>
                        <Input
                            type="number"
                            value={priceMin}
                            onChange={(e) => setPriceMin(e.target.value)}
                            placeholder="0"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.priceMax")}
                        </label>
                        <Input
                            type="number"
                            value={priceMax}
                            onChange={(e) => setPriceMax(e.target.value)}
                            placeholder="1000000"
                        />
                    </div>

                    {/* Sorting */}
                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1.5">
                            {t("filters.sort")}
                        </label>
                        <Select
                            value={ordering}
                            onChange={(e) => setOrdering(e.target.value)}
                        >
                            <option value="-created_at">{t("sort.newest")}</option>
                            <option value="created_at">{t("sort.oldest")}</option>
                            <option value="price_amount">{t("sort.priceAsc")}</option>
                            <option value="-price_amount">{t("sort.priceDesc")}</option>
                        </Select>
                    </div>
                </div>

                {/* Action buttons */}
                <div className="flex gap-3 mt-4 justify-end">
                    <Button
                        type="button"
                        onClick={handleReset}
                        variant="outline"
                        size="sm"
                    >
                        {t("filters.reset")}
                    </Button>
                    <Button
                        type="submit"
                        variant="primary"
                        size="sm"
                    >
                        {t("filters.apply")}
                    </Button>
                </div>
            </div>
        </form>
    );
}
