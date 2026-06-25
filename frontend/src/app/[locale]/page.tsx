"use client";

import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/routing';
import { useState, use } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

interface LandingPageProps {
    params: Promise<{
        locale: string;
    }>;
}

export default function RootPage(props: LandingPageProps) {
    const params = use(props.params);
    const { locale } = params;
    const t = useTranslations('landing');
    const router = useRouter();
    
    const [search, setSearch] = useState('');
    const [city, setCity] = useState('');

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        const query = new URLSearchParams();
        if (search.trim()) query.append('search', search.trim());
        if (city.trim()) query.append('city', city.trim());
        router.push(`/catalog?${query.toString()}`);
    };

    return (
        <div className="space-y-20 pb-20">
            {/* 1. Hero Section */}
            <section className="relative overflow-hidden bg-gradient-to-br from-violet-950 via-indigo-950 to-slate-950 text-white py-20 px-4 md:py-32">
                {/* Decorative glow elements */}
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />

                <div className="max-w-5xl mx-auto text-center relative z-10 space-y-8">
                    <div className="space-y-4">
                        <Badge variant="violet" className="bg-violet-500/10 text-violet-300 border border-violet-500/20 px-4 py-1.5 text-xs font-bold uppercase tracking-widest">
                            Eventmate Platform
                        </Badge>
                        <h1 className="text-4xl md:text-6xl font-black tracking-tight text-white leading-tight">
                            {t('hero.title')}
                        </h1>
                        <p className="text-lg md:text-xl text-neutral-300 max-w-3xl mx-auto font-medium leading-relaxed">
                            {t('hero.subtitle')}
                        </p>
                    </div>

                    {/* Search & Filter CTA Panel */}
                    <form onSubmit={handleSearch} className="bg-white/10 backdrop-blur-md border border-white/10 p-3 rounded-3xl shadow-2xl max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-3">
                        <div className="md:col-span-5 relative flex items-center">
                            <svg className="w-5 h-5 absolute left-4 text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <input
                                type="text"
                                placeholder={t('hero.searchPlaceholder')}
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="w-full bg-transparent border-0 pl-12 pr-4 py-3 text-sm text-white placeholder:text-neutral-400 focus:outline-none focus:ring-0 focus:border-0"
                            />
                        </div>
                        <div className="md:col-span-4 relative flex items-center md:border-l md:border-white/10">
                            <svg className="w-5 h-5 absolute left-4 text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <input
                                type="text"
                                placeholder={t('hero.cityPlaceholder')}
                                value={city}
                                onChange={(e) => setCity(e.target.value)}
                                className="w-full bg-transparent border-0 pl-12 pr-4 py-3 text-sm text-white placeholder:text-neutral-400 focus:outline-none focus:ring-0 focus:border-0"
                            />
                        </div>
                        <div className="md:col-span-3 flex items-center">
                            <button
                                type="submit"
                                className="w-full bg-violet-600 hover:bg-violet-750 text-white font-bold text-sm py-3 px-6 rounded-2xl shadow-lg transition duration-205 active:scale-95 flex items-center justify-center gap-2"
                            >
                                <span>{t('hero.findServices')}</span>
                            </button>
                        </div>
                    </form>

                    {/* Secondary Navigation CTAs */}
                    <div className="flex flex-wrap justify-center gap-4 pt-4">
                        <Link
                            href="/catalog"
                            className="bg-white text-neutral-900 font-bold px-6 py-3.5 rounded-2xl transition duration-200 hover:bg-neutral-100 active:scale-95 shadow-md text-sm"
                        >
                            {t('hero.findServices')}
                        </Link>
                        <Link
                            href="/register"
                            className="bg-transparent border border-white/30 text-white font-bold px-6 py-3.5 rounded-2xl transition duration-200 hover:bg-white/10 hover:border-white/50 active:scale-95 text-sm"
                        >
                            {t('hero.becomeProvider')}
                        </Link>
                    </div>
                </div>
            </section>

            {/* 2. Trust/Value Proposition blocks (6 cards) */}
            <section className="max-w-5xl mx-auto px-4">
                <div className="text-center space-y-4 mb-12">
                    <h2 className="text-3xl font-black text-neutral-900">{t('trust.title')}</h2>
                    <div className="w-16 h-1 bg-violet-600 mx-auto rounded-full" />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {/* Card 1: Verified Providers */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-violet-50 text-violet-600 rounded-3xl">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.verified')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.verifiedDesc')}</p>
                    </Card>

                    {/* Card 2: Transparent Offers */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-emerald-50 text-emerald-600 rounded-3xl">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.transparent')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.transparentDesc')}</p>
                    </Card>

                    {/* Card 3: QR Quality Control */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-rose-50 text-rose-600 rounded-3xl">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h.01M16 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M7 9h10v8H7V9z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.qrControl')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.qrControlDesc')}</p>
                    </Card>

                    {/* Card 4: Reviews & Ratings */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-amber-50 text-amber-600 rounded-3xl">
                            <svg className="w-7 h-7 text-amber-500 fill-amber-500" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.reviews')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.reviewsDesc')}</p>
                    </Card>

                    {/* Card 5: Secure Role-Based Flow */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-blue-50 text-blue-600 rounded-3xl">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.secure')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.secureDesc')}</p>
                    </Card>

                    {/* Card 6: Multilingual Support */}
                    <Card className="flex flex-col items-center text-center space-y-4 hoverable p-6">
                        <div className="p-4 bg-purple-50 text-purple-650 rounded-3xl">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 0H7m5 5v2m-8 1h16a2 2 0 002-2V9a2 2 0 00-2-2H4a2 2 0 00-2 2v7a2 2 0 002 2z" />
                            </svg>
                        </div>
                        <h3 className="font-extrabold text-neutral-900 text-lg">{t('trust.multilingual')}</h3>
                        <p className="text-neutral-500 text-sm leading-relaxed">{t('trust.multilingualDesc')}</p>
                    </Card>
                </div>
            </section>

            {/* 3. How it Works Section */}
            <section className="bg-neutral-50 py-16 border-y border-neutral-100">
                <div className="max-w-5xl mx-auto px-4">
                    <div className="text-center space-y-4 mb-16">
                        <h2 className="text-3xl font-black text-neutral-900">{t('howItWorks.title')}</h2>
                        <p className="text-neutral-500 max-w-xl mx-auto text-sm">{t('howItWorks.subtitle')}</p>
                        <div className="w-16 h-1 bg-violet-600 mx-auto rounded-full" />
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
                        <div className="space-y-2 relative">
                            <div className="w-10 h-10 rounded-2xl bg-violet-600 text-white flex items-center justify-center font-bold text-sm mb-4 shadow-md shadow-violet-100">1</div>
                            <h3 className="font-extrabold text-neutral-900 text-base">{t('howItWorks.step1Title')}</h3>
                            <p className="text-neutral-500 text-xs leading-relaxed">{t('howItWorks.step1Desc')}</p>
                        </div>
                        <div className="space-y-2 relative">
                            <div className="w-10 h-10 rounded-2xl bg-violet-600 text-white flex items-center justify-center font-bold text-sm mb-4 shadow-md shadow-violet-100">2</div>
                            <h3 className="font-extrabold text-neutral-900 text-base">{t('howItWorks.step2Title')}</h3>
                            <p className="text-neutral-500 text-xs leading-relaxed">{t('howItWorks.step2Desc')}</p>
                        </div>
                        <div className="space-y-2 relative">
                            <div className="w-10 h-10 rounded-2xl bg-violet-600 text-white flex items-center justify-center font-bold text-sm mb-4 shadow-md shadow-violet-100">3</div>
                            <h3 className="font-extrabold text-neutral-900 text-base">{t('howItWorks.step3Title')}</h3>
                            <p className="text-neutral-500 text-xs leading-relaxed">{t('howItWorks.step3Desc')}</p>
                        </div>
                        <div className="space-y-2 relative">
                            <div className="w-10 h-10 rounded-2xl bg-violet-600 text-white flex items-center justify-center font-bold text-sm mb-4 shadow-md shadow-violet-100">4</div>
                            <h3 className="font-extrabold text-neutral-900 text-base">{t('howItWorks.step4Title')}</h3>
                            <p className="text-neutral-500 text-xs leading-relaxed">{t('howItWorks.step4Desc')}</p>
                        </div>
                        <div className="space-y-2 relative">
                            <div className="w-10 h-10 rounded-2xl bg-violet-600 text-white flex items-center justify-center font-bold text-sm mb-4 shadow-md shadow-violet-100">5</div>
                            <h3 className="font-extrabold text-neutral-900 text-base">{t('howItWorks.step5Title')}</h3>
                            <p className="text-neutral-500 text-xs leading-relaxed">{t('howItWorks.step5Desc')}</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* 4. AI Helper Highlight Section */}
            <section className="max-w-5xl mx-auto px-4">
                <Card className="bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-100 p-8 md:p-12 rounded-3xl shadow-xs relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-8">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-violet-300/10 rounded-full blur-2xl pointer-events-none" />
                    <div className="space-y-4 max-w-2xl">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">✨</span>
                            <Badge className="bg-violet-100 text-violet-800 font-extrabold uppercase tracking-wider text-[10px] border border-violet-200">
                                Smart AI
                            </Badge>
                        </div>
                        <h2 className="text-2xl md:text-3xl font-black text-neutral-900">{t('aiHighlight.title')}</h2>
                        <p className="text-neutral-600 text-sm md:text-base leading-relaxed">
                            {t('aiHighlight.desc')}
                        </p>
                    </div>
                    <div className="shrink-0 flex items-center gap-4 z-10">
                        <Link
                            href="/catalog"
                            className="bg-violet-600 hover:bg-violet-700 text-white font-bold text-sm py-3.5 px-6 rounded-2xl shadow-md transition duration-200 active:scale-95 shadow-violet-100 hover:shadow-lg"
                        >
                            {t('hero.findServices')}
                        </Link>
                    </div>
                </Card>
            </section>

            {/* 5. Statistics block (4 cards) */}
            <section className="max-w-5xl mx-auto px-4">
                <div className="text-center space-y-4 mb-12">
                    <h2 className="text-3xl font-black text-neutral-900">{t('stats.title')}</h2>
                    <div className="w-16 h-1 bg-violet-600 mx-auto rounded-full" />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    <Card className="text-center space-y-2 p-6 hoverable border-neutral-150">
                        <h4 className="text-3xl font-black text-violet-600 leading-none">{t('stats.usersVal')}</h4>
                        <p className="text-neutral-500 text-xs font-bold uppercase tracking-wider">{t('stats.users')}</p>
                    </Card>
                    <Card className="text-center space-y-2 p-6 hoverable border-neutral-150">
                        <h4 className="text-3xl font-black text-violet-600 leading-none">{t('stats.testsVal')}</h4>
                        <p className="text-neutral-500 text-xs font-bold uppercase tracking-wider">{t('stats.tests')}</p>
                    </Card>
                    <Card className="text-center space-y-2 p-6 hoverable border-neutral-150">
                        <h4 className="text-3xl font-black text-violet-600 leading-none">{t('stats.i18nVal')}</h4>
                        <p className="text-neutral-500 text-xs font-bold uppercase tracking-wider">{t('stats.i18n')}</p>
                    </Card>
                    <Card className="text-center space-y-2 p-6 hoverable border-neutral-150">
                        <h4 className="text-3xl font-black text-violet-600 leading-none">{t('stats.flowVal')}</h4>
                        <p className="text-neutral-500 text-xs font-bold uppercase tracking-wider">{t('stats.flow')}</p>
                    </Card>
                </div>
            </section>

            {/* 6. Final CTA Section */}
            <section className="max-w-4xl mx-auto px-4 text-center space-y-8 py-8">
                <div className="space-y-4">
                    <h2 className="text-3xl md:text-4xl font-black tracking-tight text-neutral-900 leading-tight">
                        {t('cta.title')}
                    </h2>
                    <p className="text-neutral-500 max-w-xl mx-auto leading-relaxed text-sm">
                        {t('cta.subtitle')}
                    </p>
                </div>
                <div className="flex flex-wrap justify-center gap-4">
                    <Link
                        href="/catalog"
                        className="bg-violet-600 hover:bg-violet-700 text-white font-bold px-8 py-3.5 rounded-2xl shadow-lg transition duration-200 hover:shadow-violet-200 active:scale-95 text-sm"
                    >
                        {t('hero.findServices')}
                    </Link>
                    <Link
                        href="/register"
                        className="bg-white border border-neutral-200 text-neutral-700 hover:bg-neutral-50 font-bold px-8 py-3.5 rounded-2xl shadow-sm transition duration-200 active:scale-95 text-sm"
                    >
                        {t('hero.becomeProvider')}
                    </Link>
                </div>
            </section>
        </div>
    );
}
