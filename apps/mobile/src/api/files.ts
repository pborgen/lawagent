import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type {
  CaseFileList,
  ConvertResult,
  FileItem,
  PresignDownload,
  PresignUpload,
} from "./types";

export function filesKey(projectId: string) {
  return ["files", projectId];
}

export function useFiles(projectId: string | null) {
  return useQuery({
    queryKey: filesKey(projectId ?? "none"),
    enabled: !!projectId,
    queryFn: () =>
      apiFetch<CaseFileList>("/files", { query: { project_id: projectId! } }),
  });
}

// Upload via presigned PUT straight to S3. We use expo-file-system's
// uploadAsync (not fetch) because it exposes upload progress, which fetch/XHR
// can't in React Native.
export async function uploadFile(args: {
  projectId: string;
  fileUri: string;
  filename: string;
  contentType?: string;
  onProgress?: (fraction: number) => void;
}): Promise<void> {
  const presign = await apiFetch<PresignUpload>("/files/presign-upload", {
    method: "POST",
    body: {
      project_id: args.projectId,
      filename: args.filename,
      content_type: args.contentType ?? "application/octet-stream",
    },
  });

  const task = FileSystem.createUploadTask(
    presign.url,
    args.fileUri,
    {
      httpMethod: "PUT",
      uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
      headers: presign.headers,
    },
    (p) => {
      if (p.totalBytesExpectedToSend > 0) {
        args.onProgress?.(
          p.totalBytesSent / p.totalBytesExpectedToSend,
        );
      }
    },
  );

  const result = await task.uploadAsync();
  if (!result || result.status < 200 || result.status >= 300) {
    throw new Error(`S3 upload failed (${result?.status ?? "no response"})`);
  }
}

// Download via presigned GET, then hand the local file to the iOS share sheet.
export async function downloadFile(args: {
  projectId: string;
  item: FileItem;
}): Promise<void> {
  const presign = await apiFetch<PresignDownload>("/files/presign-download", {
    query: { project_id: args.projectId, key: args.item.key },
  });

  const safeName = args.item.name.replace(/[/\\]/g, "_");
  const localUri = FileSystem.cacheDirectory + safeName;
  const { uri } = await FileSystem.downloadAsync(presign.url, localUri);

  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(uri);
  }
}

export async function deleteFile(args: {
  projectId: string;
  key: string;
}): Promise<void> {
  await apiFetch<{ status: string }>("/files", {
    method: "DELETE",
    query: { project_id: args.projectId, key: args.key },
  });
}

export async function convertFile(args: {
  projectId: string;
  key: string;
}): Promise<ConvertResult> {
  return apiFetch<ConvertResult>("/files/convert", {
    method: "POST",
    body: { project_id: args.projectId, key: args.key },
  });
}
