import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import { notFound } from 'next/navigation';
import { AuthProvider } from '@/components/providers/AuthProvider';
import Header from '@/components/shared/Header';
import { routing } from '@/routing';
import { Outfit } from 'next/font/google';
import '../globals.css';

const outfit = Outfit({
    subsets: ['latin'],
    weight: ['300', '400', '500', '600', '700', '800', '900'],
    variable: '--font-outfit',
    display: 'swap',
});

export const metadata = {
    title: 'EventMate - Premium Event Services Marketplace',
    description: 'Найдите лучших провайдеров услуг для мероприятий в Казахстане',
};

export default async function LocaleLayout({
    children,
    params,
}: {
    children: React.ReactNode;
    params: Promise<{ locale: string }>;
}) {
    const { locale } = await params;

    // Ensure that the incoming `locale` is valid
    if (!routing.locales.includes(locale as any)) {
        notFound();
    }

    const messages = await getMessages();

    return (
        <html lang={locale}>
            <body className={`${outfit.variable} min-h-screen bg-gray-50 antialiased`}>
                <NextIntlClientProvider messages={messages}>
                    <AuthProvider>
                        <Header />
                        <main>{children}</main>
                    </AuthProvider>
                </NextIntlClientProvider>
            </body>
        </html>
    );
}

