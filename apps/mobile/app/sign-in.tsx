import { StyleSheet, Text, View } from "react-native";

import { Button } from "@/components/Button";
import { Screen } from "@/components/Screen";
import { config } from "@/config";
import { useAuth } from "@/auth/AuthContext";
import { colors, spacing } from "@/theme";

export default function SignIn() {
  const { signIn, status, error } = useAuth();
  const busy = status === "loading";

  return (
    <Screen style={styles.screen}>
      <View style={styles.center}>
        <Text style={styles.title}>Lawagent</Text>
        <Text style={styles.subtitle}>
          Grounded answers for your Connecticut divorce — with citations you can
          check.
        </Text>

        <Button
          title={config.authDisabled ? "Continue (dev)" : "Continue with Google"}
          onPress={() => void signIn()}
          loading={busy}
          style={styles.button}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.disclaimer}>Not legal advice.</Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.xl },
  center: { flex: 1, justifyContent: "center", gap: spacing.md },
  title: { color: colors.text, fontSize: 34, fontWeight: "700" },
  subtitle: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  button: { marginTop: spacing.sm },
  error: { color: colors.danger, fontSize: 14, marginTop: spacing.sm },
  disclaimer: {
    color: colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    marginTop: spacing.xl,
  },
});
