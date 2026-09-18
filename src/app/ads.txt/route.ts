import { NextResponse } from "next/server";
import { getAdsTxtContent } from "@/lib/adsense";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

export function GET() {
  return new NextResponse(getAdsTxtContent(), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
