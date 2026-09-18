import { notFound } from "next/navigation";
import type { Metadata } from "next";
import PageBody from "@/components/PageBody";
import { getAllPaths, getPage, pageMetadata } from "@/lib/content";

type Params = { slug: string[] };

function pathFromSlug(slug: string[]) {
  return "/" + slug.map((s) => {
    try {
      return decodeURIComponent(s);
    } catch {
      return s;
    }
  }).join("/");
}

export function generateStaticParams() {
  return getAllPaths()
    .filter((path) => path !== "/")
    .map((path) => ({
      slug: path.replace(/^\//, "").split("/"),
    }));
}

export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const page = getPage(pathFromSlug(slug));
  return page ? pageMetadata(page) : {};
}

export default async function CatchAllPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const page = getPage(pathFromSlug(slug));
  if (!page) notFound();
  return <PageBody page={page} />;
}
