import { useId, useState } from 'react';

// Animated disclosure (CSS grid-rows transition). `as` lets the curriculum rail reuse it as an <li>.
export default function Accordion({ title, meta, defaultOpen = false, as: Tag = 'div', className = '', marker, children }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <Tag className={`acc ${className}${open ? ' is-open' : ''}`}>
      {marker}
      <h3>
        <button className="acc__btn" type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
          <span className="acc__title">
            {meta ? <span className="acc__meta">{meta}</span> : null}
            {title}
          </span>
          <span className="acc__icon" aria-hidden="true" />
        </button>
      </h3>
      <div className="acc__panel" id={id} role="region" aria-label={title}>
        <div className="acc__inner"><div className="acc__body">{children}</div></div>
      </div>
    </Tag>
  );
}
