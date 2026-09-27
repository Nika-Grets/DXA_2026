import { useMutation, useQueryClient } from '@tanstack/react-query';
import { generateReport, saveReportToFile } from '../api/studies';
import { studyKeys } from './useStudy';

interface UseReportOptions {
  studyId: string | undefined;
  hasReport: boolean;
}

export function useReport({
  studyId,
  hasReport,
}: UseReportOptions) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async () => {
      if (!studyId) {
        throw new Error('studyId is required');
      }

      if (!hasReport) {
        await generateReport(studyId);
      }
      await saveReportToFile(
        studyId,
        `study-${studyId}.pdf`
      );
    },

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: studyKeys.detail(studyId!),
      });
    },
  });

  return {
    ...mutation,
    generateAndDownload: mutation.mutate,
    isGenerating: mutation.isPending,
    reportError: mutation.error,
  };
}