import {
  WEEKLY_FOCUS_OPTIONS,
  PLAN_REJECTION_OPTIONS,
  type SelectOption,
} from "./fitnessProfileConstants";

export type PlanOptionItem = SelectOption;

export { WEEKLY_FOCUS_OPTIONS };
export const REJECTION_REASONS_OPTIONS: PlanOptionItem[] =
  PLAN_REJECTION_OPTIONS;
