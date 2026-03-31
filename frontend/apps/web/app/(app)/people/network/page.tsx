'use client';

import { useRouter } from 'next/navigation';
import { RbacGate, NetworkGraph } from '@gilbertus/ui';
import { useNetwork } from '@/lib/hooks/use-people';

export default function NetworkPage() {
  const network = useNetwork();
  const router = useRouter();

  return (
    <RbacGate roles={['owner', 'ceo', 'board']}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Sieć relacji
          </h1>
          <a
            href="/people"
            className="text-sm hover:underline"
            style={{ color: 'var(--text-secondary)' }}
          >
            &larr; Ludzie
          </a>
        </div>
        <div
          className="overflow-hidden rounded-lg border p-4"
          style={{
            height: '600px',
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          <NetworkGraph
            data={network.data}
            isLoading={network.isLoading}
            onNodeClick={(slug) => router.push(`/people/${slug}`)}
          />
        </div>
      </div>
    </RbacGate>
  );
}
