import { useRef } from 'react';
import { useInView } from '../hooks/useMedia.js';

const CELLS = 25;

// 25-segment meter that fills in when it scrolls into view.
export default function SeatBar({ total, left }) {
  const ref = useRef(null);
  const inView = useInView(ref, { threshold: 0.5, once: true });
  const taken = total - left;
  const filled = taken > 0 ? Math.ceil((taken / total) * CELLS) : 0;
  return (
    <div className={`seatbar${inView ? ' is-in' : ''}`} ref={ref} aria-hidden="true">
      {Array.from({ length: CELLS }, (_, n) => (
        <i key={n} className={n < filled ? 'taken' : ''} style={{ '--i': n }} />
      ))}
    </div>
  );
}
