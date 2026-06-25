// frontend/src/app/[locale]/(dashboard)/layout.tsx
"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useAuthStore } from "@/store/useAuthStore";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default function DashboardLayout({
    children,
}: {
    children: ReactNode;
}) {
    const locale = useLocale();
    const router = useRouter();
    const tNav = useTranslations("nav");

    const isReady = useAuthStore((s) => s.isReady);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const user = useAuthStore((s) => s.user);

    useEffect(() => {
        if (!isReady) return;

        // 1. Not Authenticated -> Login
        if (!isAuthenticated) {
            const next = encodeURIComponent(
                window.location.pathname + window.location.search
            );
            router.replace(`/${locale}/login?next=${next}`);
            return;
        }

        // 2. Authenticated -> Role-based redirects
        if (user?.role === "provider") {
            router.replace(`/${locale}/provider/`);
            return;
        }

        if (user?.is_staff || user?.is_superuser || user?.role === "admin") {
            router.replace(`/${locale}/admin/reports/`);
            return;
        }

        if (user?.role !== "client") {
            router.replace(`/${locale}/login`);
            return;
        }
    }, [isReady, isAuthenticated, user, router, locale]);

    if (!isReady) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }
    
    if (!isAuthenticated) return null;
    if (user?.role !== "client") return null; // Prevent layout flash on redirect

    return (
        <DashboardShell role="client" locale={locale} tNav={tNav}>
            {children}
        </DashboardShell>
    );
}
