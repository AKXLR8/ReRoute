import { Component, type ReactNode } from 'react';

/* One crashing chart must not take down the whole dashboard. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="card p-6 mt-6 text-center">
          <p className="text-sm font-medium text-white mb-1">Something broke rendering this view</p>
          <p className="text-xs text-[#6B7280]">Try reloading. Your data is safe.</p>
        </div>
      );
    }
    return this.props.children;
  }
}
