import { useQuery } from '@tanstack/react-query';
import { getVoiceHealth } from '@gilbertus/api-client';

export function useVoiceHealth() {
  return useQuery({
    queryKey: ['voice-health'],
    queryFn: ({ signal }) => getVoiceHealth(signal),
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 1,
  });
}
