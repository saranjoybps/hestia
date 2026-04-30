'use client';

type LoadingStateProps = {
  label?: string;
  className?: string;
};

export function LoadingState({ label = 'Loading', className = '' }: LoadingStateProps) {
  return (
    <div className={`flex min-h-[260px] w-full items-center justify-center ${className}`}>
      <div className="flex flex-col items-center gap-2">
        <div
          className="h-11 w-11 rounded-full border-[3px] border-blue-100 border-t-blue-600 animate-spin"
          aria-hidden="true"
        />
        <p className="text-sm font-medium leading-none text-blue-600">{label}</p>
      </div>
    </div>
  );
}
