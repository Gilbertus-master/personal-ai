// Tauri static export requires force-static on all API routes.
// When TAURI_BUILD=1, auth stubs are returned (not needed in desktop app).
// In web mode, the real NextAuth handlers are used.
export const dynamic = 'force-static'; // Turbopack requires static string literal

export async function GET(req: Request) {
  if (process.env.TAURI_BUILD === '1') {
    return new Response(null, { status: 404 });
  }
  const { handlers } = await import('@/lib/auth');
  return handlers.GET(req as Parameters<typeof handlers.GET>[0]);
}

export async function POST(req: Request) {
  if (process.env.TAURI_BUILD === '1') {
    return new Response(null, { status: 404 });
  }
  const { handlers } = await import('@/lib/auth');
  return handlers.POST(req as Parameters<typeof handlers.POST>[0]);
}
