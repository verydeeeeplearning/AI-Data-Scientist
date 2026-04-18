/**
 * React Error Boundary — catches render errors and shows fallback UI.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { captureRendererException } from '../../observability';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info.componentStack);
    captureRendererException(error, { componentStack: info.componentStack });
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="fixed inset-0 bg-ds-bg flex flex-col items-center justify-center p-8">
          <div className="w-14 h-14 rounded-2xl bg-ds-error/10 flex items-center justify-center mb-4">
            <AlertTriangle size={28} className="text-ds-error" />
          </div>
          <h2 className="text-lg font-semibold text-ds-text mb-2">Something went wrong</h2>
          <p className="text-sm text-ds-muted mb-1 max-w-md text-center">
            An unexpected error occurred in the application.
          </p>
          {this.state.error && (
            <pre className="text-xs text-ds-error/70 bg-ds-surface border border-ds-border rounded-lg p-3 max-w-lg overflow-auto mt-3 mb-4">
              {this.state.error.message}
            </pre>
          )}
          <button
            onClick={this.handleReset}
            className="
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm
              bg-ds-accent text-white hover:bg-ds-accent-hover transition-colors
            "
          >
            <RefreshCw size={14} />
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
