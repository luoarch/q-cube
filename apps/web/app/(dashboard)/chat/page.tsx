'use client';

import Link from 'next/link';
import { Suspense } from 'react';

import { ChatPageInner } from './ChatPageInner';

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatPageFallback />}>
      <ChatPageInner />
    </Suspense>
  );
}

function ChatPageFallback() {
  return (
    <div className="dashboard-page" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header className="dashboard-header">
        <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Ranking
        </Link>
        <h1>AI Council</h1>
      </header>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
        Carregando...
      </div>
    </div>
  );
}
