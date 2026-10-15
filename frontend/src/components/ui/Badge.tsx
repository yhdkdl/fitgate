import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | "primary"
    | "success"
    | "warning"
    | "danger"
    | "neutral"
    | "secondary"
    | "info"
    | "default";
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "neutral",
  className = "",
  ...props
}) => {
  const variantStyles: Record<string, string> = {
    primary: "bg-primary/15 text-primary border-primary/25",
    success: "bg-success/15 text-success border-success/25",
    warning: "bg-warning/15 text-warning border-warning/25",
    danger: "bg-danger/15 text-danger border-danger/25",
    neutral: "bg-surface-2 text-text-muted border-border",
    secondary: "bg-surface-2 text-text-muted border-border",
    info: "bg-primary/15 text-primary border-primary/25",
    default: "bg-surface-2 text-text-muted border-border",
  };

  const selectedStyle = variantStyles[variant] || variantStyles.neutral;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${selectedStyle} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};
