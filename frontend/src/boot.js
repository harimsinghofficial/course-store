// Data the server embeds in the page (<script id="boot" type="application/json">) so React can paint
// immediately. When it is missing (e.g. `npm run dev`), components fall back to fetching the same data.
function read() {
  try {
    const el = document.getElementById('boot');
    return el ? JSON.parse(el.textContent) || {} : {};
  } catch {
    return {};
  }
}

export const boot = read();
