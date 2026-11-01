import { useEffect, useRef, useState } from 'react';
import { pad2, splitDuration } from '../lib/format.js';

// Live countdown to the end of the early-access price. When it hits zero the page asks the server for the
// new price (once per end time, so a skewed clock can never cause a request loop).
export default function Countdown({ endIso, onExpire }) {
  const end = Date.parse(endIso);
  const [now, setNow] = useState(() => Date.now());
  const fired = useRef('');

  useEffect(() => {
    if (Number.isNaN(end)) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [end]);

  const left = end - now;
  useEffect(() => {
    if (!Number.isNaN(end) && left <= 0 && fired.current !== endIso) {
      fired.current = endIso;
      const t = setTimeout(() => onExpire && onExpire(), 1200);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [left, end, endIso, onExpire]);

  if (Number.isNaN(end)) return null;
  const u = splitDuration(left);
  const cells = [['d', 'days', String(u.d)], ['h', 'hours', pad2(u.h)], ['m', 'mins', pad2(u.m)], ['s', 'secs', pad2(u.s)]];
  return (
    <div className="countdown" role="timer" aria-label="Time left at the early-access price">
      {cells.map(([k, label, text]) => (
        <div className="countdown__cell" key={k}>
          {/* key on the value re-mounts <b>, replaying the CSS tick animation each change */}
          <b key={k === 'd' ? 'd' : text}>{text}</b>
          <small>{label}</small>
        </div>
      ))}
    </div>
  );
}
