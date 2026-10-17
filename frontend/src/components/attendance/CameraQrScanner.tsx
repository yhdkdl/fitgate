import React, { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";
import { Camera, X, Clock, AlertCircle } from "lucide-react";
import { Button } from "../ui/Button";

import { checkQrCooldown } from "./qrCooldown";

interface CameraQrScannerProps {
  onScan: (code: string) => void;
  onClose: () => void;
  isProcessing?: boolean;
}

export const CameraQrScanner: React.FC<CameraQrScannerProps> = ({
  onScan,
  onClose,
  isProcessing = false,
}) => {
  const [error, setError] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const pauseTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastScannedTimeRef = useRef<number>(0);
  const isPausedRef = useRef<boolean>(false);
  const isProcessingRef = useRef<boolean>(isProcessing);
  isProcessingRef.current = isProcessing;

  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const stopCamera = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (pauseTimerRef.current) {
      clearTimeout(pauseTimerRef.current);
      pauseTimerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // ignore error on stop
        }
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const handleQrDetected = (codeData: string) => {
    const now = Date.now();
    const canScan = checkQrCooldown(
      now,
      lastScannedTimeRef.current,
      isPausedRef.current,
      isProcessingRef.current
    );

    if (!canScan) {
      return false;
    }

    isPausedRef.current = true;
    lastScannedTimeRef.current = now;
    setIsPaused(true);

    onScanRef.current(codeData);

    if (pauseTimerRef.current) {
      clearTimeout(pauseTimerRef.current);
    }
    pauseTimerRef.current = setTimeout(() => {
      isPausedRef.current = false;
      setIsPaused(false);
    }, PAUSE_DURATION_MS);

    return true;
  };

  useEffect(() => {
    let mounted = true;

    // Check secure context (HTTPS or localhost)
    const hostname = window.location.hostname;
    const isLocalhost =
      hostname === "localhost" ||
      hostname.endsWith(".localhost") ||
      hostname === "127.0.0.1";
    const isSecure =
      window.isSecureContext ||
      window.location.protocol === "https:" ||
      isLocalhost;

    if (!isSecure) {
      setError(
        "Camera scanning requires a secure connection (HTTPS or localhost). Please use the paste field below."
      );
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(
        "Camera access is not supported by your browser. Please use the paste field below."
      );
      return;
    }

    const startCamera = async () => {
      try {
        setError(null);
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
        });

        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.setAttribute("playsinline", "true");
          videoRef.current.setAttribute("autoplay", "true");
          videoRef.current.setAttribute("muted", "true");
          await videoRef.current.play().catch(() => {});
        }

        const scanFrame = () => {
          if (!mounted) return;

          const video = videoRef.current;
          if (
            video &&
            video.readyState >= (video.HAVE_CURRENT_DATA ?? 2) &&
            video.videoWidth > 0 &&
            video.videoHeight > 0
          ) {
            let canvas = canvasRef.current;
            if (!canvas) {
              canvas = document.createElement("canvas");
              canvasRef.current = canvas;
            }

            if (
              canvas.width !== video.videoWidth ||
              canvas.height !== video.videoHeight
            ) {
              canvas.width = video.videoWidth;
              canvas.height = video.videoHeight;
            }

            const ctx = canvas.getContext("2d", { willReadFrequently: true });
            if (ctx) {
              ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
              const imageData = ctx.getImageData(
                0,
                0,
                canvas.width,
                canvas.height
              );
              const code = jsQR(
                imageData.data,
                imageData.width,
                imageData.height,
                {
                  inversionAttempts: "dontInvert",
                }
              );

              if (code && code.data && code.data.trim()) {
                handleQrDetected(code.data.trim());
              }
            }
          }

          animationFrameRef.current = requestAnimationFrame(scanFrame);
        };

        animationFrameRef.current = requestAnimationFrame(scanFrame);
      } catch (err: unknown) {
        if (!mounted) return;
        const errObj = err as { name?: string; message?: string };
        if (
          errObj.name === "NotAllowedError" ||
          errObj.name === "PermissionDeniedError"
        ) {
          setError(
            "Camera permission denied. Please allow camera access in your browser settings to scan QR codes."
          );
        } else if (
          errObj.name === "NotFoundError" ||
          errObj.name === "DevicesNotFoundError"
        ) {
          setError(
            "No camera found on this device. Please use the paste field below."
          );
        } else if (
          errObj.name === "NotReadableError" ||
          errObj.name === "TrackStartError"
        ) {
          setError(
            "Camera is currently busy or in use by another application. Please close other apps and try again."
          );
        } else {
          setError(
            `Unable to access camera: ${errObj.message || "Unknown error"}. Please use the paste field below.`
          );
        }
      }
    };

    startCamera();

    // Criterion 7: Stop when browser tab is hidden
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        stopCamera();
        onCloseRef.current();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      mounted = false;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      stopCamera();
    };
  }, []);

  return (
    <div
      className="w-full max-w-md mx-auto bg-surface border border-border rounded-xl p-4 shadow-md space-y-3"
      role="region"
      aria-label="Camera QR Scanner"
    >
      <div className="flex items-center justify-between pb-2 border-b border-border">
        <div className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-sm text-text">Camera Scanner</h3>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => {
            stopCamera();
            onClose();
          }}
          className="min-h-[44px] min-w-[44px] px-3 flex items-center gap-1.5 text-xs focus:ring-2 focus:ring-primary focus:outline-none"
          aria-label="Close camera scanner"
        >
          <X className="w-4 h-4" />
          Close Camera
        </Button>
      </div>

      {error ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-left space-y-2">
          <div className="flex items-center gap-2 text-rose-400 font-semibold text-xs">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Camera Unavailable</span>
          </div>
          <p className="text-xs text-text-muted">{error}</p>
        </div>
      ) : (
        <div className="relative aspect-square sm:aspect-video w-full bg-black rounded-lg overflow-hidden flex items-center justify-center border border-border/50">
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className="w-full h-full object-cover"
            aria-label="Live camera preview"
          />

          {/* Viewfinder Overlay */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
            <div className="w-56 h-56 sm:w-64 sm:h-64 border-2 border-primary/70 rounded-lg relative">
              <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-primary" />
              <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-primary" />
              <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-primary" />
              <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-primary" />
            </div>
          </div>

          {/* Paused (3s Cooldown) Badge */}
          {isPaused && (
            <div className="absolute top-3 left-3 bg-slate-900/90 text-amber-300 border border-amber-400/50 px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-md">
              <Clock className="w-3.5 h-3.5" />
              <span>Paused (3s cooldown)</span>
            </div>
          )}

          {isProcessing && !isPaused && (
            <div className="absolute bottom-3 inset-x-3 text-center bg-slate-900/90 text-primary border border-primary/40 px-3 py-1 rounded-md text-xs font-semibold">
              Verifying scan...
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-text-muted text-center">
        Point camera at a member's QR code. Once read, scanner pauses 3s before
        next read.
      </p>
    </div>
  );
};
