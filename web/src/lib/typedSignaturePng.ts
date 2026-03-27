/** Render typed name to a PNG data URL (saved like Streamlit canvas signatures). */
export function dataUrlFromTypedSignature(name: string): string | null {
  const t = name.trim();
  if (t.length < 2) return null;
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 220;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, 640, 220);
  ctx.fillStyle = "#1e293b";
  let fontSize = 52;
  const family =
    "'Segoe Script', 'Brush Script MT', 'Apple Chancery', 'Snell Roundhand', cursive";
  ctx.textBaseline = "middle";
  const maxW = 560;
  for (;;) {
    ctx.font = `italic ${fontSize}px ${family}`;
    if (ctx.measureText(t).width <= maxW || fontSize <= 22) break;
    fontSize -= 2;
  }
  ctx.fillText(t, 40, 110);
  try {
    return canvas.toDataURL("image/png");
  } catch {
    return null;
  }
}

export async function dataUrlToPngBlob(dataUrl: string): Promise<Blob> {
  const res = await fetch(dataUrl);
  return res.blob();
}
