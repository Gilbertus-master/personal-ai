import { cn } from '../lib/utils';

interface PageSkeletonProps {
  variant: 'card' | 'table' | 'list' | 'detail';
  rows?: number;
  columns?: number;
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-[var(--surface)]', className)} />;
}

function CardVariant({ rows = 6, columns = 3 }: { rows?: number; columns?: number }) {
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonBlock key={i} className="h-32 w-full" />
      ))}
    </div>
  );
}

function TableVariant({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <SkeletonBlock key={i} className="h-8 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: columns }).map((_, j) => (
            <SkeletonBlock key={j} className="h-10 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

function ListVariant({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonBlock key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

function DetailVariant() {
  return (
    <div className="space-y-6">
      <SkeletonBlock className="h-16 w-full" />
      <div className="space-y-3">
        <SkeletonBlock className="h-6 w-3/4" />
        <SkeletonBlock className="h-6 w-1/2" />
      </div>
      <SkeletonBlock className="h-48 w-full" />
      <div className="grid grid-cols-2 gap-4">
        <SkeletonBlock className="h-24" />
        <SkeletonBlock className="h-24" />
      </div>
    </div>
  );
}

export function PageSkeleton({ variant, rows, columns }: PageSkeletonProps) {
  switch (variant) {
    case 'card':
      return <CardVariant rows={rows} columns={columns} />;
    case 'table':
      return <TableVariant rows={rows} columns={columns} />;
    case 'list':
      return <ListVariant rows={rows} />;
    case 'detail':
      return <DetailVariant />;
  }
}
