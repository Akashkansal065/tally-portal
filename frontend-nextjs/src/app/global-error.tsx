'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-background text-foreground min-h-screen flex items-center justify-center p-4">
        <div className="max-w-md w-full p-6 bg-card rounded-lg shadow-lg text-center space-y-4 border border-border">
          <h2 className="text-xl font-bold text-destructive">Something went wrong!</h2>
          <p className="text-sm text-muted-foreground">
            {error?.message || "An unexpected application error occurred."}
          </p>
          <button
            onClick={() => reset()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
