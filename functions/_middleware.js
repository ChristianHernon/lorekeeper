// Discord shows og:image small inside its embed, so serve it a punchier 16:9 card.
// Every other request passes through untouched.
const DISCORD_IMAGE = "https://lorekeeper-cgv.pages.dev/og/discord.png?v=3";   // bump ?v= when the image changes: Discord caches images by URL

const setContent = (value) => ({
  element(el) { el.setAttribute("content", value); },
});

export async function onRequest({ request, next }) {
  const response = await next();
  const ua = request.headers.get("user-agent") || "";
  const type = response.headers.get("content-type") || "";
  if (!ua.includes("Discordbot") || !type.includes("text/html")) return response;

  return new HTMLRewriter()
    .on('meta[property="og:image"]', setContent(DISCORD_IMAGE))
    .on('meta[name="twitter:image"]', setContent(DISCORD_IMAGE))
    .on('meta[property="og:image:width"]', setContent("1280"))
    .on('meta[property="og:image:height"]', setContent("720"))
    .transform(response);
}
