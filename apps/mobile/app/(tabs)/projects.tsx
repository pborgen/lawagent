import { useRouter } from "expo-router";
import { useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  useCreateProject,
  useDeleteProject,
  useProjects,
} from "@/api/projects";
import type { Project } from "@/api/types";
import { Button } from "@/components/Button";
import { Screen } from "@/components/Screen";
import { useActiveProject } from "@/project/ActiveProjectContext";
import { colors, radius, spacing } from "@/theme";

export default function ProjectsScreen() {
  const projects = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const { activeProjectId, setActiveProject } = useActiveProject();
  const router = useRouter();

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const pick = (p: Project) => {
    setActiveProject(p.id, p.name);
    router.navigate("/(tabs)/chat");
  };

  const confirmDelete = (p: Project) => {
    Alert.alert("Delete project?", `"${p.name}" will be removed.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          deleteProject.mutate(p.id, {
            onSuccess: () => {
              if (activeProjectId === p.id) setActiveProject(null);
            },
          });
        },
      },
    ]);
  };

  const submitCreate = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    createProject.mutate(
      { name: trimmed, description: description.trim() || undefined },
      {
        onSuccess: (p) => {
          setActiveProject(p.id, p.name);
          setShowCreate(false);
          setName("");
          setDescription("");
        },
        onError: (e) =>
          Alert.alert("Could not create project", String(e instanceof Error ? e.message : e)),
      },
    );
  };

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>Projects</Text>
        <Pressable onPress={() => setShowCreate(true)} hitSlop={8}>
          <Text style={styles.add}>+ New</Text>
        </Pressable>
      </View>

      <FlatList
        data={projects.data ?? []}
        keyExtractor={(p) => p.id}
        contentContainerStyle={styles.list}
        refreshing={projects.isFetching}
        onRefresh={() => projects.refetch()}
        ListEmptyComponent={
          projects.isLoading ? null : (
            <Text style={styles.empty}>
              No projects yet. Create one to organize your case files.
            </Text>
          )
        }
        renderItem={({ item }) => {
          const active = item.id === activeProjectId;
          return (
            <Pressable
              style={[styles.card, active && styles.cardActive]}
              onPress={() => pick(item)}
              onLongPress={() => confirmDelete(item)}
            >
              <View style={styles.cardRow}>
                <Text style={styles.cardName}>{item.name}</Text>
                {active ? <Text style={styles.activeTag}>active</Text> : null}
              </View>
              {item.matter_type ? (
                <Text style={styles.cardMeta}>{item.matter_type}</Text>
              ) : null}
              {item.description ? (
                <Text style={styles.cardDesc} numberOfLines={2}>
                  {item.description}
                </Text>
              ) : null}
            </Pressable>
          );
        }}
      />

      <Modal
        visible={showCreate}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCreate(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>New project</Text>
            <TextInput
              style={styles.input}
              placeholder="Name (e.g. Smith v. Smith)"
              placeholderTextColor={colors.textMuted}
              value={name}
              onChangeText={setName}
              maxLength={200}
            />
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="Description (optional)"
              placeholderTextColor={colors.textMuted}
              value={description}
              onChangeText={setDescription}
              multiline
              maxLength={2000}
            />
            <View style={styles.modalActions}>
              <Button
                title="Cancel"
                variant="secondary"
                onPress={() => setShowCreate(false)}
                style={styles.flex1}
              />
              <Button
                title="Create"
                onPress={submitCreate}
                loading={createProject.isPending}
                disabled={!name.trim()}
                style={styles.flex1}
              />
            </View>
          </View>
        </View>
      </Modal>
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
  list: { padding: spacing.lg, gap: spacing.sm },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing.xl },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  cardActive: { borderColor: colors.primary },
  cardRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardName: { color: colors.text, fontSize: 16, fontWeight: "600", flexShrink: 1 },
  activeTag: { color: colors.primary, fontSize: 12, fontWeight: "600" },
  cardMeta: { color: colors.textMuted, fontSize: 13 },
  cardDesc: { color: colors.textMuted, fontSize: 13 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  modalTitle: { color: colors.text, fontSize: 18, fontWeight: "700" },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    color: colors.text,
    fontSize: 15,
  },
  inputMultiline: { minHeight: 70, textAlignVertical: "top" },
  modalActions: { flexDirection: "row", gap: spacing.sm },
  flex1: { flex: 1 },
});
