import createMiddleware from 'next-intl/middleware';
import { routing } from './routing';

export default createMiddleware(routing);

export const config = {
    // Match all pathnames except for:
    // - API routes 
    // - Static files (_next/static)
    // - favicon, robots, etc.
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)'],
};
