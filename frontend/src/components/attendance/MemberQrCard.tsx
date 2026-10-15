import React, { useEffect, useState, useRef } from "react";
import QRCode from "qrcode";
import { RefreshCw, Clock, QrCode, AlertCircle } from "lucide-react";
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

      // Generate high-resolution QR data URL
      const dataUrl = await QRCode.toDataURL(data.token, {
        width: 280,
        margin: 2,
        color: {
          dark: "#0F172A", // Dark navy slate for scan reliability
          light: "#FFFFFF",
        },
      });
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
          {/* QR Code Container */}
          <div className="p-3 bg-white rounded-2xl shadow-inner border border-slate-200 inline-block mb-4 transition-transform hover:scale-[1.02]">
            {qrDataUrl && (
              <img
                src={qrDataUrl}
                alt="Personal Member Check-in QR Code"
                className="w-56 h-56 sm:w-64 sm:h-64 object-contain rounded-lg"
              />
            )}
          </div>

          {/* Countdown & Timer Bar */}
          <div className="w-full max-w-xs mb-4">
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
          <div className="w-full max-w-xs flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fetchToken(true)}
              disabled={refreshing}
              className="flex-1 min-h-[44px] flex items-center justify-center gap-2 text-xs font-semibold"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
              {refreshing ? "Refreshing..." : "Refresh Token"}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
};
