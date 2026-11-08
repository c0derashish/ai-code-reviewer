import ChakraArt from "./ChakraArt";

export default function HeroBackground() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden opacity-30"
    >
      {/* 1. saffron to black gradient */}
      <div className="hero-gradient absolute inset-0" />

      {/* 2. light rays */}
      <div className="hero-rays absolute inset-0" />

      {/* 3. chakra: centred on small screens, shifted right on large screens */}
      <ChakraArt className="absolute left-1/2 top-1/2 aspect-square w-[min(120vw,900px)] -translate-x-1/2 -translate-y-1/2 text-saffron opacity-40 lg:left-[72%]" />

      {/* 4. manuscript texture */}
      <div className="manuscript-texture absolute inset-0" />

      {/* 5. fade into base colour at the bottom */}
      <div className="absolute inset-x-0 bottom-0 h-40 bg-linear-to-t from-base to-transparent" />
    </div>
  );
}