import type { Metadata } from "next";

import FilesClient from "./FilesClient";

export const metadata: Metadata = {
  title: "Case files | divorse.ai",
  description:
    "Upload, review, and manage the documents in your Connecticut divorce case.",
};

export default function FilesPage() {
  return <FilesClient />;
}
