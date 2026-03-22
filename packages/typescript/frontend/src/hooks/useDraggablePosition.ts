import { useCallback, useLayoutEffect, useRef, useState } from 'react';

type Offset = { x: number; y: number };

/**
 * Pixel offset from a centered dialog position (left/top 50% with translate -50%).
 * Resets when `active` is true and `resetToken` changes.
 */
export function useDraggablePosition(active: boolean, resetToken: string | number) {
  const effectiveKey = active ? resetToken : null;
  const [offset, setOffset] = useState<Offset>({ x: 0, y: 0 });
  const [prevEffectiveKey, setPrevEffectiveKey] = useState<string | number | null>(null);
  const offsetRef = useRef<Offset>({ x: 0, y: 0 });

  if (effectiveKey !== prevEffectiveKey) {
    setPrevEffectiveKey(effectiveKey);
    if (effectiveKey !== null) {
      const z: Offset = { x: 0, y: 0 };
      if (offset.x !== 0 || offset.y !== 0) {
        setOffset(z);
      }
    }
  }

  useLayoutEffect(() => {
    offsetRef.current = offset;
  }, [offset]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const origX = offsetRef.current.x;
    const origY = offsetRef.current.y;

    const onMove = (ev: PointerEvent) => {
      const next: Offset = {
        x: origX + ev.clientX - startX,
        y: origY + ev.clientY - startY,
      };
      offsetRef.current = next;
      setOffset(next);
    };
    const onUp = () => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
    };
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onUp);
  }, []);

  return { offset, handlePointerDown };
}
