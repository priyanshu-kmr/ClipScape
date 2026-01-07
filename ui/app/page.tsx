"use client";

import { useEffect, useMemo, useState } from "react";

type FileKind = "text" | "file" | "image";
type ConnectionState = "idle" | "connecting" | "connected" | "error" | "disconnected";

const statusColors: Record<ConnectionState, string> = {
  connected: "bg-emerald-400 shadow-[0_0_0_6px_rgba(16,185,129,0.15)]",
  connecting: "bg-amber-300 shadow-[0_0_0_6px_rgba(251,191,36,0.15)] animate-pulse",
  idle: "bg-slate-500 shadow-[0_0_0_6px_rgba(100,116,139,0.15)]",
  disconnected: "bg-slate-600 shadow-[0_0_0_6px_rgba(71,85,105,0.15)]",
  error: "bg-rose-400 shadow-[0_0_0_6px_rgba(244,63,94,0.18)]",
};

type CardData = {
  type: FileKind;
  title: string;
  description: string;
  wordCount?: number;
  file: {
    name: string;
    path: string;
    size: string;
    createdAt: string;
    mime: string;
  };
  image?: {
    resolution: string;
    aspectRatio: string;
    colorProfile?: string;
  };
};

const demoCard: CardData = {
  type: "file",
  title: "Explainer Deck.pdf",
  description: "Pinned from your Clips. Includes storyboard text plus a high-res cover render.",
  wordCount: 2450,
  file: {
    name: "Explainer Deck.pdf",
    path: "C:\\Users\\csp\\Documents\\Decks\\Explainer Deck.pdf",
    size: "4.7 MB",
    createdAt: "2025-12-03 09:41",
    mime: "application/pdf",
  },
  image: {
    resolution: "3840 x 2160 px",
    aspectRatio: "16:9",
    colorProfile: "Display P3",
  },
};

const formatMeta = (card: CardData) => {
  const entries: { label: string; value: string }[] = [
    { label: "Name", value: card.file.name },
    { label: "Location", value: card.file.path },
    { label: "Size", value: card.file.size },
    { label: "Created", value: card.file.createdAt },
    { label: "MIME", value: card.file.mime },
  ];

  if (card.type === "text" && card.wordCount) {
    entries.unshift({ label: "Words", value: `${card.wordCount.toLocaleString()} words` });
  }

  if (card.image) {
    entries.push({ label: "Resolution", value: card.image.resolution });
    entries.push({ label: "Aspect", value: card.image.aspectRatio });
    if (card.image.colorProfile) {
      entries.push({ label: "Profile", value: card.image.colorProfile });
    }
  }

  return entries;
};

export default function Home() {
  const [connection, setConnection] = useState<ConnectionState>("idle");

  const indicatorClass = useMemo(() => statusColors[connection], [connection]);

  const connect = async () => {
    try {
      setConnection("connecting");
      const res = await fetch("/api/redis/connect", { method: "POST" });
      if (!res.ok) throw new Error("connect failed");
      setConnection("connected");
    } catch (err) {
      console.error(err);
      setConnection("error");
    }
  };

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await fetch("/api/redis/status");
        const data = (await res.json()) as { status: string; ok: boolean };

        if (!active) return;

        if (data.status === "connected" || data.status === "ready") {
          setConnection("connected");
          return;
        }

        if (data.status === "connecting") {
          setConnection("connecting");
          return;
        }

        if (!data.ok) {
          setConnection(connection === "connected" ? "disconnected" : "error");
          return;
        }

        setConnection("idle");
      } catch (error) {
        console.error("status poll error", error);
        if (!active) return;
        setConnection("error");
      }
    };

    poll();
    const id = setInterval(poll, 6000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [connection]);

  const meta = formatMeta(demoCard);

  return (
    <div className="min-h-screen bg-[#0c0f14] text-slate-100">
      <div className="relative isolate flex min-h-screen items-center justify-center px-6 py-16">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,rgba(80,126,255,0.2),transparent_35%),radial-gradient(circle_at_80%_0%,rgba(111,220,255,0.14),transparent_28%),radial-gradient(circle_at_90%_70%,rgba(255,126,95,0.16),transparent_30%)]" />

        <div className="w-full max-w-3xl">
          <div className="mb-6 flex items-center justify-between text-sm text-slate-400">
            <span className="tracking-wide">Pinned Clip</span>
            <div className="flex items-center gap-3">
              <button
                onClick={connect}
                className="relative inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-50 shadow-[0_12px_40px_-22px_rgba(0,0,0,0.9)] transition hover:border-white/30 hover:bg-white/10 hover:shadow-[0_15px_55px_-20px_rgba(0,0,0,0.85)] focus:outline-none focus:ring-2 focus:ring-cyan-400/70"
              >
                <span className="relative flex h-3 w-3 items-center justify-center">
                  <span className={`absolute inset-0 rounded-full blur-[1.5px] ${indicatorClass}`} />
                  <span className={`relative h-3 w-3 rounded-full ${indicatorClass}`} />
                </span>
                <span className="tracking-wide">Redis Link</span>
              </button>
              <span className="rounded-full bg-white/5 px-3 py-1 font-medium text-slate-200 shadow-sm">Hover to reveal metadata</span>
            </div>
          </div>

          <article className="group relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#161a22] via-[#10131a] to-[#0c0f14] shadow-[0_20px_80px_-35px_rgba(0,0,0,0.65)] transition-transform duration-400 ease-out hover:-translate-y-1 hover:shadow-[0_25px_90px_-30px_rgba(0,0,0,0.75)]">
            <div className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100" aria-hidden>
              <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(111,220,255,0.08),rgba(111,220,255,0.02)_35%,rgba(255,126,95,0.08))]" />
            </div>

            <div className="relative z-10 flex flex-col gap-4 p-8">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-200">
                {demoCard.type === "image" && "Image"}
                {demoCard.type === "file" && "File"}
                {demoCard.type === "text" && "Text"}
                <span className="h-1 w-1 rounded-full bg-emerald-400/70" />
                Synced
              </div>

              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <h1 className="text-3xl font-semibold tracking-tight text-slate-50">{demoCard.title}</h1>
                  <p className="max-w-2xl text-base leading-relaxed text-slate-300">{demoCard.description}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-right text-xs text-slate-200 shadow-inner">
                  <div className="font-semibold text-slate-50">Quick Glance</div>
                  <div className="text-slate-300">{demoCard.file.size}</div>
                  {demoCard.image ? (
                    <div className="text-slate-400">{demoCard.image.resolution}</div>
                  ) : demoCard.wordCount ? (
                    <div className="text-slate-400">{demoCard.wordCount.toLocaleString()} words</div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(20,24,32,0.7),rgba(12,15,20,0.94))] backdrop-blur-lg transition-[max-height,opacity,transform] duration-500 ease-out max-h-0 opacity-0 -translate-y-2 group-hover:max-h-[360px] group-hover:opacity-100 group-hover:translate-y-0">
              <div className="relative h-full overflow-y-auto px-8 py-6">
                <div className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Metadata</div>
                <div className="grid grid-cols-1 gap-3 text-sm text-slate-200 sm:grid-cols-2">
                  {meta.map((item) => (
                    <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 shadow-sm">
                      <div className="text-[11px] uppercase tracking-[0.08em] text-slate-400">{item.label}</div>
                      <div className="mt-1 font-medium text-slate-50">{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  );
}
