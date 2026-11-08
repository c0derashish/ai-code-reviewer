type ChakraMarkProps = {
  size?: number;
};

export default function ChakraMark({ size = 28 }: ChakraMarkProps) {
  return (
    <img
      src="/favicon.svg"
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}