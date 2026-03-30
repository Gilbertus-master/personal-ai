// NextAuth route — conditionally stubbed for Tauri static export.
// Turbopack (Next.js 16) can't handle dynamic imports in force-static routes,
// so the real handlers are only loaded via top-level import in web mode.
export const dynamic = 'force-static';

// NOTE: real auth is handled by next.config.ts webpack alias in web mode.
// In Tauri build (TAURI_BUILD=1), this stub is used directly.
export async function GET(_req: Request): Promise<Response> {
  return new Response(null, { status: 404 });
}

export async function POST(_req: Request): Promise<Response> {
  return new Response(null, { status: 404 });
}
