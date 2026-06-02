import type { Metadata } from "next";
import Link from "next/link";

import BrandLogo from "@/components/BrandLogo";
import ProjectChip from "@/components/ProjectChip";
import UserMenu from "@/components/UserMenu";

export const metadata: Metadata = {
  title: "The Divorce Process | divorse.ai",
  description:
    "A plain-English walkthrough of the high-level steps in a Connecticut divorce, from filing through final judgment, so you know what is ahead.",
};

type Step = {
  phase: string;
  title: string;
  summary: string;
  details: string[];
};

const steps: Step[] = [
  {
    phase: "Step 1",
    title: "Start the case",
    summary:
      "One spouse files a complaint for dissolution of marriage with the Superior Court and has it served on the other spouse.",
    details: [
      "The filing spouse (the plaintiff) prepares a Summons, Complaint, and Notice of Automatic Orders.",
      "A state marshal serves the other spouse (the defendant) and the papers are then filed with the court.",
      "The papers list a return date — the official start of the court timeline, not a hearing you have to attend.",
    ],
  },
  {
    phase: "Step 2",
    title: "Automatic orders take effect",
    summary:
      "The moment the case is served, standing court orders apply to both spouses to keep things stable.",
    details: [
      "Neither spouse may sell, hide, or unusually spend marital assets, or change insurance and beneficiaries.",
      "If there are children, neither parent may remove them from the state permanently without agreement or a court order.",
      "These rules bind both sides equally and stay in place for the life of the case.",
    ],
  },
  {
    phase: "Step 3",
    title: "Exchange financial information",
    summary:
      "Both spouses complete a sworn financial affidavit and disclose income, assets, debts, and expenses.",
    details: [
      "The financial affidavit is the backbone of alimony, support, and property decisions — accuracy matters.",
      "Each side may request documents (discovery): tax returns, pay records, account statements, and more.",
      "Incomplete or inaccurate disclosure is the fastest way to lose credibility with the judge.",
    ],
  },
  {
    phase: "Step 4",
    title: "Temporary (pendente lite) orders",
    summary:
      "If you need support, a parenting schedule, or use of the home while the case is pending, you ask the court now.",
    details: [
      "Either spouse can file a motion for temporary alimony, child support, custody, or exclusive use of the residence.",
      "A short hearing lets the judge set rules that hold until the divorce is final.",
      "Connecticut weighs current need and ability to pay (see Conn. Gen. Stat. §§ 46b-82, 46b-83).",
    ],
  },
  {
    phase: "Step 5",
    title: "Parenting education (if you have children)",
    summary:
      "Parents of minor children must complete a court-approved parenting education program.",
    details: [
      "The program covers how divorce affects children and how to co-parent through the transition.",
      "It is typically required before the court will enter final orders involving the children.",
      "Disputed custody or parenting issues may also be referred to Family Services for evaluation.",
    ],
  },
  {
    phase: "Step 6",
    title: "Negotiate and try to settle",
    summary:
      "Most cases resolve by agreement. You can negotiate directly, through counsel, or with court help.",
    details: [
      "A full agreement is written into a separation agreement covering property, support, and parenting.",
      "The court offers settlement conferences and mediation through Family Services to narrow disputes.",
      "Settling gives you control over the outcome instead of leaving it to a judge.",
    ],
  },
  {
    phase: "Step 7",
    title: "Case management and pretrial",
    summary:
      "The court checks in on progress and, if issues remain, holds a pretrial conference before scheduling trial.",
    details: [
      "A case management date confirms deadlines and whether the case is agreed or contested.",
      "At a pretrial, a judge or referee reviews each side's position and may suggest a likely outcome.",
      "Connecticut requires a 90-day waiting period from the return date before a divorce can be finalized.",
    ],
  },
  {
    phase: "Step 8",
    title: "Trial (only if you cannot agree)",
    summary:
      "If disputes remain, a judge hears evidence and decides the unresolved issues.",
    details: [
      "Each side presents testimony, documents, and proposed orders on the contested issues.",
      "The judge applies the statutory factors to alimony, property division, and any parenting disputes.",
      "Trials are the exception, not the rule — but preparing as if you may have one strengthens your position.",
    ],
  },
  {
    phase: "Step 9",
    title: "Final judgment",
    summary:
      "The court enters a judgment of dissolution — by agreement or after trial — that legally ends the marriage.",
    details: [
      "The judgment sets the final terms for property, alimony, child support, and custody.",
      "Both spouses must follow these orders; they are enforceable like any court order.",
      "Keep a certified copy — you may need it to retitle assets or update accounts.",
    ],
  },
  {
    phase: "After judgment",
    title: "Modification and enforcement",
    summary:
      "Some orders can be revisited later if circumstances change, and the court can enforce orders that are ignored.",
    details: [
      "Alimony, child support, and custody can be modified on a substantial change in circumstances.",
      "If a spouse violates the orders, you can file a motion for contempt to enforce them.",
      "Property division in the final judgment is generally final and not modifiable.",
    ],
  },
];

export default function ProcessPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <div className="mx-auto flex w-full max-w-6xl flex-col px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
            <BrandLogo href="/" />
            <nav className="flex items-center gap-3 text-sm text-slate-300 sm:gap-4">
              <Link className="hidden transition hover:text-white sm:inline" href="/projects">
                Projects
              </Link>
              <Link className="hidden transition hover:text-white sm:inline" href="/files">
                Files
              </Link>
              <ProjectChip />
              <Link
                className="rounded-full bg-sky-400 px-3 py-1.5 font-semibold text-slate-950 transition hover:bg-sky-300"
                href="/chat"
              >
                Open assistant
              </Link>
              <UserMenu />
            </nav>
          </div>
        </header>

        <section className="space-y-6 py-12 sm:py-16">
          <div className="inline-flex items-center rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-sky-200">
            What lies ahead
          </div>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            The Connecticut divorce process, step by step.
          </h1>
          <p className="max-w-2xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
            A divorce moves through a predictable set of stages. Knowing the map
            ahead of time makes each step less overwhelming and helps you prepare
            for what the court will ask of you. This is the high-level path most
            Connecticut cases follow.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
              href="/chat"
            >
              Ask about your situation
            </Link>
            <Link
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/35 hover:bg-white/5"
              href="/"
            >
              Back to home
            </Link>
          </div>
        </section>

        <section aria-label="Steps in a Connecticut divorce" className="border-t border-white/10 py-10 sm:py-12">
          <ol className="space-y-5">
            {steps.map((step, index) => (
              <li key={step.title}>
                <article className="relative rounded-[1.75rem] border border-white/10 bg-white/4 p-5 sm:p-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
                    <div className="flex items-start gap-4 sm:w-56 sm:shrink-0 sm:flex-col sm:gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-sky-400/30 bg-sky-400/10 text-sm font-semibold text-sky-200">
                        {index + 1}
                      </span>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-200">
                          {step.phase}
                        </p>
                        <h2 className="mt-1 text-xl font-semibold text-white">
                          {step.title}
                        </h2>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <p className="text-base leading-7 text-slate-200">
                        {step.summary}
                      </p>
                      <ul className="space-y-2">
                        {step.details.map((detail) => (
                          <li
                            key={detail}
                            className="flex gap-3 text-sm leading-6 text-slate-300"
                          >
                            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-sky-400/70" />
                            <span>{detail}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              </li>
            ))}
          </ol>
        </section>

        <section className="rounded-[2rem] border border-amber-300/20 bg-amber-300/8 px-5 py-6 sm:px-6">
          <div className="max-w-3xl space-y-3">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-100">
              Keep in mind
            </p>
            <h2 className="text-2xl font-semibold text-white">
              Every case is different.
            </h2>
            <p className="text-sm leading-6 text-amber-50/90">
              This walkthrough is general information about the Connecticut
              process, not legal advice, and not a substitute for an attorney.
              Timelines, motions, and requirements vary with the facts of your
              case. Use divorse.ai to dig into the specific law and citations
              behind any step that affects you.
            </p>
          </div>
        </section>

        <footer className="border-t border-white/10 py-8">
          <div className="flex flex-col gap-3 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
            <p>divorse.ai</p>
            <p>CT divorce research and preparation, designed mobile first.</p>
          </div>
        </footer>
      </div>
    </main>
  );
}
