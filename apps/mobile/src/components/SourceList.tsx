import * as WebBrowser from "expo-web-browser";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Source } from "@/api/types";
import { colors, radius, spacing } from "@/theme";

// The grounded sources behind an answer. Tapping one with a URL opens it so
// the litigant can verify the cite — the whole point of the product.
export function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <View style={styles.wrap}>
      <Text style={styles.heading}>Sources</Text>
      {sources.map((s, i) => {
        const hasUrl = !!s.url;
        const body = (
          <View style={styles.row}>
            <Text style={styles.badge}>{s.source_type || "source"}</Text>
            <Text style={[styles.citation, hasUrl && styles.link]}>
              {s.citation}
            </Text>
          </View>
        );
        return hasUrl ? (
          <Pressable
            key={`${s.citation}-${i}`}
            onPress={() => void WebBrowser.openBrowserAsync(s.url)}
          >
            {body}
          </Pressable>
        ) : (
          <View key={`${s.citation}-${i}`}>{body}</View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    gap: spacing.xs,
  },
  heading: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    marginBottom: spacing.xs,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  badge: {
    color: colors.textMuted,
    fontSize: 11,
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    overflow: "hidden",
  },
  citation: { color: colors.text, fontSize: 13, flexShrink: 1 },
  link: { color: colors.link, textDecorationLine: "underline" },
});
