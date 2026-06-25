import { useTranslations } from 'next-intl';
import { Service } from '@/types/catalog';
import { notFound } from 'next/navigation';
import ServiceDetailClient from '@/components/ServiceDetailClient';
import { ENDPOINTS } from '@/lib/api/endpoints';

const API_BASE =
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "http://localhost:8000";

const API_URL = API_BASE.endsWith("/api/v1")
    ? API_BASE
    : `${API_BASE.replace(/\/$/, "")}/api/v1`;

async function getService(id: string, locale: string): Promise<Service | null> {
    try {
        const url = `${API_URL.replace(/\/$/, '')}${ENDPOINTS.SERVICES}${id}/?lang=${locale}`;
        const res = await fetch(url, {
            headers: {
                'Accept-Language': locale,
            },
            next: { revalidate: 60 },
        });

        if (!res.ok) {
            return null;
        }

        return res.json();
    } catch (error) {
        return null;
    }
}

export default async function ServiceDetailPage({
    params,
}: {
    params: Promise<{ id: string; locale: string }>;
}) {
    const { id, locale } = await params;
    const service = await getService(id, locale);

    if (!service) {
        notFound();
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <ServiceDetailClient service={service} locale={locale} />
        </div>
    );
}
