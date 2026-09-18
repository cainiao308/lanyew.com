import type { Metadata, Viewport } from "next";
import { getAdsenseConfig, shouldShowAds } from "@/lib/adsense";

export const metadata: Metadata = {
  title: {
    default: "蓝叶网 - 分享emlog模板插件zblog模板插件精品好资源",
    template: "%s",
  },
  description: "蓝叶网站分享emlog模板插件zblog模板插件精品好资源。",
  robots: "index,follow",
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const { client } = getAdsenseConfig();
  const showAds = shouldShowAds();

  return (
    <html lang="zh-cn" suppressHydrationWarning>
      <head>
        <meta name="renderer" content="webkit" />
        {client ? <meta name="google-adsense-account" content={client} /> : null}
        {showAds ? (
          <script
            async
            crossOrigin="anonymous"
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(client)}`}
          />
        ) : null}
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
