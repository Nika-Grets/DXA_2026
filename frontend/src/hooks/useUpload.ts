import { useState } from 'react';
import {
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { uploadStudy } from '../api/studies';
import {
  savePendingFile,
  promotePendingFile,
} from '../utils/fileCache';
import { studyKeys } from './useStudy';
import type { components } from '../api/schema';


type UploadResponse =
  components['schemas']['UploadResponse'];

export function useUpload() {
  const [progress, setProgress] = useState(0);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async ({
      file,
    }: {
      file: File;
    }) => {
      setProgress(0);

      await savePendingFile(file);

      const result = await uploadStudy(
        file,
        (p) => setProgress(p)
      );

      await promotePendingFile(
        result.study_id
      );

      return result;
    },

    onSuccess: (data: UploadResponse) => {
      queryClient.setQueryData(
        studyKeys.detail(data.study_id),
        data
      );

      navigate(
        `/study/${data.study_id}`
      );
    },
  });

  return {
    ...mutation,
    progress,
    upload: mutation.mutate,
    isUploading:
      mutation.isPending,
    uploadError:
      mutation.error,
  };
}