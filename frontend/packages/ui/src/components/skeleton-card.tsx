import { cn } from '../lib/utils';

interface SkeletonCardProps {
  className?: string;
  height?: string;
  width?: string;
}

export function SkeletonCard({
  className,
  height = 'h-32',
  width = 'w-full',
}: SkeletonCardProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-muted',
        height,
        width,
        className,
      )}
    />
  );
}
