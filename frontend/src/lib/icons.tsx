// The Nimbus mark: a puffy cloud scalloped on every edge, including underneath, rather
// than the flat-bottomed weather cloud most icon sets use. Drawn as vector, not shipped
// as an image, so it scales, prints, and recolours straight from the palette.
//
// Built from overlapping circles on purpose: filled circles union into one silhouette
// with no internal seams, which a hand-authored path cannot promise. The rim is the same
// circles drawn slightly larger underneath, so the outline stays in sync automatically.
// The body is `currentColor`; the rim is paper, so the mark also reads on a dark surface.
const PUFFS: [number, number, number][] = [
  [11, 13, 7],
  [20, 10, 8],
  [29, 14, 7],
  [15, 19, 7],
  [25, 19, 7],
  [7, 17, 5],
  [33, 18, 5],
];
const RIM = 1.4;

export function CloudMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size * 0.7}
      viewBox="0 0 40 28"
      className={className}
      role="img"
      aria-label="Nimbus"
    >
      <g fill="var(--paper)">
        {PUFFS.map(([cx, cy, r], i) => (
          <circle key={i} cx={cx} cy={cy} r={r + RIM} />
        ))}
      </g>
      <g fill="currentColor">
        {PUFFS.map(([cx, cy, r], i) => (
          <circle key={i} cx={cx} cy={cy} r={r} />
        ))}
      </g>
    </svg>
  );
}

// stroke uses currentColor, so the icon inherits the text colour around it
export function EyeIcon({ off = false }: { off?: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z" />
      <circle cx="12" cy="12" r="2.8" />
      {off && <line x1="4" y1="20" x2="20" y2="4" />}
    </svg>
  );
}
