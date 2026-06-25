import { Metadata } from 'next';
import ProviderProfileClient from '@/components/ProviderProfileClient';
import { ENDPOINTS } from '@/lib/api/endpoints';

const API_BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

const API_URL = API_BASE.endsWith("/api/v1")
  ? API_BASE
  : `${API_BASE.replace(/\/$/, "")}/api/v1`;

async function getProvider(id: string) {
  try {
    const url = `${API_URL.replace(/\/$/, '')}${ENDPOINTS.PROVIDERS}${id}/`;
    const res = await fetch(url, {
      next: { revalidate: 60 },
    });
    if (res.ok) {
      return res.json();
    }
  } catch (error) {
    // ignore
  }
  return null;
}

export async function generateMetadata({
  params
}: {
  params: Promise<{ id: string; locale: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const provider = await getProvider(id);
  
  const title = provider ? `${provider.username} - EventMate Provider` : 'Provider Profile - EventMate';
  const description = provider?.bio || 'View provider services, portfolio, and reviews on EventMate.';
  
  return {
    title,
    description,
  };
}

export default async function ProviderDetailPage({
  params
}: {
  params: Promise<{ id: string; locale: string }>;
}) {
  const { id, locale } = await params;
  return <ProviderProfileClient id={id} locale={locale} />;
}
