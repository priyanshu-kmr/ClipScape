"use client";

import { useEffect, useMemo, useState } from "react";
import { CardData, ClipCard } from "@/app/components/ClipCard";
import { Device, DeviceItem } from "@/app/components/DeviceItem";
type ConnectionState = "idle" | "connecting" | "connected" | "error" | "disconnected";

const statusColors: Record<ConnectionState, string> = {
  connected: "bg-emerald-400 shadow-[0_0_0_6px_rgba(16,185,129,0.15)]",
  connecting: "bg-amber-300 shadow-[0_0_0_6px_rgba(251,191,36,0.15)] animate-pulse",
  idle: "bg-slate-500 shadow-[0_0_0_6px_rgba(100,116,139,0.15)]",
  disconnected: "bg-slate-600 shadow-[0_0_0_6px_rgba(71,85,105,0.15)]",
  error: "bg-rose-400 shadow-[0_0_0_6px_rgba(244,63,94,0.18)]",
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

const discoveredDevices: Device[] = [
  { id: "d1", name: "Living Room PC", address: "192.168.1.21", status: "online" },
  { id: "d2", name: "Work Laptop", address: "192.168.1.42", status: "idle" },
];

const knownDevices: Device[] = [
  { id: "k1", name: "Studio Mac", address: "192.168.1.13", status: "offline" },
  { id: "k2", name: "Render Node", address: "192.168.1.31", status: "online" },
];

export default function Home() {
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [sidebarOpen, setSidebarOpen] = useState(true);

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

  return (
    <div className="min-h-screen bg-[#0c0f14] text-slate-100">
      <div className="relative isolate flex min-h-screen px-4 py-10 sm:px-6 lg:px-10">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,rgba(80,126,255,0.2),transparent_35%),radial-gradient(circle_at_80%_0%,rgba(111,220,255,0.14),transparent_28%),radial-gradient(circle_at_90%_70%,rgba(255,126,95,0.16),transparent_30%)]" />

        <div className="hidden w-80 flex-col gap-3 lg:flex lg:pr-6">
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="w-full rounded-3xl border border-white/10 bg-gradient-to-r from-[#1c2230] via-[#181d27] to-[#141922] px-5 py-4 text-left text-sm font-semibold text-slate-100 shadow-[0_18px_60px_-35px_rgba(0,0,0,0.8)] transition hover:border-white/25 hover:bg-white/10"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="relative flex h-9 w-9 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                  <span className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-400/30 via-cyan-300/10 to-emerald-300/10" aria-hidden />
                  <span className="relative text-base text-slate-100">⇅</span>
                </span>
                <div className="leading-tight">
                  <div className="text-sm font-semibold text-slate-100">Devices</div>
                  <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Discovered + Known</div>
                </div>
              </div>
              <span className={`text-lg transition-transform duration-200 ${sidebarOpen ? "rotate-180" : "rotate-0"}`}>
                ▾
              </span>
            </div>
          </button>

          {sidebarOpen && (
            <div className="space-y-5 rounded-3xl border border-white/10 bg-white/5 p-4 shadow-[0_20px_80px_-40px_rgba(0,0,0,0.8)] backdrop-blur-xl">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Discovered Devices</div>
                <div className="mt-2 space-y-2">
                  {discoveredDevices.map((device) => (
                    <DeviceItem key={device.id} device={device} />
                  ))}
                </div>
              </div>

              <div className="h-px bg-white/10" />

              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Known Devices</div>
                <div className="mt-2 space-y-2">
                  {knownDevices.map((device) => (
                    <DeviceItem key={device.id} device={device} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex w-full flex-col items-center justify-center lg:items-start">
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
                  <span className="tracking-wide">Sync Files</span>
                </button>
                <span className="rounded-full bg-white/5 px-3 py-1 font-medium text-slate-200 shadow-sm">Hover to reveal metadata</span>
              </div>
            </div>

            <ClipCard card={demoCard} />
          </div>
        </div>
      </div>
    </div>
  );
}
