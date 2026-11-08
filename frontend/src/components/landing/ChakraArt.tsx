type ChakraArtProps = {
  className?: string;
};

// list of angles evenly spaced around a circle, e.g. angles(4) = [0, 90, 180, 270]
function angles(count: number) {
  return Array.from({ length: count }, (_, i) => (360 / count) * i);
}

export default function ChakraArt({ className = "" }: ChakraArtProps) {
  return (
    <svg
      viewBox="-200 -200 400 400"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="0.7"
    >
      {/* Outer serrated ring. Turns slowly one way. */}
      <g className="chakra-spin">
        {angles(72).map((a) => (
          <path
            key={a}
            d="M-7.5,-176 L0,-196 L7.5,-176 Z"
            transform={`rotate(${a})`}
          />
        ))}
        <circle r="176" />
        <circle r="170" strokeOpacity="0.6" />
      </g>

      {/* Inner mandala. Turns the other way. */}
      <g className="chakra-spin-reverse">
        {/* 24 spokes with a dot near the rim */}
        {angles(24).map((a) => (
          <g key={a} transform={`rotate(${a})`}>
            <line x1="0" y1="-30" x2="0" y2="-170" strokeOpacity="0.5" />
            <circle cy="-146" r="2.4" fill="currentColor" stroke="none" />
          </g>
        ))}

        {/* ring that holds the petals */}
        <circle r="122" />
        <circle r="66" />

        {/* 12 lotus petals */}
        {angles(12).map((a) => (
          <path
            key={a}
            d="M0,-66 C14,-82 14,-104 0,-122 C-14,-104 -14,-82 0,-66 Z"
            transform={`rotate(${a})`}
          />
        ))}

        {/* centre */}
        <circle r="30" />
        <circle r="14" />
        <circle r="8" fill="var(--gold)" stroke="none" />
      </g>
    </svg>
  );
}