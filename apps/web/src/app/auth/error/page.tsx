import Link from "next/link";

import BrandLogo from "@/components/BrandLogo";

const MESSAGES: Record<string, string> = {
  session_expired: "Your sign-in took too long or the window was reopened. Please try again.",
  token_exchange_failed: "We could not complete sign-in with Google. Please try again.",
  no_email_claim: "Google did not return a verified email. Try a different account.",
  not_authorized: "That Google account isn't on the allowlist for this app.",
};

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const { reason } = await searchParams;
  const message = (reason && MESSAGES[reason]) || "Sign-in failed. Please try again.";

  return (
    <main className="flex min-h-screen flex-col bg-slate-950 text-slate-50">
      <header className="border-b border-white/10 px-4 py-3 sm:px-6 lg:px-8">
        <BrandLogo href="/" />
      </header>
      <section className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-4 py-12">
        <h1 className="text-2xl font-semibold">Couldn&apos;t sign you in</h1>
        <p className="text-slate-300">{message}</p>
        <Link
          href="/auth/signin"
          className="inline-flex w-fit items-center rounded-full bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
        >
          Try again
        </Link>
      </section>
    </main>
  );
}
