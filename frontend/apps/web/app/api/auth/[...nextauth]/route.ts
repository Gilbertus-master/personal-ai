// Auth route stub — works for dev (no Azure AD configured).
// Returns proper NextAuth v5 responses so SessionProvider resolves correctly.
export const dynamic = 'force-dynamic';

export function generateStaticParams() {
  return [{ nextauth: ['session'] }, { nextauth: ['csrf'] }];
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const path = url.pathname;

  if (path.endsWith('/session')) {
    // NextAuth v5 SessionProvider expects this exact shape for "no session"
    return new Response(JSON.stringify({ user: null, expires: '' }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
      },
    });
  }
  if (path.endsWith('/csrf')) {
    return Response.json({ csrfToken: 'dev-stub' });
  }
  if (path.endsWith('/providers')) {
    return Response.json({});
  }
  return Response.json({ error: 'not_configured' }, { status: 404 });
}

export async function POST(req: Request): Promise<Response> {
  return Response.json({ error: 'not_configured' }, { status: 404 });
}
