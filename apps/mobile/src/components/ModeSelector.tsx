import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Mode } from "@/api/types";
import { colors, radius, spacing } from "@/theme";

const MODES: { value: Mode; label: string }[] = [
  { value: "short", label: "Short" },
  { value: "memo", label: "Memo" },
  { value: "annotate", label: "Annotate" },
];

// Segmented control for the answer mode (short | memo | annotate).
export function ModeSelector({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <View style={styles.wrap}>
      {MODES.map((m) => {
        const active = m.value === value;
        return (
          <Pressable
            key={m.value}
            onPress={() => onChange(m.value)}
            style={[styles.seg, active && styles.segActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>
              {m.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: 2,
  },
  seg: {
    flex: 1,
    paddingVertical: spacing.xs,
    alignItems: "center",
    borderRadius: radius.sm,
  },
  segActive: { backgroundColor: colors.primary },
  label: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  labelActive: { color: colors.primaryText },
});
