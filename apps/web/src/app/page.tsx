import Link from "next/link";

import BrandLogo from "@/components/BrandLogo";
import ProjectChip from "@/components/ProjectChip";
import UserMenu from "@/components/UserMenu";

const proofPoints = [
  {
    title: "Grounded in Connecticut law",
    description:
      "Every answer is built around statutes, rules, and case citations instead of generic AI guesses.",
  },
  {
    title: "Built for real divorce prep",
    description:
      "Start with alimony questions, hearings, and motion prep, then expand into the rest of a case.",
  },
  {
    title: "Made for your phone first",
    description:
      "Short, scannable sections and strong calls to action keep the experience useful on a small screen.",
  },
];

const workflow = [
  {
    eyebrow: "1. Ask the real question",
    title: "Bring the issue that is blocking you",
    description:
      "Ask about a statute, a hearing, a motion, or a fact pattern in plain English.",
  },
  {
    eyebrow: "2. Get a cited answer",
    title: "See the law behind the guidance",
    description:
      "The assistant returns a clear answer with the source material you can inspect yourself.",
  },
  {
    eyebrow: "3. Turn it into preparation",
    title: "Walk away with something usable",
    description:
      "Use a short answer, a structured memo, or annotated statute notes to prepare your next step.",
  },
];

const safeguards = [
  "Connecticut divorce only, not a general legal chatbot.",
  "Citations are part of the product, not an afterthought.",
  "Designed to support self-represented litigants without pretending to replace counsel.",
];

const faqItems = [
  {
    question: "Who is divorse.ai for?",
    answer:
      "It is aimed at self-represented people navigating a Connecticut divorce who need leverage, clarity, and grounded research support.",
  },
  {
    question: "Is this legal advice?",
    answer:
      "No. The product is designed to help users understand the law, inspect citations, and prepare better questions and arguments.",
  },
  {
    question: "What makes it different from a general chatbot?",
    answer:
      "The scope is narrow by design: Connecticut divorce law, citation-backed answers, and workflows shaped around real family-court preparation.",
  },
];

export default async function Home() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1e293b_0%,#0f172a_38%,#020617_100%)] text-slate-50">
      <div className="mx-auto flex w-full max-w-6xl flex-col px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
            <BrandLogo href="/" />
            <nav className="flex items-center gap-3 text-sm text-slate-300 sm:gap-4">
              <a className="hidden transition hover:text-white lg:inline" href="#how-it-works">
                How it works
              </a>
              <a className="hidden transition hover:text-white lg:inline" href="#faq">
                FAQ
              </a>
              <Link className="hidden transition hover:text-white sm:inline" href="/process">
                The process
              </Link>
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

        <section className="grid gap-10 py-12 sm:py-16 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:gap-12 lg:py-20">
          <div className="space-y-6">
            <div className="inline-flex items-center rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-sky-200">
              Connecticut divorce prep, grounded in real citations
            </div>
            <div className="space-y-4">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-400">
                Mobile-first frontend for divorse.ai
              </p>
              <h1 className="max-w-xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
                Understand the law before you walk into court.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
                divorse.ai is a focused research and prep assistant for
                Connecticut divorce cases. It helps self-represented litigants
                ask better questions, inspect the source law, and prepare with
                more confidence from a phone or laptop.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                className="inline-flex min-h-12 items-center justify-center rounded-full bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
                href="/chat"
              >
                Ask the assistant
              </Link>
              <a
                className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/35 hover:bg-white/5"
                href="#trust"
              >
                Review the safeguards
              </a>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {proofPoints.map((point) => (
                <article
                  key={point.title}
                  className="rounded-3xl border border-white/10 bg-white/5 p-4 shadow-[0_12px_40px_rgba(15,23,42,0.24)]"
                >
                  <h2 className="text-sm font-semibold text-white">
                    {point.title}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {point.description}
                  </p>
                </article>
              ))}
            </div>
          </div>

          <section
            id="preview"
            aria-label="Product preview"
            className="rounded-[2rem] border border-white/10 bg-white/5 p-3 shadow-[0_24px_80px_rgba(2,6,23,0.45)]"
          >
            <div className="overflow-hidden rounded-[1.6rem] border border-white/10 bg-slate-950/90">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 text-xs uppercase tracking-[0.2em] text-slate-400">
                <span>Preview</span>
                <span>Phone view</span>
              </div>
              <div className="space-y-4 p-4">
                <div className="rounded-3xl bg-slate-900 p-4 text-sm text-slate-200">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                    User asks
                  </p>
                  <p className="mt-2 leading-6">
                    What does a Connecticut judge consider for pendente lite
                    alimony, and what should I bring to the hearing?
                  </p>
                </div>

                <div className="rounded-3xl border border-sky-400/20 bg-sky-400/10 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-sky-200">
                    divorse.ai answers
                  </p>
                  <div className="mt-3 space-y-3 text-sm leading-6 text-slate-100">
                    <p>
                      Start with the statutory factors and the immediate
                      financial picture the court can verify.
                    </p>
                    <ul className="space-y-2 text-slate-200">
                      <li>
                        1. Focus on current need, ability to pay, and the case
                        posture before the final judgment.
                      </li>
                      <li>
                        2. Bring your financial affidavit, recent income
                        records, and any prior orders affecting support.
                      </li>
                      <li>
                        3. Use the cited statute and case law as a checklist for
                        what facts to highlight.
                      </li>
                    </ul>
                  </div>
                </div>

                <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                    Supporting sources
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-slate-200">
                    <p className="rounded-2xl border border-white/8 bg-slate-900/80 px-3 py-2">
                      CGS Sec. 46b-83: pendente lite alimony
                    </p>
                    <p className="rounded-2xl border border-white/8 bg-slate-900/80 px-3 py-2">
                      Practice Book Ch. 25: family matters procedure
                    </p>
                    <p className="rounded-2xl border border-white/8 bg-slate-900/80 px-3 py-2">
                      Appellate case notes interpreting temporary support
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </section>

        <section
          id="how-it-works"
          className="grid gap-4 border-t border-white/10 py-12 sm:py-16 lg:grid-cols-3"
        >
          {workflow.map((step) => (
            <article
              key={step.eyebrow}
              className="rounded-[1.75rem] border border-white/10 bg-white/4 p-5"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-200">
                {step.eyebrow}
              </p>
              <h2 className="mt-3 text-xl font-semibold text-white">
                {step.title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                {step.description}
              </p>
            </article>
          ))}
        </section>

        <section className="grid gap-4 border-t border-white/10 py-12 sm:py-16 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div className="space-y-4">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-400">
              Why this product exists
            </p>
            <h2 className="text-3xl font-semibold tracking-tight text-balance">
              Generic AI is fast. Court prep needs something safer.
            </h2>
            <p className="text-base leading-7 text-slate-300">
              The point is not to sound confident. The point is to help someone
              working through a high-stakes Connecticut divorce understand the
              governing law, verify the answer quickly, and turn it into useful
              preparation.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            {safeguards.map((item) => (
              <article
                key={item}
                className="rounded-[1.75rem] border border-white/10 bg-slate-900/70 p-5"
              >
                <p className="text-sm leading-6 text-slate-200">{item}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          id="trust"
          className="rounded-[2rem] border border-amber-300/20 bg-amber-300/8 px-5 py-6 sm:px-6"
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl space-y-3">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-100">
                Product guardrails
              </p>
              <h2 className="text-2xl font-semibold text-white">
                Built to support judgment, not replace it.
              </h2>
              <p className="text-sm leading-6 text-amber-50/90">
                divorse.ai is not legal advice, not a law firm, and not a
                substitute for counsel. The experience should make verification
                faster, not encourage blind trust.
              </p>
            </div>
            <a
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/20 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/35 hover:bg-white/5"
              href="#faq"
            >
              Read common questions
            </a>
          </div>
        </section>

        <section
          id="faq"
          className="grid gap-4 border-t border-white/10 py-12 sm:py-16 lg:grid-cols-3"
        >
          {faqItems.map((item) => (
            <article
              key={item.question}
              className="rounded-[1.75rem] border border-white/10 bg-white/4 p-5"
            >
              <h2 className="text-lg font-semibold text-white">
                {item.question}
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                {item.answer}
              </p>
            </article>
          ))}
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
