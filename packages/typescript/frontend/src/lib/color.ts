/**
 * `'black'` or `'white'`, whichever has the higher WCAG contrast on a `#rrggbb` background. For
 * colors chosen by users (tag colors), which are data and not design tokens.
 */
export function readableTextColor(background: string): 'black' | 'white' {
  const match = /^#?([0-9a-f]{6})$/i.exec(background.trim());
  if (!match) return 'white';
  const [r, g, b] = [0, 2, 4]
    .map((i) => parseInt(match[1].slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const againstWhite = 1.05 / (luminance + 0.05);
  const againstBlack = (luminance + 0.05) / 0.05;
  return againstWhite >= againstBlack ? 'white' : 'black';
}
