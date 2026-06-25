// frontend/src/app/[locale]/(provider)/layout.tsx
"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useAuthStore } from "@/store/useAuthStore";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default function ProviderLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const locale = useLocale();
    const router = useRouter();
    const pathname = usePathname();
    const tNav = useTranslations("nav");

    const isReady = useAuthStore((s) => s.isReady);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const user = useAuthStore((s) => s.user);

    useEffect(() => {
        // Only run logic when auth state is fully hydrated
        if (!isReady) return;

        // 1. Not Authenticated -> Login
        if (!isAuthenticated) {
            const currentPath = pathname || `/${locale}/provider/`;
            const next = encodeURIComponent(currentPath);
            router.replace(`/${locale}/login/?next=${next}`);
            return;
        }

        // 2. Authenticated but NOT Provider -> Client Dashboard
        if (user?.role && user.role !== "provider") {
            // Redirect to REAL client requests page, not legacy dashboard
            router.replace(`/${locale}/dashboard/requests/`);
            return;
        }
    }, [isReady, isAuthenticated, router, locale, user?.role, pathname]);

    // Show loading while hydrating auth state
    if (!isReady) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    // Don't render anything if redirects are pending
    if (!isAuthenticated) return null;
    if (user?.role !== "provider") return null;

    return (
        <DashboardShell role="provider" locale={locale} tNav={tNav}>
            {children}
        </DashboardShell>
    );
}
