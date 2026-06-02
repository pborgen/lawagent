import * as DocumentPicker from "expo-document-picker";
import { useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  convertFile,
  deleteFile,
  downloadFile,
  filesKey,
  uploadFile,
  useFiles,
} from "@/api/files";
import type { FileItem } from "@/api/types";
import { Button } from "@/components/Button";
import { Screen } from "@/components/Screen";
import { UploadProgress } from "@/components/UploadProgress";
import { useActiveProject } from "@/project/ActiveProjectContext";
import { colors, radius, spacing } from "@/theme";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FilesScreen() {
  const { activeProjectId } = useActiveProject();
  const router = useRouter();
  const qc = useQueryClient();
  const files = useFiles(activeProjectId);

  const [upload, setUpload] = useState<{ name: string; fraction: number } | null>(
    null,
  );
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const refresh = () => {
    if (activeProjectId) {
      qc.invalidateQueries({ queryKey: filesKey(activeProjectId) });
    }
  };

  const pickAndUpload = async () => {
    if (!activeProjectId) return;
    const res = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true });
    if (res.canceled || !res.assets?.length) return;
    const asset = res.assets[0];
    setUpload({ name: asset.name, fraction: 0 });
    try {
      await uploadFile({
        projectId: activeProjectId,
        fileUri: asset.uri,
        filename: asset.name,
        contentType: asset.mimeType ?? undefined,
        onProgress: (f) => setUpload({ name: asset.name, fraction: f }),
      });
      refresh();
    } catch (e) {
      Alert.alert("Upload failed", String(e instanceof Error ? e.message : e));
    } finally {
      setUpload(null);
    }
  };

  const onDownload = async (item: FileItem) => {
    if (!activeProjectId) return;
    setBusyKey(item.key);
    try {
      await downloadFile({ projectId: activeProjectId, item });
    } catch (e) {
      Alert.alert("Download failed", String(e instanceof Error ? e.message : e));
    } finally {
      setBusyKey(null);
    }
  };

  const onConvert = async (item: FileItem) => {
    if (!activeProjectId) return;
    setBusyKey(item.key);
    try {
      const result = await convertFile({ projectId: activeProjectId, key: item.key });
      refresh();
      if (result.scanned) {
        Alert.alert(
          "Converted (scanned PDF)",
          "This PDF had no text layer, so the Word file contains page images, not editable text.",
        );
      }
    } catch (e) {
      Alert.alert("Convert failed", String(e instanceof Error ? e.message : e));
    } finally {
      setBusyKey(null);
    }
  };

  const onDelete = (item: FileItem) => {
    if (!activeProjectId) return;
    Alert.alert("Delete file?", item.name, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteFile({ projectId: activeProjectId, key: item.key });
            refresh();
          } catch (e) {
            Alert.alert("Delete failed", String(e instanceof Error ? e.message : e));
          }
        },
      },
    ]);
  };

  if (!activeProjectId) {
    return (
      <Screen>
        <View style={styles.header}>
          <Text style={styles.title}>Files</Text>
        </View>
        <View style={styles.empty}>
          <Text style={styles.emptyText}>
            Pick a project first to see and upload its files.
          </Text>
          <Button
            title="Go to Projects"
            onPress={() => router.navigate("/(tabs)/projects")}
            style={styles.emptyBtn}
          />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>Files</Text>
        <Pressable onPress={() => void pickAndUpload()} hitSlop={8} disabled={!!upload}>
          <Text style={[styles.add, upload && styles.disabled]}>+ Upload</Text>
        </Pressable>
      </View>

      {upload ? (
        <UploadProgress filename={upload.name} fraction={upload.fraction} />
      ) : null}

      <FlatList
        data={files.data?.items ?? []}
        keyExtractor={(f) => f.key}
        contentContainerStyle={styles.list}
        refreshing={files.isFetching}
        onRefresh={() => files.refetch()}
        ListEmptyComponent={
          files.isLoading ? null : (
            <Text style={styles.emptyText}>No files yet. Tap Upload to add one.</Text>
          )
        }
        renderItem={({ item }) => {
          const busy = busyKey === item.key;
          const isPdf = item.name.toLowerCase().endsWith(".pdf");
          return (
            <View style={styles.card}>
              <Text style={styles.fileName}>{item.name}</Text>
              <Text style={styles.fileMeta}>
                {formatSize(item.size)} ·{" "}
                {new Date(item.last_modified).toLocaleDateString()}
              </Text>
              <View style={styles.actions}>
                <Pressable onPress={() => void onDownload(item)} disabled={busy}>
                  <Text style={styles.action}>Download</Text>
                </Pressable>
                {isPdf ? (
                  <Pressable onPress={() => void onConvert(item)} disabled={busy}>
                    <Text style={styles.action}>→ Word</Text>
                  </Pressable>
                ) : null}
                <Pressable onPress={() => onDelete(item)} disabled={busy}>
                  <Text style={[styles.action, styles.delete]}>Delete</Text>
                </Pressable>
              </View>
            </View>
          );
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: { color: colors.text, fontSize: 22, fontWeight: "700" },
  add: { color: colors.primary, fontSize: 16, fontWeight: "600" },
  disabled: { opacity: 0.5 },
  list: { padding: spacing.lg, gap: spacing.sm },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.md },
  emptyText: { color: colors.textMuted, textAlign: "center", fontSize: 15 },
  emptyBtn: { minWidth: 180 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  fileName: { color: colors.text, fontSize: 15, fontWeight: "500" },
  fileMeta: { color: colors.textMuted, fontSize: 12 },
  actions: { flexDirection: "row", gap: spacing.lg, marginTop: spacing.xs },
  action: { color: colors.link, fontSize: 14, fontWeight: "600" },
  delete: { color: colors.danger },
});
