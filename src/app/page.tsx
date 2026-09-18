import type { Metadata } from "next";
import PageBody from "@/components/PageBody";
import { getPage, pageMetadata } from "@/lib/content";

export function generateMetadata(): Metadata {
  const page = getPage("/");
  return page ? pageMetadata(page) : { title: "蓝叶网" };
}

export default function HomePage() {
  const page = getPage("/");
  if (!page) {
    return <main style={{ padding: 24 }}>首页内容尚未生成，请先运行 crawl。</main>;
  }
  return <PageBody page={page} />;
}
