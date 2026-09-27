import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getPrediction, predictStudy } from '../api/studies';
import { studyKeys } from './useStudy';
import type { components } from '../api/schema';

type PredictionResponse = components['schemas']['PredictionResponse'];

export function usePredict({ studyId }: { studyId: string | undefined }) {
  const queryClient = useQueryClient();
  const predictionKey = ['prediction', studyId] as const;

  const query = useQuery({
    queryKey: predictionKey,
    queryFn: async () => {
      if (!studyId) throw new Error('studyId is required');
      return getPrediction(studyId);
    },
    enabled: Boolean(studyId),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: async (): Promise<PredictionResponse> => {
      if (!studyId) throw new Error('studyId is required');
      return predictStudy(studyId);
    },
    onSuccess: (prediction) => {
      queryClient.setQueryData(predictionKey, prediction);
      queryClient.invalidateQueries({ queryKey: studyKeys.detail(studyId!) });
    },
  });

  return {
    data: query.data,
    error: query.error,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    mutationError: mutation.error,
  };
}
