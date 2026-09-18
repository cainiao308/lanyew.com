export function isAdsenseEnabled() {
  return String(process.env.NEXT_PUBLIC_ADSENSE_ENABLED || "").toLowerCase() === "true";
}

export function getAdsenseClient() {
  return process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "";
}

export function getAdsenseConfig() {
  const enabled = isAdsenseEnabled();
  const client = getAdsenseClient();
  return { enabled, client };
}

export function shouldShowAds() {
  const { enabled, client } = getAdsenseConfig();
  return enabled && Boolean(client);
}

export function getAdsTxtContent() {
  return process.env.ADS_TXT_CONTENT || "";
}
