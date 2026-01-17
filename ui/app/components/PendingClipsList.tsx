"use client";

import { useEffect, useState } from "react";
import { CardData, ClipCard, FileKind } from "@/app/components/ClipCard";
import {
  PendingClip,
  approvePendingClip,
  fetchPendingClips,
  rejectPendingClip,
} from "@/app/lib/pendingClips";

const POLL_INTERVAL_MS = 2000;

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exp = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  const value = bytes / Math.pow(1024, exp);
  return `${value.toFixed(exp === 0 ? 0 : 1)} ${units[exp]}`;
}

function toFileKind(type: PendingClip["type"]): FileKind {
  if (type === "text") return "text";
  if (type === "image") return "image";
  return "file";
}

function toCardData(clip: PendingClip): CardData {
  const meta = clip.metadata as Record<string, unknown>;
  const name =
    (meta.file_name as string) ||
    (meta.folder_name as string) ||
    (clip.type === "text" ? "Text clip" : "Clip");

  return {
    type: toFileKind(clip.type),
    title: name,
    description: clip.preview || "(no preview available)",
    file: {
      name,
      path: (meta.path as string) || "",
      size: formatBytes(clip.size_bytes),
      createdAt: (meta.creation_time as string) || clip.timestamp,
      mime: (meta.mime as string) || "",
    },
  };
}

export function PendingClipsList() {
  const [clips, setClips] = useState<PendingClip[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const items = await fetchPendingClips();
      setClips(items);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const items = await fetchPendingClips();
        if (!active) return;
        setClips(items);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError((err as Error).message);
      }
    };

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const handleApprove = async (id: string) => {
    await approvePendingClip(id);
    await refresh();
  };

  const handleReject = async (id: string) => {
    await rejectPendingClip(id);
    await refresh();
  };

  return (
    <div className="mb-10 space-y-4">
      <div className="flex items-center justify-between text-sm text-slate-400">
        <span className="tracking-wide">Pending Approval ({clips.length})</span>
        {error && (
          <span className="rounded-full bg-rose-400/10 px-3 py-1 text-xs text-rose-300">
            Approval server unreachable
          </span>
        )}
      </div>

      {clips.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-white/10 px-6 py-8 text-center text-sm text-slate-500">
          No clips awaiting approval.
        </div>
      ) : (
        <div className="space-y-4">
          {clips.map((clip) => (
            <ClipCard
              key={clip.id}
              card={toCardData(clip)}
              onApprove={() => handleApprove(clip.id)}
              onReject={() => handleReject(clip.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
