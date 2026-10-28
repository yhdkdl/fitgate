import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  title?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class SectionErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("SectionErrorBoundary caught an error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="bg-surface border border-danger/30 rounded-card p-4 text-text space-y-2 my-2">
          <div className="flex items-center gap-2 text-danger font-medium text-sm">
            <span>⚠️</span>
            <span>{this.props.title || "Section Error"}</span>
          </div>
          <p className="text-xs text-text-muted">
            This dashboard section encountered an unexpected error. Other
            sections remain operational.
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="text-xs text-primary hover:underline font-medium min-h-[32px] inline-flex items-center"
          >
            Retry loading section
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
