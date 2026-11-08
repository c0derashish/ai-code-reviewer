import ChakraMark from "./ChakraMark";

export default function Logo() {
  return (
    <div className="flex items-center gap-3 text-saffron">
      <ChakraMark size={30} />
      <span className="text-lg font-bold tracking-[0.2em] text-main">VEDIX</span>
    </div>
  );
}