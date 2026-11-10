import { useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import Button from "../common/Button";
import Logo from "../common/Logo";
import ProfileMenu from "../settings/ProfileMenu";
import SettingsMenu from "../settings/SettingsMenu";
import { useAuth } from "../../context/AuthContext";

export default function LandingNav() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <nav className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-5 py-4 sm:px-8">
      <Logo />

      <div className="flex items-center gap-2">
        {user ? (
          <ProfileMenu />
        ) : (
          <Button
            variant="outline"
            icon={<LogIn size={16} />}
            onClick={() => navigate("/login")}
          >
            Login / Register
          </Button>
        )}

        <SettingsMenu />
      </div>
    </nav>
  );
}