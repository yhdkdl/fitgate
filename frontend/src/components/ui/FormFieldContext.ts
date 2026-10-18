import { createContext } from "react";

export interface FormFieldContextValue {
  insideFormField: boolean;
}

export const FormFieldContext = createContext<FormFieldContextValue>({
  insideFormField: false,
});
