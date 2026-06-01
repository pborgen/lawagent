import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getCurrentUser } from "@/lib/auth/dal";

import AdminClient from "./AdminClient";

export const metadata: Metadata = {
  title: "Admin · Usage | divorse.ai",
  description: "LLM usage and cost across users.",
};

export default async function AdminPage() {
  // Server-side guard: non-admins (and unauthenticated callers) get a 404
  // so the route's existence never leaks. The backend independently 403s
  // the data endpoint, so this is defense in depth, not the only gate.
  const user = await getCurrentUser();
  if (!user?.isAdmin) {
    notFound();
  }
  return <AdminClient />;
}
