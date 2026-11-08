import { LogIn } from "lucide-react";
import Button from "../common/Button";
import Logo from "../common/Logo";
import SettingsMenu from "../settings/SettingsMenu";

export default function LandingNav() {
  return (
    <nav className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-5 py-4 sm:px-8">
      <Logo />

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          icon={<LogIn size={16} />}
          onClick={() => console.log("Login / Register: built in Phase 8")}
        >
          Login / Register
        </Button>

        <SettingsMenu />
      </div>
    </nav>
  );
}