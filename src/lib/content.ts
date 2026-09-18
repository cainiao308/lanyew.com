import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Metadata } from "next";

export type SitePage = {
  title: string;
  description: string;
  robots: string;
  canonical: string;
  ogTitle: string;
  ogDescription: string;
  ogType: string;
  ogUrl: string;
  css?: string[];
  js?: string[];
  inlineStyle?: string;
  html: string;
  source?: string;
};

let cache: Record<string, SitePage> | null = null;

function loadPages() {
  if (!cache) {
    const file = join(process.cwd(), "src/data/pages.json");
    cache = JSON.parse(readFileSync(file, "utf8")) as Record<string, SitePage>;
  }
  return cache;
}

export function normalizePath(path: string) {
  if (!path || path === "/") return "/";
  const withSlash = path.startsWith("/") ? path : `/${path}`;
  // keep .html and extensionless sort/tag paths without forcing trailing slash
  return withSlash;
}

export function getPage(path: string) {
  const pages = loadPages();
  const n = normalizePath(path);
  if (pages[n]) return pages[n];
  // try with/without trailing slash
  if (n.endsWith("/") && pages[n.slice(0, -1)]) return pages[n.slice(0, -1)];
  if (!n.endsWith("/") && pages[n + "/"]) return pages[n + "/"];
  return null;
}

export function getAllPaths() {
  return Object.keys(loadPages());
}

export function pageMetadata(page: SitePage): Metadata {
  const metadata: Metadata = {
    title: page.title,
    description: page.description || undefined,
    robots: page.robots || undefined,
    alternates: page.canonical ? { canonical: page.canonical } : undefined,
  };

  if (page.ogTitle || page.ogDescription || page.ogUrl) {
    metadata.openGraph = {
      title: page.ogTitle || page.title,
      description: page.ogDescription || page.description,
      type: page.ogType === "article" ? "article" : "website",
      url: page.ogUrl || page.canonical || undefined,
    };
  }

  return metadata;
}
