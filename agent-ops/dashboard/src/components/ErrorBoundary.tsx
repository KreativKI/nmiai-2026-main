import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="flex items-center justify-center h-full p-8">
            <div className="rounded-2xl bg-red-50/80 border border-red-200 p-6 max-w-lg">
              <h3 className="text-lg font-bold text-red-800 font-[Fredoka]">
                Something went wrong
              </h3>
              <p className="text-sm text-red-600 mt-2 font-mono break-all">
                {this.state.error.message}
              </p>
              <button
                onClick={() => this.setState({ error: null })}
                className="mt-4 px-4 py-2 rounded-full bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
