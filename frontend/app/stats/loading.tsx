export default function StatsLoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <div
        className="w-10 h-10 rounded-full border-4 border-t-transparent animate-spin"
        style={{ borderColor: 'var(--blue)', borderTopColor: 'transparent' }}
      />
      <p className="text-[0.88rem]" style={{ color: 'var(--text-muted)' }}>
        Loading statistics...
      </p>
    </div>
  );
}