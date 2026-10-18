import React, { useEffect, useState, useRef } from "react";
import QRCode from "qrcode";
import {
  RefreshCw,
  Clock,
  QrCode,
  AlertCircle,
  Copy,
  Check,
  Maximize2,
  X,
} from "lucide-react";
import {
  getMemberQrToken,
  type MemberQrTokenResponse,
} from "../../api/attendance";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import { Alert } from "../ui/Alert";

interface MemberQrCardProps {
  memberStatus?: string;
  onRefresh?: () => void;
}

export const MemberQrCard: React.FC<MemberQrCardProps> = ({ memberStatus }) => {
  const [tokenData, setTokenData] = useState<MemberQrTokenResponse | null>(
    null
  );
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorReason, setErrorReason] = useState<string | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(90);
  const [copied, setCopied] = useState(false);
  const [isEnlarged, setIsEnlarged] = useState(false);

  const handleCopyCode = async () => {
    if (!tokenData?.token) return;
    try {
      await navigator.clipboard.writeText(tokenData.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard write error fallback
    }
  };

  const fetchToken = async (isManual = false) => {
    if (isManual) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    setErrorReason(null);

    try {
      const data = await getMemberQrToken();
      setTokenData(data);

      // Generate sharp SVG QR with lowest error correction level 'L' and >=4 squares margin
      const svgString = await QRCode.toString(data.token, {
        type: "svg",
        errorCorrectionLevel: "L",
        margin: 4,
        color: {
          dark: "#000000",
          light: "#FFFFFF",
        },
      });
      const dataUrl = `data:image/svg+xml;utf8,${encodeURIComponent(svgString)}`;
      setQrDataUrl(dataUrl);

      // Compute seconds remaining
      const expiryTime = new Date(data.expires_at).getTime();
      const nowTime = Date.now();
      const remaining = Math.max(0, Math.floor((expiryTime - nowTime) / 1000));
      setSecondsRemaining(remaining || 90);
    } catch (err: unknown) {
      const errorObj = err as {
        data?: { detail?: string; reason?: string };
        message?: string;
      };
      const detail =
        errorObj.data?.detail ||
        errorObj.message ||
        "Failed to issue QR token.";
      const reason = errorObj.data?.reason || "error";
      setError(detail);
      setErrorReason(reason);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchToken();
  }, []);

  // Countdown timer & auto-refresh
  const fetchTokenRef = useRef(fetchToken);
  fetchTokenRef.current = fetchToken;

  useEffect(() => {
    if (!tokenData || error) return;

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          // Window expired, auto-refresh fresh token
          fetchTokenRef.current(false);
          return 90;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [tokenData, error]);

  // Escape key closes enlarged view
  useEffect(() => {
    if (!isEnlarged) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsEnlarged(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isEnlarged]);

  const percentageRemaining = Math.min(
    100,
    Math.max(0, (secondsRemaining / 90) * 100)
  );

  return (
    <Card className="bg-surface border-border flex flex-col items-center p-6 text-center shadow-lg relative overflow-hidden">
      <div className="w-full flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <QrCode className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-bold text-text">Check-in QR Pass</h2>
        </div>
        {memberStatus && (
          <Badge
            variant={
              memberStatus === "active"
                ? "primary"
                : memberStatus === "frozen"
                  ? "secondary"
                  : "danger"
            }
          >
            {memberStatus.toUpperCase()}
          </Badge>
        )}
      </div>

      <p className="text-xs text-text-muted mb-6 max-w-xs">
        Present this dynamic QR code at the front desk or turnstile. Rotates
        automatically every 90 seconds.
      </p>

      {loading ? (
        <div className="h-64 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <span className="text-xs text-text-muted">
            Generating secure asymmetric pass...
          </span>
        </div>
      ) : error ? (
        <div className="w-full space-y-4 my-4">
          <Alert variant="danger">
            <div className="flex flex-col items-start text-left gap-1">
              <span className="font-semibold flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-danger" />
                Pass Unavailable ({errorReason})
              </span>
              <span className="text-xs">{error}</span>
            </div>
          </Alert>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchToken(true)}
            className="min-h-[44px] w-full flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </Button>
        </div>
      ) : (
        <div className="flex flex-col items-center w-full">
          {/* QR Code Container: at least 280px wide up to 420px, sharp SVG, black on plain white */}
          <div className="w-[280px] sm:w-[340px] md:w-[380px] max-w-[420px] aspect-square p-2 bg-white rounded-2xl shadow-inner border border-slate-200 flex items-center justify-center mb-4 transition-transform hover:scale-[1.01]">
            {qrDataUrl && (
              <img
                src={qrDataUrl}
                alt="Personal Member Check-in QR Code"
                className="w-full h-full object-contain"
              />
            )}
          </div>

          {/* Countdown & Timer Bar */}
          <div className="w-full max-w-sm mb-4">
            <div className="flex items-center justify-between text-xs text-text-muted mb-1.5 font-medium">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-primary" />
                Valid for {secondsRemaining}s
              </span>
              <span>{Math.round(percentageRemaining)}%</span>
            </div>

            <div className="w-full h-2 bg-surface-2 rounded-full overflow-hidden border border-border/50">
              <div
                className={`h-full transition-all duration-1000 rounded-full ${
                  secondsRemaining < 15
                    ? "bg-danger animate-pulse"
                    : secondsRemaining < 30
                      ? "bg-amber-500"
                      : "bg-primary"
                }`}
                style={{ width: `${percentageRemaining}%` }}
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="w-full max-w-sm flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsEnlarged(true)}
              disabled={!qrDataUrl}
              className="flex-1 min-h-[44px] flex items-center justify-center gap-1.5 text-xs font-semibold"
            >
              <Maximize2 className="w-3.5 h-3.5" />
              Enlarge
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fetchToken(true)}
              disabled={refreshing}
              className="flex-1 min-h-[44px] flex items-center justify-center gap-1.5 text-xs font-semibold"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
              {refreshing ? "Refreshing..." : "Refresh"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleCopyCode}
              disabled={!tokenData?.token}
              className="flex-1 min-h-[44px] flex items-center justify-center gap-1.5 text-xs font-semibold"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  Copy code
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Full-screen Enlarge View */}
      {isEnlarged && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Enlarged QR Pass"
          className="fixed inset-0 z-50 bg-white flex flex-col items-center justify-between p-6 sm:p-8"
        >
          {/* Header */}
          <div className="w-full max-w-md flex items-center justify-between">
            <div className="flex items-center gap-2">
              <QrCode className="w-6 h-6 text-primary" />
              <h2 className="text-xl font-bold text-slate-900">Entrance QR Pass</h2>
            </div>
            <button
              type="button"
              onClick={() => setIsEnlarged(false)}
              className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors p-2"
              aria-label="Close enlarged pass"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Large QR in center on plain white background */}
          <div className="w-full max-w-[420px] aspect-square flex items-center justify-center my-auto p-4 bg-white">
            {qrDataUrl && (
              <img
                src={qrDataUrl}
                alt="Enlarged Member QR Code"
                className="w-full h-full max-w-[420px] max-h-[420px] object-contain"
              />
            )}
          </div>

          {/* Countdown & Close */}
          <div className="w-full max-w-md flex flex-col items-center gap-4">
            <div className="w-full">
              <div className="flex items-center justify-between text-sm text-slate-700 mb-1.5 font-semibold">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-primary" />
                  Valid for {secondsRemaining}s
                </span>
                <span>{Math.round(percentageRemaining)}%</span>
              </div>
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div
                  className={`h-full transition-all duration-1000 rounded-full ${
                    secondsRemaining < 15
                      ? "bg-danger animate-pulse"
                      : secondsRemaining < 30
                        ? "bg-amber-500"
                        : "bg-primary"
                  }`}
                  style={{ width: `${percentageRemaining}%` }}
                />
              </div>
            </div>

            <Button
              variant="secondary"
              size="md"
              onClick={() => setIsEnlarged(false)}
              className="w-full min-h-[44px] font-semibold text-sm"
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
};
