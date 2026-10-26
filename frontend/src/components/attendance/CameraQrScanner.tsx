import React, { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";
import { Camera, X, Clock, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "../ui/Button";
import { checkQrCooldown, PAUSE_DURATION_MS } from "./qrCooldown";

export interface CameraQrScannerProps {
  onScan: (code: string) => void;
  onClose?: () => void;
  isProcessing?: boolean;
  variant?: "inline" | "fullscreen";
  onManualToggle?: () => void;
  disabled?: boolean;
}

const FACING_STORAGE_KEY = "fitgate_camera_facing";

export const CameraQrScanner: React.FC<CameraQrScannerProps> = ({
  onScan,
  onClose,
  isProcessing = false,
  variant = "inline",
  onManualToggle,
  disabled = false,
}) => {
  const [error, setError] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">(() => {
    try {
      const saved = localStorage.getItem(FACING_STORAGE_KEY);
      return saved === "user" ? "user" : "environment";
    } catch {
      return "environment";
    }
  });

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const pauseTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastScannedTimeRef = useRef<number>(0);
  const isPausedRef = useRef<boolean>(false);
  const isProcessingRef = useRef<boolean>(isProcessing);
  isProcessingRef.current = isProcessing;

  const wakeLockSentinelRef = useRef<{ release: () => Promise<void> } | null>(
    null
  );

  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const handleQrDetectedRef = useRef<(code: string) => boolean>(() => false);

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

  const requestWakeLock = async () => {
    if (
      typeof navigator !== "undefined" &&
      "wakeLock" in navigator &&
      document.visibilityState === "visible"
    ) {
      try {
        const navWithWakeLock = navigator as unknown as {
          wakeLock: {
            request: (
              type: "screen"
            ) => Promise<{ release: () => Promise<void> }>;
          };
        };
        wakeLockSentinelRef.current =
          await navWithWakeLock.wakeLock.request("screen");
      } catch {
        // Screen Wake Lock rejected or not supported on this platform
      }
    }
  };

  const releaseWakeLock = async () => {
    if (wakeLockSentinelRef.current) {
      try {
        await wakeLockSentinelRef.current.release();
      } catch {
        // ignore release errors
      }
      wakeLockSentinelRef.current = null;
    }
  };

  const toggleFacingMode = () => {
    const nextMode = facingMode === "environment" ? "user" : "environment";
    setFacingMode(nextMode);
    try {
      localStorage.setItem(FACING_STORAGE_KEY, nextMode);
    } catch {
      // ignore storage errors
    }
  };

  const handleQrDetected = (codeData: string) => {
    if (disabled) return false;

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
  handleQrDetectedRef.current = handleQrDetected;

  useEffect(() => {
    let mounted = true;

    // Check secure context (HTTPS, localhost, *.localhost, 127.0.0.1)
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
        "Camera scanning requires a secure connection (HTTPS or localhost). Please use the manual code field."
      );
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(
        "No camera found on this device. Please use the manual code field."
      );
      return;
    }

    const startCamera = async () => {
      try {
        setError(null);
        let stream: MediaStream;
        try {
          // Ask for 1280x720 or better and continuous autofocus if supported
          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: { ideal: facingMode },
              width: { ideal: 1280, min: 640 },
              height: { ideal: 720, min: 480 },
              advanced: [
                { focusMode: "continuous" } as MediaTrackConstraintSet,
              ],
            },
          });
        } catch {
          try {
            // Fallback without advanced focus constraint if rejected
            stream = await navigator.mediaDevices.getUserMedia({
              video: {
                facingMode: { ideal: facingMode },
                width: { ideal: 1280, min: 640 },
                height: { ideal: 720, min: 480 },
              },
            });
          } catch {
            // Fallback to basic facingMode constraint if resolution constraints fail
            stream = await navigator.mediaDevices.getUserMedia({
              video: { facingMode: { ideal: facingMode } },
            });
          }
        }

        // Apply track-level continuous focus if supported
        const videoTrack = stream.getVideoTracks()[0];
        if (videoTrack && typeof videoTrack.applyConstraints === "function") {
          try {
            const capabilities =
              typeof videoTrack.getCapabilities === "function"
                ? (videoTrack.getCapabilities() as unknown as {
                    focusMode?: string[];
                  })
                : null;
            if (capabilities?.focusMode?.includes("continuous")) {
              await videoTrack
                .applyConstraints({
                  advanced: [
                    { focusMode: "continuous" } as MediaTrackConstraintSet,
                  ],
                })
                .catch(() => {});
            }
          } catch {
            // ignore if unsupported
          }
        }

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

        // Request Screen Wake Lock while scanning
        await requestWakeLock();

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
                handleQrDetectedRef.current(code.data.trim());
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
            "No camera found on this device. Please use the manual code field."
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
            `Unable to access camera: ${errObj.message || "Unknown error"}. Please use the manual code field.`
          );
        }
      }
    };

    startCamera();

    // Turn camera and wake lock off when tab hidden
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        stopCamera();
        releaseWakeLock();
        if (variant === "inline" && onCloseRef.current) {
          onCloseRef.current();
        }
      } else if (document.visibilityState === "visible") {
        if (variant === "fullscreen" && mounted) {
          startCamera();
        }
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      mounted = false;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      stopCamera();
      releaseWakeLock();
    };
  }, [facingMode, variant]);

  const isFullscreen = variant === "fullscreen";

  return (
    <div
      className={
        isFullscreen
          ? "w-full h-full flex flex-col justify-between relative bg-black select-none"
          : "w-full max-w-md mx-auto bg-surface border border-border rounded-xl p-4 shadow-md space-y-3"
      }
      role="region"
      aria-label="Camera QR Scanner"
    >
      {/* Controls Bar */}
      <div
        className={
          isFullscreen
            ? "absolute top-4 inset-x-4 z-20 flex items-center justify-between pointer-events-auto"
            : "flex items-center justify-between pb-2 border-b border-border"
        }
      >
        <div className="flex items-center gap-2">
          {!isFullscreen && <Camera className="w-5 h-5 text-primary" />}
          {!isFullscreen && (
            <h3 className="font-bold text-sm text-text">Camera Scanner</h3>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Camera front/back switch button */}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={toggleFacingMode}
            className="min-h-[44px] min-w-[44px] px-3 flex items-center gap-1.5 text-xs focus:ring-2 focus:ring-primary focus:outline-none bg-surface/80 backdrop-blur-sm border border-border"
            aria-label="Switch camera front/back"
            title={`Switch camera (currently ${facingMode === "environment" ? "back" : "front"})`}
          >
            <RefreshCw className="w-4 h-4 text-primary" />
            <span className="hidden sm:inline">
              {facingMode === "environment" ? "Back Camera" : "Front Camera"}
            </span>
          </Button>

          {onClose && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                stopCamera();
                onClose();
              }}
              className="min-h-[44px] min-w-[44px] px-3 flex items-center gap-1.5 text-xs focus:ring-2 focus:ring-primary focus:outline-none bg-surface/80 backdrop-blur-sm border border-border"
              aria-label="Close camera scanner"
            >
              <X className="w-4 h-4" />
              <span>{isFullscreen ? "Exit Scanner" : "Close Camera"}</span>
            </Button>
          )}
        </div>
      </div>

      {/* Main Viewport */}
      {error ? (
        <div
          className={
            isFullscreen
              ? "flex-1 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto space-y-4"
              : "p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-left space-y-2"
          }
        >
          <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>Camera Unavailable</span>
          </div>
          <p className="text-sm text-text-muted">{error}</p>
          {onManualToggle && (
            <Button
              type="button"
              variant="primary"
              onClick={onManualToggle}
              className="min-h-[44px] px-4 text-xs font-semibold mt-2"
            >
              Enter Code Manually
            </Button>
          )}
        </div>
      ) : (
        <div
          className={
            isFullscreen
              ? "relative flex-1 w-full h-full bg-black overflow-hidden flex items-center justify-center"
              : "relative aspect-square sm:aspect-video w-full bg-black rounded-lg overflow-hidden flex items-center justify-center border border-border/50"
          }
        >
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className="w-full h-full object-cover"
            aria-label="Live camera preview"
          />

          {/* Viewfinder Target Overlay */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
            <div
              className={
                isFullscreen
                  ? "w-64 h-64 sm:w-80 sm:h-80 md:w-96 md:h-96 border-2 border-primary/70 rounded-2xl relative shadow-2xl"
                  : "w-56 h-56 sm:w-64 sm:h-64 border-2 border-primary/70 rounded-lg relative"
              }
            >
              <div className="absolute -top-1 -left-1 w-6 h-6 border-t-4 border-l-4 border-primary rounded-tl-lg" />
              <div className="absolute -top-1 -right-1 w-6 h-6 border-t-4 border-r-4 border-primary rounded-tr-lg" />
              <div className="absolute -bottom-1 -left-1 w-6 h-6 border-b-4 border-l-4 border-primary rounded-bl-lg" />
              <div className="absolute -bottom-1 -right-1 w-6 h-6 border-b-4 border-r-4 border-primary rounded-br-lg" />
            </div>
          </div>

          {/* Paused (3s Cooldown) Badge */}
          {isPaused && (
            <div
              className="absolute top-16 left-4 bg-slate-900/90 text-amber-300 border border-amber-400/50 px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-md animate-pulse"
              role="status"
              aria-live="polite"
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Paused (3s cooldown)</span>
            </div>
          )}

          {isProcessing && !isPaused && (
            <div
              className="absolute bottom-16 inset-x-4 max-w-xs mx-auto text-center bg-slate-900/90 text-primary border border-primary/40 px-4 py-2 rounded-lg text-sm font-semibold shadow-lg"
              role="status"
              aria-live="polite"
            >
              Verifying scan...
            </div>
          )}
        </div>
      )}

      {/* Footer / Instructions */}
      <div
        className={
          isFullscreen
            ? "absolute bottom-4 inset-x-4 z-20 flex flex-col items-center gap-2 pointer-events-auto"
            : "text-center space-y-1.5"
        }
      >
        {!isFullscreen && (
          <p className="text-xs text-text-muted">
            Point camera at a member's QR code. Once read, scanner pauses 3s
            before next read.
          </p>
        )}

        {onManualToggle && (
          <button
            type="button"
            onClick={onManualToggle}
            className="min-h-[44px] min-w-[44px] px-3 py-2 text-xs font-medium text-text-muted hover:text-primary underline flex items-center justify-center transition-colors focus:ring-2 focus:ring-primary focus:outline-none rounded"
          >
            Enter code manually
          </button>
        )}
      </div>
    </div>
  );
};
