import Link from "next/link";

import { getAuthConfig } from "@/lib/auth/config";
import { getCurrentEmail, getCurrentUser } from "@/lib/auth/dal";

/**
 * Header strip showing the signed-in email and a sign-out form. Server
 * component — reads the cookie directly via the DAL.
 *
 * When AUTH_DISABLED is set, we render a small badge so it's obvious
 * the gate is off (and easy to spot if it ever leaks into prod logs).
 */
export default async function UserMenu() {
  const email = await getCurrentEmail();
  const disabled = getAuthConfig().authDisabled;

  if (!email) {
    return (
      <a
        href="/auth/signin"
        className="text-sm font-medium text-slate-300 transition hover:text-white"
      >
        Sign in
      </a>
    );
  }

  // Admin link is gated on the backend's is_admin flag. A null result
  // (backend unreachable, or not an admin) simply hides the link.
  const user = await getCurrentUser();

  return (
    <div className="flex items-center gap-3 text-sm">
      {disabled ? (
        <span className="rounded-full bg-amber-400/15 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-amber-200">
          auth off
        </span>
      ) : null}
      {user?.isAdmin ? (
        <Link
          href="/admin"
          className="hidden font-medium text-slate-300 transition hover:text-white sm:inline"
        >
          Admin
        </Link>
      ) : null}
      <span className="hidden text-slate-400 sm:inline">{email}</span>
      {disabled ? null : (
        <form action="/auth/signout" method="post">
          <button
            type="submit"
            className="rounded-full border border-white/15 px-3 py-1 font-medium text-slate-200 transition hover:border-white/35 hover:bg-white/5"
          >
            Sign out
          </button>
        </form>
      )}
    </div>
  );
}
