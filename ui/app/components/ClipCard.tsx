import React from "react";

export type FileKind = "text" | "file" | "image";

export type CardData = {
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

export function ClipCard({ card }: { card: CardData }) {
  const meta = formatMeta(card);

  return (
    <article className="group relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#161a22] via-[#10131a] to-[#0c0f14] shadow-[0_20px_80px_-35px_rgba(0,0,0,0.65)] transition-transform duration-400 ease-out hover:-translate-y-1 hover:shadow-[0_25px_90px_-30px_rgba(0,0,0,0.75)]">
      <div className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100" aria-hidden>
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(111,220,255,0.08),rgba(111,220,255,0.02)_35%,rgba(255,126,95,0.08))]" />
      </div>

      <div className="relative z-10 flex flex-col gap-4 p-8">
        <div className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-200">
          {card.type === "image" && "Image"}
          {card.type === "file" && "File"}
          {card.type === "text" && "Text"}
          <span className="h-1 w-1 rounded-full bg-emerald-400/70" />
          Synced
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-50">{card.title}</h1>
            <p className="max-w-2xl text-base leading-relaxed text-slate-300">{card.description}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-right text-xs text-slate-200 shadow-inner">
            <div className="font-semibold text-slate-50">Quick Glance</div>
            <div className="text-slate-300">{card.file.size}</div>
            {card.image ? (
              <div className="text-slate-400">{card.image.resolution}</div>
            ) : card.wordCount ? (
              <div className="text-slate-400">{card.wordCount.toLocaleString()} words</div>
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
  );
}
