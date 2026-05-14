import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: '#fff',
        }}>
          <div style={{
            maxWidth: 520, padding: 32, background: '#fef2f2',
            border: '1px solid #fca5a5', borderRadius: 12,
          }}>
            <h2 style={{ margin: '0 0 12px', color: '#dc2626', fontSize: 18 }}>
              Something went wrong
            </h2>
            <pre style={{
              fontSize: 12, color: '#7f1d1d', background: '#fee2e2',
              padding: 12, borderRadius: 6, overflowX: 'auto', whiteSpace: 'pre-wrap',
            }}>
              {this.state.error.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              style={{
                marginTop: 16, background: '#dc2626', color: '#fff',
                border: 'none', borderRadius: 6, padding: '8px 20px',
                fontSize: 13, cursor: 'pointer',
              }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
