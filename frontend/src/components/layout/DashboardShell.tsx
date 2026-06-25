import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavItem {
    label: string;
    href: string;
    icon: React.ReactNode;
}

interface DashboardShellProps {
    children: React.ReactNode;
    role: 'client' | 'provider' | 'admin';
    locale: string;
    tNav?: (key: string) => string;
}

export const DashboardShell: React.FC<DashboardShellProps> = ({
    children,
    role,
    locale,
    tNav,
}) => {
    const pathname = usePathname();
    const [isMobileOpen, setIsMobileOpen] = useState(false);

    // Fallback translation helper
    const translate = (key: string, fallback: string): string => {
        if (tNav) {
            try {
                return tNav(key);
            } catch {
                return fallback;
            }
        }
        return fallback;
    };

    // Navigation items based on role
    const getNavItems = (): NavItem[] => {
        switch (role) {
            case 'client':
                return [
                    {
                        label: translate('home', 'Overview'),
                        href: `/${locale}/dashboard`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('requests', 'My Requests'),
                        href: `/${locale}/dashboard/requests`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('orders', 'My Orders'),
                        href: `/${locale}/dashboard/orders`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('chats', 'Chats'),
                        href: `/${locale}/dashboard/chats`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('favorites', 'Favorites'),
                        href: `/${locale}/dashboard/favorites`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('notifications', 'Notifications'),
                        href: `/${locale}/dashboard/notifications`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                            </svg>
                        ),
                    },
                ];
            case 'provider':
                return [
                    {
                        label: translate('home', 'Overview'),
                        href: `/${locale}/provider`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('services', 'My Services'),
                        href: `/${locale}/provider/services`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('findRequests', 'Find Requests'),
                        href: `/${locale}/provider/requests`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('orders', 'My Orders'),
                        href: `/${locale}/provider/orders`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('chats', 'Chats'),
                        href: `/${locale}/provider/chats`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('calendar', 'Calendar'),
                        href: `/${locale}/provider/calendar`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('portfolio', 'Portfolio'),
                        href: `/${locale}/provider/portfolio`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('billing', 'Billing'),
                        href: `/${locale}/provider/billing`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('notifications', 'Notifications'),
                        href: `/${locale}/provider/notifications`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                            </svg>
                        ),
                    },
                    {
                        label: translate('settings', 'Settings'),
                        href: `/${locale}/provider/settings`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                        ),
                    },
                ];
            case 'admin':
                return [
                    {
                        label: translate('reports', 'Reports Moderation'),
                        href: `/${locale}/admin/reports`,
                        icon: (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        ),
                    },
                ];
            default:
                return [];
        }
    };

    const navItems = getNavItems();

    const isLinkActive = (href: string): boolean => {
        // Direct equal or matches subpaths
        if (pathname === href) return true;
        // Normalize slash endings
        const cleanPath = pathname?.replace(/\/$/, '') || '';
        const cleanHref = href.replace(/\/$/, '');
        
        // Exact match
        if (cleanPath === cleanHref) return true;
        
        // Skip root match checks for subpage mappings
        if (cleanHref.endsWith('/dashboard') || cleanHref.endsWith('/provider')) {
            return cleanPath === cleanHref;
        }
        
        return cleanPath.startsWith(cleanHref + '/');
    };

    return (
        <div className="flex flex-col md:flex-row min-h-[calc(100vh-80px)] bg-neutral-50/50">
            {/* Desktop Sidebar */}
            <aside className="hidden md:block w-64 bg-white border-r border-slate-200 shrink-0">
                <nav className="p-4 space-y-1">
                    {navItems.map((item, idx) => {
                        const active = isLinkActive(item.href);
                        return (
                            <Link
                                key={idx}
                                href={item.href}
                                className={`flex items-center gap-3 px-4 py-3 text-sm font-semibold rounded-xl transition ${
                                    active
                                        ? 'bg-violet-50 text-violet-700'
                                        : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
                                }`}
                            >
                                {item.icon}
                                {item.label}
                            </Link>
                        );
                    })}
                </nav>
            </aside>

            {/* Mobile Header / Nav Toggle */}
            <div className="md:hidden bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between z-20">
                <span className="text-sm font-bold text-neutral-800 uppercase tracking-wide">
                    {role === 'client' ? 'Client Area' : role === 'provider' ? 'Provider Area' : 'Admin Area'}
                </span>
                <button
                    onClick={() => setIsMobileOpen(!isMobileOpen)}
                    className="p-2 text-neutral-600 hover:bg-neutral-50 rounded-xl transition"
                    aria-label="Toggle Navigation"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>
            </div>

            {/* Mobile Drawer Navigation */}
            {isMobileOpen && (
                <div className="md:hidden fixed inset-0 z-30 flex">
                    <div className="fixed inset-0 bg-neutral-900/30 backdrop-blur-xs" onClick={() => setIsMobileOpen(false)} />
                    <nav className="relative flex flex-col w-64 max-w-xs bg-white h-full p-4 space-y-1 shadow-xl z-10 animate-in slide-in-from-left duration-200">
                        <div className="flex items-center justify-between mb-6 pb-4 border-b">
                            <span className="font-extrabold text-neutral-900">Menu</span>
                            <button
                                onClick={() => setIsMobileOpen(false)}
                                className="p-1 text-neutral-400 hover:text-neutral-600 rounded-lg"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        {navItems.map((item, idx) => {
                            const active = isLinkActive(item.href);
                            return (
                                <Link
                                    key={idx}
                                    href={item.href}
                                    onClick={() => setIsMobileOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-3 text-sm font-semibold rounded-xl transition ${
                                        active
                                            ? 'bg-violet-50 text-violet-700'
                                            : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
                                    }`}
                                >
                                    {item.icon}
                                    {item.label}
                                </Link>
                            );
                        })}
                    </nav>
                </div>
            )}

            {/* Main Content Area */}
            <div className="flex-1 p-4 md:p-8 min-w-0">
                {children}
            </div>
        </div>
    );
};
