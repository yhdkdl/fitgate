import React from "react";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "danger" | "error";
  title?: string;
  onClose?: () => void;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = "info",
  title,
  className = "",
  onClose,
  ...props
}) => {
  const variantStyles: Record<string, string> = {
    info: "bg-surface-2 border-border text-text",
    success: "bg-success/10 border-success/30 text-success",
    warning: "bg-warning/10 border-warning/30 text-warning",
    danger: "bg-danger/10 border-danger/30 text-danger",
    error: "bg-danger/10 border-danger/30 text-danger",
  };

  const selectedStyle = variantStyles[variant] || variantStyles.info;

  return (
    <div
      role="alert"
      className={`rounded-card border p-4 text-base relative ${selectedStyle} ${className}`}
      {...props}
    >
      {title && <h4 className="font-semibold mb-1 text-base">{title}</h4>}
      <div>{children}</div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 text-text-muted hover:text-text p-1 min-h-[32px] min-w-[32px] flex items-center justify-center rounded"
          aria-label="Close alert"
        >
          ×
        </button>
      )}
    </div>
  );
};
