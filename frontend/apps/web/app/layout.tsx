import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/providers';

const inter = Inter({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'Gilbertus',
  description: 'AI Mentat — operational intelligence platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pl" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} font-sans bg-[var(--bg)] text-[var(--text)]`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
