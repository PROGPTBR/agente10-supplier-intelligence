/**
 * IAgentics brand mark — node graph (6 circles, 5 connectors) + wordmark.
 * The icon and the wordmark gradient render in pure SVG so the asset
 * scales perfectly and inherits the sidebar's white-on-violet treatment.
 */

export function IAgenticsLogo({
  size = 28,
  tone = "light",
  withWordmark = true,
}: {
  size?: number;
  tone?: "light" | "ink";
  withWordmark?: boolean;
}) {
  const stroke = tone === "light" ? "#A4C5FF" : "#5B3FE5";
  const wordColor = tone === "light" ? "#FFFFFF" : "var(--r-ink)";
  return (
    <span className="inline-flex items-center gap-3">
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 60"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        {/* connectors */}
        <g stroke={stroke} strokeWidth={2.5} strokeLinecap="round">
          <line x1="20" y1="8" x2="20" y2="22" />
          <line x1="20" y1="8" x2="36" y2="22" />
          <line x1="8" y1="38" x2="20" y2="22" />
          <line x1="20" y1="38" x2="20" y2="22" />
          <line x1="36" y1="22" x2="36" y2="38" />
          <line x1="20" y1="38" x2="36" y2="38" />
        </g>
        {/* nodes */}
        <g stroke={stroke} strokeWidth={2.5} fill="none">
          <circle cx="20" cy="8" r="5" />
          <circle cx="20" cy="22" r="5" />
          <circle cx="36" cy="22" r="5" />
          <circle cx="8" cy="38" r="5" />
          <circle cx="20" cy="38" r="5" />
          <circle cx="36" cy="38" r="5" />
        </g>
      </svg>
      {withWordmark && (
        <span
          className="r-display text-xl tracking-tight"
          style={{
            color: wordColor,
            backgroundImage:
              tone === "ink"
                ? "linear-gradient(90deg, #7B6FFF 0%, #5B3FE5 60%, #2C1666 100%)"
                : undefined,
            backgroundClip: tone === "ink" ? "text" : undefined,
            WebkitBackgroundClip: tone === "ink" ? "text" : undefined,
            WebkitTextFillColor: tone === "ink" ? "transparent" : undefined,
          }}
        >
          IAgentics
        </span>
      )}
    </span>
  );
}
