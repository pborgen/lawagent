import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useMe } from "@/api/me";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { ActiveProjectProvider } from "@/project/ActiveProjectContext";
import { colors } from "@/theme";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

// Drives navigation off auth status and syncs the /me identity into context.
function AuthGate() {
  const { status, setUser } = useAuth();
  const router = useRouter();
  const segments = useSegments();

  const me = useMe(status === "authenticated");
  useEffect(() => {
    if (me.data) setUser(me.data);
  }, [me.data, setUser]);

  useEffect(() => {
    if (status === "loading") return;
    const inAuthGroup = segments[0] === "sign-in";
    if (status === "unauthenticated" && !inAuthGroup) {
      router.replace("/sign-in");
    } else if (status === "authenticated" && inAuthGroup) {
      router.replace("/(tabs)/chat");
    }
  }, [status, segments, router]);

  if (status === "loading") {
    return (
      <View style={styles.splash}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="sign-in" />
      <Stack.Screen name="(tabs)" />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={styles.fill}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <ActiveProjectProvider>
              <StatusBar style="light" />
              <AuthGate />
            </ActiveProjectProvider>
          </AuthProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  splash: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
});
