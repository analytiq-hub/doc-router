import React from 'react';

import analytiqHubLogoMask from './analytiq-hub-logo-mask.png';

/** Analytiq Hub mark — head profile with circuit nodes; inherits `currentColor` from parent. */
export function AnalytiqHubIcon({ className }: { className?: string }): React.ReactElement {
  return (
    <span
      aria-hidden
      className={['inline-block shrink-0', className].filter(Boolean).join(' ')}
      style={{
        backgroundColor: 'currentColor',
        WebkitMaskImage: `url(${analytiqHubLogoMask.src})`,
        maskImage: `url(${analytiqHubLogoMask.src})`,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
        WebkitMaskMode: 'alpha',
        maskMode: 'alpha',
      }}
    />
  );
}
