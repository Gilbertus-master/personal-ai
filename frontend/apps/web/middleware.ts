import { NextResponse } from 'next/server';

// Auth middleware disabled in dev — no Azure AD / NEXTAUTH_SECRET configured.
// Pass all requests through without auth checks.
export function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!login|api/auth|_next|favicon\\.ico|.*\\..*).*)',
  ],
};
