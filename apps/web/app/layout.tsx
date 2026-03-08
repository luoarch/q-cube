import type { Metadata } from 'next';

import './globals.css';
import { QueryProvider } from '../src/components/providers/QueryProvider';
import { ThemeProvider } from '../src/components/providers/ThemeProvider';
import { DevAutoLogin } from '../src/components/providers/DevAutoLogin';

export const metadata: Metadata = {
  title: 'Q³ — Q-Cube',
  description: 'Quantitative Strategy Lab',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" data-theme="dark">
      <body>
        <QueryProvider>
          <ThemeProvider>
            <DevAutoLogin>{children}</DevAutoLogin>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
