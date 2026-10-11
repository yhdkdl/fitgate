import React from "react";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = "info",
  title,
  className = "",
  ...props
}) => {
  const variantStyles = {
    info: "bg-surface-2 border-border text-text",
    success: "bg-success/10 border-success/30 text-success",
    warning: "bg-warning/10 border-warning/30 text-warning",
    danger: "bg-danger/10 border-danger/30 text-danger",
  };

  return (
    <div
      role="alert"
      className={`rounded-card border p-4 text-base ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {title && <h4 className="font-semibold mb-1 text-base">{title}</h4>}
      <div>{children}</div>
    </div>
  );
};
