import React from "react";

export interface FormFieldProps {
  label: string;
  htmlFor?: string;
  id?: string;
  required?: boolean;
  error?: string;
  helperText?: string;
  helpText?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  htmlFor,
  id,
  required = false,
  error,
  helperText,
  helpText,
  children,
  className = "",
}) => {
  const targetId = htmlFor || id;
  const description = helperText || helpText;

  return (
    <div className={`space-y-1.5 ${className}`}>
      <label htmlFor={targetId} className="block text-sm font-medium text-text">
        {label} {required && <span className="text-danger">*</span>}
      </label>
      {children}
      {error ? (
        <p className="text-sm text-danger">{error}</p>
      ) : description ? (
        <p className="text-sm text-text-muted">{description}</p>
      ) : null}
    </div>
  );
};
