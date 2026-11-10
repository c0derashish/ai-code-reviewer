import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

type ErrorBoundaryProps = { children: ReactNode };
type ErrorBoundaryState = { error: Error | null };

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("VEDIX crashed:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex min-h-full items-center justify-center bg-base p-6 text-main">
        <div className="w-full max-w-2xl rounded-xl border border-danger/40 bg-panel p-6">
          <h1 className="text-lg font-semibold text-danger">Something broke on this page</h1>
          <p className="mt-2 text-sm text-muted">
            Copy the message below. It names the file that failed.
          </p>
          <pre className="mt-4 max-h-80 overflow-auto rounded-md border border-line bg-base p-3 font-mono text-xs">
            {this.state.error.message}
            {"\n\n"}
            {this.state.error.stack}
          </pre>
          <button
            type="button"
            onClick={() => window.location.assign("/")}
            className="mt-4 rounded-md border border-saffron px-4 py-2 text-sm text-saffron hover:bg-saffron/10"
          >
            Back to start
          </button>
        </div>
      </div>
    );
  }
}