import { Upload, GitBranch } from "lucide-react";
import Button from "../common/Button";

type HeroProps = {
  onUploadClick: () => void;
  onConnectClick: () => void;
};

export default function Hero({ onUploadClick, onConnectClick }: HeroProps) {
  return (
    <section className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center lg:items-start lg:px-20 lg:text-left">
      <h1 className="title-glass pl-[0.14em] text-7xl font-extrabold tracking-[0.14em] sm:text-8xl md:text-9xl lg:pl-0">
        VEDIX
      </h1>

      <p className="text-glass mt-4 pl-[0.3em] text-lg font-normal tracking-[0.3em] sm:text-2xl lg:pl-0">
        An AI Code Reviewer
      </p>

      <p className="mt-6 max-w-md text-base text-main/80 sm:text-lg">
        Where ancient wisdom meets modern intelligence.
      </p>

      <div className="mt-10 flex flex-col gap-4 sm:flex-row">
        <Button size="lg" icon={<Upload size={18} />} onClick={onUploadClick}>
          Upload your code
        </Button>
        <Button
          size="lg"
          variant="outline"
          icon={<GitBranch size={18} />}
          onClick={onConnectClick}
        >
          Connect to repository
        </Button>
      </div>
    </section>
  );
}