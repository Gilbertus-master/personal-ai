import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import MicrosoftEntraID from 'next-auth/providers/microsoft-entra-id';
import type { RoleName } from '@gilbertus/rbac';

declare module 'next-auth' {
  interface User {
    role: RoleName;
    roleLevel: number;
    permissions: string[];
    tenant: string;
    authType: 'api_key' | 'azure_ad';
  }

  interface Session {
    user: User & {
      id: string;
      email: string;
      name: string;
    };
  }
}

// JWT token fields are typed via `any` casts in callbacks below.
// Module augmentation for @auth/core/jwt is not resolvable in this monorepo setup.

const GILBERTUS_API_URL =
  process.env.GILBERTUS_API_URL || 'http://127.0.0.1:8000';

const nextAuth = NextAuth({
  providers: [
    Credentials({
      id: 'api-key',
      name: 'API Key',
      credentials: {
        apiKey: { label: 'API Key', type: 'password' },
      },
      async authorize(credentials) {
        const apiKey = credentials?.apiKey;
        if (typeof apiKey !== 'string' || !apiKey) return null;

        try {
          const res = await fetch(`${GILBERTUS_API_URL}/health`, {
            headers: { 'X-API-Key': apiKey },
          });

          if (res.ok) {
            return {
              id: 'owner',
              email: 'sebastian@gilbertus.local',
              name: 'Sebastian',
              role: 'owner' as RoleName,
              roleLevel: 100,
              permissions: [],
              tenant: 'gilbertus',
              authType: 'api_key' as const,
            };
          }
        } catch {
          // API unreachable
        }

        return null;
      },
    }),
    MicrosoftEntraID({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      issuer: process.env.AZURE_AD_TENANT_ID,
      // TODO: Full Omnius user lookup — for now map Azure AD profile to basic session
    }),
  ],
  pages: {
    signIn: '/login',
  },
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.role = (user as any).role;
        token.roleLevel = (user as any).roleLevel;
        token.permissions = (user as any).permissions;
        token.tenant = (user as any).tenant;
        token.authType = (user as any).authType;
      }
      return token;
    },
    session({ session, token }) {
      const t = token as any;
      session.user.role = t.role;
      session.user.roleLevel = t.roleLevel;
      session.user.permissions = t.permissions;
      session.user.tenant = t.tenant;
      session.user.authType = t.authType;
      return session;
    },
  },
});

export const { handlers, auth, signIn, signOut } = nextAuth;
