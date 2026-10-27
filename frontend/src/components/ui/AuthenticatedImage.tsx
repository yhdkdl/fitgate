import React, { useEffect, useState } from "react";
import { fetchAuthenticatedBlobUrl } from "../../api/media";

export interface AuthenticatedImageProps {
  src?: string | null;
  alt?: string;
  fallbackInitials?: string;
  className?: string;
  placeholderClassName?: string;
}

function getInitials(nameOrInitials?: string): string {
  if (!nameOrInitials) return "?";
  const clean = nameOrInitials.trim();
  if (!clean) return "?";
  return clean.charAt(0).toUpperCase();
}

/**
 * Shared Authenticated Image Component.
 *
 * Fetches protected images with Authorization headers + token refresh,
 * in-page caching, revokes blob URLs on unmount/source change,
 * and renders a neutral initials placeholder (not a broken-image icon)
 * when absent, loading, or on error.
 */
export const AuthenticatedImage: React.FC<AuthenticatedImageProps> = ({
  src,
  alt = "Photo",
  fallbackInitials,
  className = "",
  placeholderClassName,
}) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!src) {
      setBlobUrl(null);
      setIsError(false);
      return;
    }

    let isMounted = true;
    let localBlobUrl: string | null = null;
    setIsError(false);

    fetchAuthenticatedBlobUrl(src)
      .then((url) => {
        if (!isMounted) {
          URL.revokeObjectURL(url);
          return;
        }
        localBlobUrl = url;
        setBlobUrl(url);
      })
      .catch(() => {
        if (!isMounted) return;
        setBlobUrl(null);
        setIsError(true);
      });

    return () => {
      isMounted = false;
      if (localBlobUrl) {
        URL.revokeObjectURL(localBlobUrl);
      }
    };
  }, [src]);

  const initials = getInitials(fallbackInitials || alt);

  // If no source, loading, or load error, render neutral initials placeholder
  if (!src || isError || !blobUrl) {
    return (
      <div
        className={
          placeholderClassName ||
          `${className} bg-surface-2 text-text-muted flex items-center justify-center font-bold select-none`
        }
        aria-label={alt}
        role="img"
      >
        <span>{initials}</span>
      </div>
    );
  }

  return (
    <img
      src={blobUrl}
      alt={alt}
      className={className}
      onError={() => {
        setIsError(true);
        if (blobUrl) {
          URL.revokeObjectURL(blobUrl);
          setBlobUrl(null);
        }
      }}
    />
  );
};
