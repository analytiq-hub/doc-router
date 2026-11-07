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

/** Lightweight stand-in for `next/image` in the Vite SPA. */
export default function AppImage({
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
