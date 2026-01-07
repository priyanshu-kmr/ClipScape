import { NextResponse } from "next/server";
import { getRedisStatus, pingRedis } from "@/app/lib/redis";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const status = getRedisStatus();

    if (status === "ready") {
      const alive = await pingRedis();
      return NextResponse.json({ status: alive ? "connected" : "error", ok: alive });
    }

    return NextResponse.json({ status, ok: false });
  } catch (error) {
    console.error("Redis status failure", error);
    return NextResponse.json({ status: "error", ok: false }, { status: 500 });
  }
}
