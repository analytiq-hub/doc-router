import type { CSSProperties, ImgHTMLAttributes } from 'react';

type ImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'alt'> & {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  fill?: boolean;
  priority?: boolean;
  sizes?: string;
  quality?: number;
};

/** Vite stand-in for `next/image` (vite.config.ts alias). */
export default function Image({
  src,
  alt,
  width,
  height,
  className,
  fill,
  priority,
  style,
  sizes: _sizes,
  quality: _quality,
  ...rest
}: ImageProps) {
  const imgStyle: CSSProperties = fill
    ? { objectFit: 'cover', width: '100%', height: '100%', ...style }
    : { ...style };

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={fill ? undefined : width}
      height={fill ? undefined : height}
      className={className}
      style={imgStyle}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      {...rest}
    />
  );
}
