import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "@/theme";

// Thin progress bar shown while a file uploads to S3.
export function UploadProgress({
  filename,
  fraction,
}: {
  filename: string;
  fraction: number;
}) {
  const pct = Math.round(fraction * 100);
  return (
    <View style={styles.wrap}>
      <Text style={styles.name} numberOfLines={1}>
        Uploading {filename}… {pct}%
      </Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  name: { color: colors.textMuted, fontSize: 13 },
  track: {
    height: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    overflow: "hidden",
  },
  fill: { height: 6, backgroundColor: colors.primary },
});
