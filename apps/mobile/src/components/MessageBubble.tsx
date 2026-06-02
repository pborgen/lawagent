import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import type { ChatTurn } from "@/api/types";
import { colors, radius, spacing } from "@/theme";

import { MarkdownAnswer } from "./MarkdownAnswer";
import { SourceList } from "./SourceList";

// One chat turn. User turns are plain text on the right; assistant turns
// render markdown + sources on the left.
export function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <View
      style={[
        styles.row,
        { justifyContent: isUser ? "flex-end" : "flex-start" },
      ]}
    >
      <View
        style={[
          styles.bubble,
          isUser ? styles.user : styles.assistant,
          isUser ? styles.userWidth : styles.assistantWidth,
        ]}
      >
        {turn.pending ? (
          <ActivityIndicator color={colors.textMuted} />
        ) : isUser ? (
          <Text style={styles.userText}>{turn.text}</Text>
        ) : turn.error ? (
          <Text style={styles.errorText}>{turn.text}</Text>
        ) : (
          <>
            <MarkdownAnswer text={turn.text} />
            {turn.sources ? <SourceList sources={turn.sources} /> : null}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", marginVertical: spacing.xs },
  bubble: {
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  user: { backgroundColor: colors.userBubble },
  assistant: {
    backgroundColor: colors.assistantBubble,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  userWidth: { maxWidth: "85%" },
  assistantWidth: { maxWidth: "92%" },
  userText: { color: colors.text, fontSize: 15 },
  errorText: { color: colors.danger, fontSize: 14 },
});
