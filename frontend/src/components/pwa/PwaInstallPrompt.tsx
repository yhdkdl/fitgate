import React, { useEffect, useState } from "react";
import { Download, Share, X, Smartphone } from "lucide-react";
import { Button } from "../ui/Button";

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt(): Promise<void>;
}

export const PwaInstallPrompt: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    // Check if already in standalone display mode
    const standaloneMode =
      (typeof window.matchMedia === "function" &&
        window.matchMedia("(display-mode: standalone)").matches) ||
      (window.navigator as unknown as { standalone?: boolean }).standalone ===
        true;
    setIsStandalone(standaloneMode);

    // Detect iOS user agent
    const userAgent = window.navigator.userAgent || "";
    const isIosDevice =
      /iPad|iPhone|iPod/.test(userAgent) &&
      !(window as unknown as { MSStream?: unknown }).MSStream;
    setIsIOS(isIosDevice);

    // Listen for beforeinstallprompt event (Android / Chromium)
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener(
        "beforeinstallprompt",
        handleBeforeInstallPrompt
      );
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === "accepted") {
      setDeferredPrompt(null);
    }
  };

  // If already running standalone or user dismissed, don't show
  if (isStandalone || isDismissed) {
    return null;
  }

  // Android / Chromium with install prompt
  if (deferredPrompt) {
    return (
      <div
        className="w-full bg-gradient-to-r from-blue-900/40 via-blue-800/30 to-indigo-900/40 border border-blue-500/30 rounded-xl p-4 sm:p-5 mb-6 text-white shadow-lg backdrop-blur-sm"
        role="region"
        aria-label="PWA install prompt"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-lg bg-blue-600/30 text-blue-400 border border-blue-500/40 shrink-0">
              <Download className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-semibold text-base sm:text-lg text-white">
                Download App
              </h3>
              <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-xl">
                Install FitGate on your device for fast access and seamless offline
                QR check-in without the browser address bar.
              </p>
              <div className="mt-3.5 flex items-center gap-3">
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={handleInstallClick}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 min-h-[40px] flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <span>Download App</span>
                </Button>
                <button
                  type="button"
                  onClick={() => setIsDismissed(true)}
                  className="text-xs text-slate-400 hover:text-white px-2 py-1"
                >
                  Maybe later
                </button>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsDismissed(true)}
            aria-label="Dismiss download prompt"
            className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    );
  }

  // iOS Safari instructions
  if (isIOS) {
    return (
      <div
        className="w-full bg-gradient-to-r from-blue-900/30 via-slate-800/40 to-blue-900/30 border border-blue-500/30 rounded-xl p-4 mb-6 text-white shadow-lg backdrop-blur-sm"
        role="region"
        aria-label="iOS install instructions"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 shrink-0">
              <Smartphone className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-sm sm:text-base text-white">
                Add FitGate to Home Screen
              </h3>
              <p className="text-xs sm:text-sm text-slate-300 mt-1">
                Install FitGate as an app on your iPhone: tap the{" "}
                <span className="inline-flex items-center gap-1 font-semibold text-blue-400">
                  <Share className="w-3.5 h-3.5 inline" /> Share
                </span>{" "}
                button in Safari, then select{" "}
                <span className="font-semibold text-white">
                  Add to Home Screen
                </span>
                .
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsDismissed(true)}
            aria-label="Dismiss iOS install instructions"
            className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return null;
};
