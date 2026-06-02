import * as WebBrowser from "expo-web-browser";
import { useMemo } from "react";
import Markdown from "react-native-markdown-display";

import { colors, spacing } from "@/theme";

// Renders the agent's markdown answer. Links (including the inline citation
// links the API embeds) open in the in-app browser — the "checkable
// citations" value prop.
export function MarkdownAnswer({ text }: { text: string }) {
  const styles = useMemo(
    () => ({
      body: { color: colors.text, fontSize: 15, lineHeight: 22 },
      link: { color: colors.link, textDecorationLine: "underline" as const },
      heading1: { color: colors.text, fontSize: 20, marginTop: spacing.sm },
      heading2: { color: colors.text, fontSize: 18, marginTop: spacing.sm },
      heading3: { color: colors.text, fontSize: 16, marginTop: spacing.sm },
      bullet_list: { color: colors.text },
      ordered_list: { color: colors.text },
      code_inline: {
        color: colors.text,
        backgroundColor: colors.surfaceAlt,
      },
      blockquote: {
        backgroundColor: colors.surfaceAlt,
        borderColor: colors.border,
      },
    }),
    [],
  );

  return (
    <Markdown
      style={styles}
      onLinkPress={(url) => {
        void WebBrowser.openBrowserAsync(url);
        return false;
      }}
    >
      {text}
    </Markdown>
  );
}
