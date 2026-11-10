import { Link } from "react-router-dom";
import { ChartColumn, History, LogOut, User as UserIcon } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { usePopover } from "../../hooks/usePopover";

const ITEMS: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/history", label: "Analysis History", icon: History },
  { to: "/analytics", label: "Analytics", icon: ChartColumn },
  { to: "/account", label: "Account information", icon: UserIcon },
];

const ITEM_CLASS =
  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-main transition hover:bg-saffron/10 hover:text-saffron";

export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const { open, setOpen, ref } = usePopover();

  if (!user) return null;

  const initial = user.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Profile menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-saffron/60 bg-saffron/15 text-sm font-semibold text-saffron transition hover:bg-saffron/25"
      >
        {initial}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Profile"
          className="modal-in glass-panel absolute right-0 top-full z-30 mt-2 w-64 max-w-[calc(100vw-2rem)] rounded-xl border p-2 shadow-2xl [--glass-alpha:70%]"
        >
          <div className="border-b border-line px-3 pb-3 pt-2">
            <p className="truncate font-medium">{user.name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
          </div>

          <div className="py-1">
            {ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={ITEM_CLASS}
                >
                  <Icon size={16} />
                  {item.label}
                </Link>
              );
            })}
          </div>

          <div className="border-t border-line pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className={ITEM_CLASS}
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </div>
      )}
    </div>
  );
}