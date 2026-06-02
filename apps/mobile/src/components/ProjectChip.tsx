import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text } from "react-native";

import { useActiveProject } from "@/project/ActiveProjectContext";
import { colors, radius, spacing } from "@/theme";

// Shows the active project; tapping jumps to the Projects tab to switch.
export function ProjectChip() {
  const { activeProjectName } = useActiveProject();
  const router = useRouter();
  return (
    <Pressable
      style={styles.chip}
      onPress={() => router.navigate("/(tabs)/projects")}
    >
      <Text style={styles.label} numberOfLines={1}>
        {activeProjectName ? `📁 ${activeProjectName}` : "No project — tap to pick"}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    alignSelf: "flex-start",
    maxWidth: "100%",
  },
  label: { color: colors.text, fontSize: 13 },
});
