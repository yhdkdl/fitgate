import React from "react";
import { Check, X } from "lucide-react";
import { checkPasswordRequirements } from "../../utils/validators";

export interface PasswordChecklistProps {
  password: string;
  confirmPassword?: string;
  className?: string;
}

export const PasswordChecklist: React.FC<PasswordChecklistProps> = ({
  password,
  confirmPassword,
  className = "",
}) => {
  const reqs = checkPasswordRequirements(password, confirmPassword);

  const items = [
    { label: "At least 10 characters", valid: reqs.minLength },
    { label: "Not only digits", valid: reqs.notNumeric },
    { label: "Not a common password", valid: reqs.notCommon },
    ...(confirmPassword !== undefined
      ? [{ label: "Matches password confirmation", valid: reqs.matchesConfirm }]
      : []),
  ];

  return (
    <div
      className={`p-3 bg-surface-2/60 rounded-input border border-border text-sm space-y-1.5 ${className}`}
      aria-live="polite"
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5">
        Password requirements:
      </p>
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2">
          {item.valid ? (
            <Check
              className="w-4 h-4 text-success shrink-0"
              aria-label="Requirement met"
            />
          ) : (
            <X
              className="w-4 h-4 text-text-muted/60 shrink-0"
              aria-label="Requirement not met"
            />
          )}
          <span
            className={
              item.valid ? "text-success font-medium" : "text-text-muted"
            }
          >
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
};
