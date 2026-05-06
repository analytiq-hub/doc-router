import { useLayoutEffect, useMemo, useRef, useState } from 'react';

/**
 * Measures a hidden span and returns an input width in px that matches the rendered text + padding.
 * Keeps the control as wide as its content (up to CSS max-width) and grows as you type.
 */
export function useInlineNameWidthPx(value: string, placeholder: string) {
  const spanRef = useRef<HTMLSpanElement | null>(null);
  const [px, setPx] = useState<number | undefined>(undefined);

  const basis = useMemo(() => {
    const v = value.trim();
    return v.length ? v : placeholder;
  }, [placeholder, value]);

  useLayoutEffect(() => {
    const el = spanRef.current;
    if (!el) return;
    // +2px avoids occasional fractional rounding clipping.
    const next = Math.ceil(el.getBoundingClientRect().width + 2);
    setPx(next);
  }, [basis]);

  return { spanRef, widthPx: px, basis };
}

