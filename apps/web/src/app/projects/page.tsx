import type { Metadata } from "next";

import ProjectsClient from "./ProjectsClient";

export const metadata: Metadata = {
  title: "Projects | divorse.ai",
  description:
    "Create and manage the matters you're researching in divorse.ai.",
};

export default function ProjectsPage() {
  return <ProjectsClient />;
}
