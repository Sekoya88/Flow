"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { logger } from "@/lib/logger";

type Props = { children: ReactNode; label?: string };

type State = { error: Error | null };

export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logger.error("[RouteErrorBoundary] render crash", { label: this.props.label, error: error.message, stack: info.componentStack ?? "" });
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-2xl space-y-4 py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{this.props.label ?? "Something broke"}</AlertTitle>
            <AlertDescription className="space-y-2">
              <p className="font-mono text-xs break-all">{this.state.error.message}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => this.setState({ error: null })}>
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      );
    }
    return this.props.children;
  }
}
