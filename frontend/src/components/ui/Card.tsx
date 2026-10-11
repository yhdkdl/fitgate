import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "surface" | "surface-2";
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = "surface",
  className = "",
  ...props
}) => {
  const bgClass = variant === "surface" ? "bg-surface" : "bg-surface-2";
  return (
    <div
      className={`${bgClass} border border-border rounded-card p-6 transition-all ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
