"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useAuthStore } from "@/store/useAuthStore";

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const locale = useLocale();
    const router = useRouter();
    const pathname = usePathname();
    const t = useTranslations("admin.reports");

    const isReady = useAuthStore((s) => s.isReady);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const user = useAuthStore((s) => s.user);

    useEffect(() => {
        if (!isReady) return;

        // 1. Not Authenticated -> Login
        if (!isAuthenticated) {
            const currentPath = pathname || `/${locale}/admin/reports/`;
            const next = encodeURIComponent(currentPath);
            router.replace(`/${locale}/login/?next=${next}`);
            return;
        }
    }, [isReady, isAuthenticated, router, locale, pathname]);

    if (!isReady) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-600 mb-4"></div>
                <p className="text-gray-500 font-medium">{t("loading")}</p>
            </div>
        );
    }

    if (!isAuthenticated) return null;

    const hasAccess = user?.is_staff === true || user?.is_superuser === true || user?.role === "admin";

    if (!hasAccess) {
        return (
            <div className="max-w-xl mx-auto text-center py-16 px-4">
                <div className="h-16 w-16 bg-rose-50 rounded-full flex items-center justify-center mx-auto text-rose-500 mb-4">
                    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <h2 className="text-2xl font-black text-gray-900 mb-2">{t("forbidden")}</h2>
            </div>
        );
    }

    return <>{children}</>;
}
