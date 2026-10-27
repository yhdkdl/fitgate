import React, { useContext } from "react";
import { AlertCircle } from "lucide-react";
import { FormFieldContext } from "./FormFieldContext";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ error, helperText, className = "", id, ...props }, ref) => {
    const { insideFormField } = useContext(FormFieldContext);

    return (
      <div className="w-full">
        <input
          ref={ref}
          id={id}
          className={`w-full min-h-[44px] px-3.5 py-2.5 bg-surface text-text placeholder-text-muted border rounded-input transition-colors text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50 disabled:cursor-not-allowed ${
            error
              ? "border-danger focus-visible:outline-danger"
              : "border-border hover:border-border/80"
          } ${className}`}
          aria-invalid={Boolean(error)}
          aria-describedby={
            error && id
              ? `${id}-error`
              : helperText && id
                ? `${id}-helper`
                : undefined
          }
          {...props}
        />
        {!insideFormField && error ? (
          <p
            id={id ? `${id}-error` : undefined}
            className="mt-1.5 text-sm text-danger flex items-center gap-1.5"
            role="alert"
          >
            <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </p>
        ) : !insideFormField && helperText ? (
          <p
            id={id ? `${id}-helper` : undefined}
            className="mt-1.5 text-sm text-text-muted"
          >
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = "Input";
