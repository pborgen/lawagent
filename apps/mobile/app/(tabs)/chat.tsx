import { useCallback, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useChat } from "@/api/chat";
import type { ChatTurn, Mode } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { MessageBubble } from "@/components/MessageBubble";
import { ModeSelector } from "@/components/ModeSelector";
import { ProjectChip } from "@/components/ProjectChip";
import { Screen } from "@/components/Screen";
import { useActiveProject } from "@/project/ActiveProjectContext";
import { colors, spacing } from "@/theme";

// Stable-ish ids without pulling in a uuid dep: a monotonic counter.
let turnCounterSeed = 0;
function nextId(): string {
  turnCounterSeed += 1;
  return `turn-${turnCounterSeed}`;
}

export default function ChatScreen() {
  const [mode, setMode] = useState<Mode>("short");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const listRef = useRef<FlatList<ChatTurn>>(null);

  const { signOut } = useAuth();
  const { activeProjectId } = useActiveProject();
  const chat = useChat();

  const send = useCallback(() => {
    const question = input.trim();
    if (!question || chat.isPending) return;
    if (question.length > 4000) return;

    const userTurn: ChatTurn = {
      id: nextId(),
      role: "user",
      text: question,
    };
    const pendingId = nextId();
    const pendingTurn: ChatTurn = {
      id: pendingId,
      role: "assistant",
      text: "",
      pending: true,
    };
    // Newest first (inverted list).
    setTurns((prev) => [pendingTurn, userTurn, ...prev]);
    setInput("");

    chat.mutate(
      { question, mode, projectId: activeProjectId ?? undefined },
      {
        onSuccess: (data) => {
          setTurns((prev) =>
            prev.map((t) =>
              t.id === pendingId
                ? {
                    ...t,
                    pending: false,
                    text: data.answer,
                    mode: data.mode,
                    sources: data.sources,
                  }
                : t,
            ),
          );
        },
        onError: (err) => {
          setTurns((prev) =>
            prev.map((t) =>
              t.id === pendingId
                ? {
                    ...t,
                    pending: false,
                    error: true,
                    text:
                      err instanceof Error
                        ? err.message
                        : "The assistant failed to answer.",
                  }
                : t,
            ),
          );
        },
      },
    );
  }, [input, chat, mode, activeProjectId]);

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <Text style={styles.title}>Chat</Text>
          <Pressable onPress={() => void signOut()} hitSlop={8}>
            <Text style={styles.signOut}>Sign out</Text>
          </Pressable>
        </View>
        <ProjectChip />
        <ModeSelector value={mode} onChange={setMode} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 88 : 0}
      >
        {turns.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>
              Ask a question about Connecticut divorce law or your case.
            </Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={turns}
            inverted
            keyExtractor={(t) => t.id}
            renderItem={({ item }) => <MessageBubble turn={item} />}
            contentContainerStyle={styles.list}
            keyboardShouldPersistTaps="handled"
          />
        )}

        <View style={styles.composer}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ask a question…"
            placeholderTextColor={colors.textMuted}
            multiline
            maxLength={4000}
          />
          <Pressable
            onPress={send}
            disabled={!input.trim() || chat.isPending}
            style={[
              styles.sendBtn,
              (!input.trim() || chat.isPending) && styles.sendBtnDisabled,
            ]}
          >
            <Text style={styles.sendText}>Send</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: { color: colors.text, fontSize: 22, fontWeight: "700" },
  signOut: { color: colors.textMuted, fontSize: 14 },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  emptyText: { color: colors.textMuted, textAlign: "center", fontSize: 15 },
  list: { padding: spacing.lg },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  input: {
    flex: 1,
    color: colors.text,
    backgroundColor: colors.surfaceAlt,
    borderRadius: 18,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    maxHeight: 140,
    fontSize: 15,
  },
  sendBtn: {
    backgroundColor: colors.primary,
    borderRadius: 18,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sendBtnDisabled: { opacity: 0.5 },
  sendText: { color: colors.primaryText, fontWeight: "600" },
});
