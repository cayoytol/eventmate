import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n.ts');

// Helper to normalize the backend URL and prevent double slashes
export function getCleanRewriteDestination(backendUrl: string): string {
    let cleanUrl = backendUrl.trim();
    
    // Strip trailing slashes
    while (cleanUrl.endsWith('/')) {
        cleanUrl = cleanUrl.slice(0, -1);
    }
    
    // Clean up trailing /api or /api/v1 to avoid nested api paths in the destination
    if (cleanUrl.endsWith('/api/v1')) {
        cleanUrl = cleanUrl.slice(0, -7);
    } else if (cleanUrl.endsWith('/api')) {
        cleanUrl = cleanUrl.slice(0, -4);
    }
    
    while (cleanUrl.endsWith('/')) {
        cleanUrl = cleanUrl.slice(0, -1);
    }
    
    return `${cleanUrl}/api/:path*`;
}

// Inline assertions to verify the rewrite helper behaves exactly as required
function runRewriteNormalizationTests() {
    const testCases = [
        { origin: "http://localhost:8000", expected: "http://localhost:8000/api/:path*" },
        { origin: "http://localhost:8000/", expected: "http://localhost:8000/api/:path*" },
        { origin: "http://localhost:8000/api", expected: "http://localhost:8000/api/:path*" },
        { origin: "http://localhost:8000/api/v1", expected: "http://localhost:8000/api/:path*" },
        { origin: "http://localhost:8000/api/v1/", expected: "http://localhost:8000/api/:path*" },
        { origin: "https://sfera-backend-8hif.onrender.com", expected: "https://sfera-backend-8hif.onrender.com/api/:path*" },
        { origin: "https://sfera-backend-8hif.onrender.com///", expected: "https://sfera-backend-8hif.onrender.com/api/:path*" },
    ];
    
    for (const tc of testCases) {
        const actual = getCleanRewriteDestination(tc.origin);
        if (actual !== tc.expected) {
            throw new Error(`[Rewrite Test Failed] Origin: "${tc.origin}". Expected: "${tc.expected}", Got: "${actual}"`);
        }
    }
}

// Execute tests during config loading
runRewriteNormalizationTests();

const backendUrl =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000";

const nextConfig: NextConfig = {
    // Preserve trailing slashes to match Django APPEND_SLASH=True
    trailingSlash: true,

    images: {
        remotePatterns: [
            {
                protocol: 'http',
                hostname: 'localhost',
                port: '8000',
                pathname: '/media/**',
            },
            {
                protocol: 'https',
                hostname: '*.onrender.com',
                pathname: '/media/**',
            },
            {
                // Accept S3/R2 storage hosts
                protocol: 'https',
                hostname: '*.amazonaws.com',
                pathname: '/**',
            },
            {
                // Accept custom domains for Render backend media
                protocol: 'https',
                hostname: 'sfera-backend-8hif.onrender.com',
                pathname: '/media/**',
            }
        ],
    },
    async rewrites() {
        return [
            {
                source: "/api/:path*",
                destination: getCleanRewriteDestination(backendUrl),
            },
        ];
    },
};

export default withNextIntl(nextConfig);
