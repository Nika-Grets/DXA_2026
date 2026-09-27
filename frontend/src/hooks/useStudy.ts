import { useQuery} from '@tanstack/react-query';
import { getStudy } from '../api/studies';
import type { components} from '../api/schema';

type StudySummary = components['schemas']['StudySummary'];
type StudyStatus = components['schemas']['StudyStatus'];
// Ключи кэша — централизованно, чтобы не дублировать в разных местах
export const studyKeys = {
  all: ['study'] as const,
  detail: (studyId: string) => ['study', studyId] as const,
};

// Какие статусы требуют поллинга
const POLLING_STATUSES: StudyStatus[] = ['uploaded', 'parsed', 'predicting'];

interface UseStudyOptions {
  enabled?: boolean;
  refetchInterval?: number | false;
}

export function useStudy(
  studyId: string | undefined,
  options: UseStudyOptions = {}
): {
  study: StudySummary | undefined;
  isLoading: boolean;
  error: Error | null;
  isFetching: boolean;
} {
  const result = useQuery({
    queryKey: studyId ? studyKeys.detail(studyId) : ['study', 'none'],
    queryFn: async () => {
      if (!studyId) throw new Error('studyId is required');
      return getStudy(studyId);
    },
    enabled: Boolean(studyId) && (options.enabled ?? true),
    refetchInterval: (query) => {
      if (options.refetchInterval !== undefined) {
        return options.refetchInterval;
      }
      const status = query.state.data?.status;
      if (!status) return 2000;
      return POLLING_STATUSES.includes(status) ? 2000 : false;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return {
    study: result.data,
    isLoading: result.isLoading,
    error: result.error,
    isFetching: result.isFetching,
  };
}