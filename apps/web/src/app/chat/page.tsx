import type { Metadata } from "next";

import ChatClient from "./ChatClient";

export const metadata: Metadata = {
  title: "Ask divorse.ai | Connecticut Divorce Prep",
  description:
    "Ask grounded, citation-backed questions about Connecticut divorce law.",
};

export default function ChatPage() {
  return <ChatClient />;
}
