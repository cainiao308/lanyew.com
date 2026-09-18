import type { SitePage } from "@/lib/content";

export default function PageBody({ page }: { page: SitePage }) {
  const css = (page.css?.length
    ? page.css
    : [
        "/content/templates/lanyesimpleone/css/fontawesom/font-awesome.css",
        "/content/templates/lanyesimpleone/css/style.css",
        "/content/templates/lanyesimpleone/css/markdown.css",
      ]
  ).map((href) => href.split("?")[0]);

  const js = (page.js?.length
    ? page.js
    : [
        "/content/templates/lanyesimpleone/js/jquery.min.js",
        "/content/templates/lanyesimpleone/js/script.js",
      ]
  ).map((src) => src.split("?")[0]);

  const scriptsHtml = js.map((src) => `<script src="${src}"></script>`).join("");
  const html = `${page.html}${scriptsHtml}`;

  return (
    <>
      {css.map((href) => (
        <link key={href} rel="stylesheet" href={href} />
      ))}
      {page.inlineStyle ? <style dangerouslySetInnerHTML={{ __html: page.inlineStyle }} /> : null}
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </>
  );
}
