/* ponytail: layered storybook hills divider — two SVG ridges, no images. */

/** Rolling-hills divider. `top` fills the sky above, `back`/`front` the ridge colors. */
export default function Hills({ top = 'transparent', back = '#7CCB8F', front = '#1FA47A', flip = false }: {
  top?: string; back?: string; front?: string; flip?: boolean;
}) {
  return (
    <div aria-hidden className="w-full leading-[0]" style={{ background: top, transform: flip ? 'scaleY(-1)' : undefined }}>
      <svg viewBox="0 0 1440 120" preserveAspectRatio="none" className="w-full h-[64px] sm:h-[96px] block">
        <path
          d="M0,70 C180,30 340,95 540,65 C740,35 900,90 1100,60 C1260,38 1360,55 1440,45 L1440,120 L0,120 Z"
          fill={back}
        />
        <path
          d="M0,95 C220,60 420,110 640,88 C860,66 1060,108 1260,86 C1340,77 1400,82 1440,78 L1440,120 L0,120 Z"
          fill={front}
        />
      </svg>
    </div>
  );
}
