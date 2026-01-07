import { NextResponse } from "next/server";
import { getRedis, pingRedis } from "@/app/lib/redis";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST() {
  try {
    await getRedis();
    const alive = await pingRedis();

    return NextResponse.json(
      {
        status: alive ? "connected" : "error",
        ok: alive,
      },
      { status: alive ? 200 : 500 }
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("Redis connect failure", error);
    return NextResponse.json({ status: "error", ok: false, message }, { status: 500 });
  }
}
