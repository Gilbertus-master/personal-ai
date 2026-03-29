import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getOwnApiKeys, createApiKey } from '@gilbertus/api-client';

export function useOwnApiKeys() {
  return useQuery({
    queryKey: ['own-api-keys'],
    queryFn: ({ signal }) => getOwnApiKeys(signal),
    staleTime: 60_000,
  });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; role: string; user_email: string }) =>
      createApiKey(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['own-api-keys'] }),
  });
}
