// Indian digit grouping, mirrors inr() in main.py: 1499900 paise -> "₹14,999".
export function inr(paise) {
  const n = Math.max(0, Math.round(Number(paise) || 0));
  const rupees = Math.floor(n / 100);
  const rem = n % 100;
  let s = String(rupees);
  if (s.length > 3) {
    let head = s.slice(0, -3);
    const tail = s.slice(-3);
    const parts = [];
    while (head.length > 2) {
      parts.unshift(head.slice(-2));
      head = head.slice(0, -2);
    }
    if (head) parts.unshift(head);
    s = [...parts, tail].join(',');
  }
  return `₹${s}${rem ? `.${String(rem).padStart(2, '0')}` : ''}`;
}

export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function pad2(n) {
  return n < 10 ? `0${n}` : String(n);
}

// Split a number of milliseconds into countdown units.
export function splitDuration(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
}
