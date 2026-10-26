import React from "react";
import { AlertCircle } from "lucide-react";
import { FormFieldContext } from "./FormFieldContext";

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
    <FormFieldContext.Provider value={{ insideFormField: true }}>
      <div className={`space-y-1.5 ${className}`}>
        <label
          htmlFor={targetId}
          className="block text-sm font-medium text-text"
        >
          {label}{" "}
          {required && (
            <span className="text-danger" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {children}
        {error ? (
          <p
            id={targetId ? `${targetId}-error` : undefined}
            className="text-sm text-danger flex items-center gap-1.5 mt-1"
            role="alert"
          >
            <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </p>
        ) : description ? (
          <p
            id={targetId ? `${targetId}-helper` : undefined}
            className="text-sm text-text-muted mt-1"
          >
            {description}
          </p>
        ) : null}
      </div>
    </FormFieldContext.Provider>
  );
};
