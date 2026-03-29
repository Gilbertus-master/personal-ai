'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';

type ThemeProviderProps = React.ComponentProps<typeof NextThemesProvider>;

export function ThemeProvider({
  children,
  defaultTheme = 'dark',
  attribute = 'class',
  ...props
}: ThemeProviderProps) {
  return (
    <NextThemesProvider defaultTheme={defaultTheme} attribute={attribute} {...props}>
      {children}
    </NextThemesProvider>
  );
}
