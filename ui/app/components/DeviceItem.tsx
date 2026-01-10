import React from "react";

export type DeviceStatus = "online" | "offline" | "idle";

export type Device = {
  id: string;
  name: string;
  address: string;
  status: DeviceStatus;
};

const statusColor: Record<DeviceStatus, string> = {
  online: "bg-emerald-400",
  offline: "bg-rose-400",
  idle: "bg-amber-300",
};

function DefaultDeviceIcon({ muted = false }: { muted?: boolean }) {
  return (
    <div className={`relative flex h-9 w-9 items-center justify-center rounded-2xl ${muted ? "bg-white/5" : "bg-cyan-400/15"} border border-white/10`}> 
      <div className="relative h-4 w-4">
        <span className={`absolute inset-0 rounded-full ${muted ? "bg-white/30" : "bg-cyan-300"}`} />
        <span className={`absolute inset-0 scale-[1.5] rounded-full ${muted ? "bg-white/10" : "bg-cyan-200/50"}`} />
      </div>
    </div>
  );
}

export function DeviceItem({ device, compact = false }: { device: Device; compact?: boolean }) {
  const status = statusColor[device.status];

  return (
    <div className="group flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-3 shadow-[0_14px_30px_-24px_rgba(0,0,0,0.8)] transition hover:border-white/25 hover:bg-white/10">
      <div className="relative">
        <DefaultDeviceIcon muted={compact} />
        <span className={`absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full ring-2 ring-[#0c0f14] ${status}`} />
      </div>
      {!compact && (
        <div className="flex flex-1 items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-slate-100">{device.name}</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{device.address}</div>
          </div>
          <div className="text-[11px] rounded-full border border-white/10 px-2 py-1 text-slate-300 capitalize">
            {device.status}
          </div>
        </div>
      )}
    </div>
  );
}
