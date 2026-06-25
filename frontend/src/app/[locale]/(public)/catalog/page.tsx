import { Service, Category } from '@/types/catalog';
import { ENDPOINTS } from '@/lib/api/endpoints';
import CatalogClient from './CatalogClient';

// Standard API_BASE resolution (without /api/v1 suffix)
const API_BASE =
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    'http://localhost:8000';

// Generate correct API_URL
const API_URL = API_BASE.endsWith('/api/v1')
    ? API_BASE
    : `${API_BASE.replace(/\/$/, '')}/api/v1`;

async function getCategories(locale: string): Promise<Category[]> {
    const url = `${API_URL.replace(/\/$/, '')}${ENDPOINTS.CATEGORIES}?lang=${locale}`;
    try {
        const res = await fetch(url, {
            headers: {
                'Accept-Language': locale,
            },
            next: { revalidate: 300 }, // cache categories for 5 mins
        });

        if (!res.ok) {
            console.error(`[Catalog] Failed to fetch categories: ${res.status}. URL: ${url}`);
            return [];
        }

        return res.json();
    } catch (err) {
        console.error("[Catalog] Error fetching categories:", err);
        return [];
    }
}

interface PaginatedServices {
    results: Service[];
    count: number;
    next: string | null;
    previous: string | null;
}

async function getServices(filters: Record<string, string | undefined>, locale: string): Promise<PaginatedServices> {
    const query = new URLSearchParams();
    const ALLOWLIST = [
        "search",
        "category_id",
        "city",
        "provider",
        "price_min",
        "price_max",
        "ordering",
        "page",
        "lat",
        "lng",
        "radius",
        "bbox"
    ];

    ALLOWLIST.forEach((key) => {
        const value = filters[key];
        if (value !== undefined && value !== null) {
            const trimmed = typeof value === "string" ? value.trim() : String(value).trim();
            if (trimmed) {
                query.append(key, trimmed);
            }
        }
    });

    query.append("lang", locale);

    const queryString = query.toString();
    const url = `${API_URL.replace(/\/$/, '')}${ENDPOINTS.SERVICES}${queryString ? `?${queryString}` : ''}`;

    try {
        const res = await fetch(url, {
            headers: {
                'Accept-Language': locale,
            },
            cache: 'no-store', // SSR fetch without cache for active filters
        });

        if (!res.ok) {
            console.error(`[Catalog] Failed to fetch services: ${res.status}. URL: ${url}`);
            return { results: [], count: 0, next: null, previous: null };
        }

        const data = await res.json();

        // Normalization
        if (Array.isArray(data)) {
            return { results: data, count: data.length, next: null, previous: null };
        }
        if (data && Array.isArray(data.results)) {
            return {
                results: data.results,
                count: data.count ?? data.results.length,
                next: data.next ?? null,
                previous: data.previous ?? null,
            };
        }

        return { results: [], count: 0, next: null, previous: null };
    } catch (err) {
        console.error(`[Catalog] Error fetching services:`, err);
        return { results: [], count: 0, next: null, previous: null };
    }
}

export default async function CatalogPage({
    params,
    searchParams,
}: {
    params: Promise<{ locale: string }>;
    searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
    const { locale } = await params;
    const resolvedSearchParams = await searchParams;

    // Fetch categories and services concurrently on the server
    const [categories, servicesData] = await Promise.all([
        getCategories(locale),
        getServices(resolvedSearchParams, locale),
    ]);

    const currentPage = resolvedSearchParams.page ? parseInt(resolvedSearchParams.page, 10) : 1;

    return (
        <div className="container mx-auto px-4 py-8">
            <CatalogClient
                categories={categories}
                services={servicesData.results}
                count={servicesData.count}
                next={servicesData.next}
                previous={servicesData.previous}
                currentPage={currentPage}
                locale={locale}
                filters={resolvedSearchParams}
            />
        </div>
    );
}
