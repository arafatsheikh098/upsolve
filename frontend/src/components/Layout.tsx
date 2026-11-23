import { Suspense, useState, type FormEvent } from "react";
import {
  BookOpen,
  CalendarCheck,
  GitCompareArrows,
  LogOut,
  Monitor,
  Moon,
  Search,
  Sun,
  TrendingUp,
} from "lucide-react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useLogout, useMe, useTheme, type Theme } from "../hooks";
import { Button, Spinner } from "./ui";

export function HandleSearch({ big = false, initial = "" }: { big?: boolean; initial?: string }) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const h = value.trim();
    if (!/^[A-Za-z0-9_.-]{3,24}$/.test(h)) {
      setError("Codeforces handles are 3–24 letters, digits, '_', '-' or '.'.");
      return;
    }
    setError(null);
    navigate(`/u/${encodeURIComponent(h)}`);
  };
  return (
    <form onSubmit={submit} className="w-full" role="search">
      <div
        className={`group flex items-center gap-2 rounded-2xl border border-line bg-surface p-1.5 transition-shadow focus-within:border-accent focus-within:shadow-[0_0_0_4px_var(--accent-wash)] ${
          big ? "shadow-[var(--lift)]" : ""
        }`}
      >
        <Search size={big ? 20 : 16} className="ml-2 shrink-0 text-muted" aria-hidden />
        <label htmlFor={big ? "handle-big" : "handle"} className="sr-only">
          Codeforces handle
        </label>
        <input
          id={big ? "handle-big" : "handle"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter a Codeforces handle"
          autoComplete="off"
          spellCheck={false}
          className={`min-w-0 flex-1 bg-transparent text-ink placeholder:text-muted focus:outline-none ${
            big ? "py-2 text-lg" : "py-1 text-sm"
          }`}
        />
        <Button type="submit" className={big ? "px-5 py-2.5 text-base" : ""}>
          Analyze
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-bad">{error}</p>}
    </form>
  );
}

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "Auto theme", icon: Monitor },
  { value: "light", label: "Light theme", icon: Sun },
  { value: "dark", label: "Dark theme", icon: Moon },
];

function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const i = THEMES.findIndex((t) => t.value === theme);
  const current = THEMES[i];
  const next = THEMES[(i + 1) % THEMES.length];
  const Icon = current.icon;
  return (
    <button
      onClick={() => setTheme(next.value)}
      className="grid size-9 place-items-center rounded-xl border border-line bg-surface text-ink-2 transition-colors hover:text-ink"
      aria-label={`${current.label}. Switch to ${next.label.toLowerCase()}`}
      title={current.label}
    >
      <Icon size={16} key={current.value} className="pop" />
    </button>
  );
}

export function Logo() {
  return (
    <Link to="/" className="group flex items-center gap-2 font-semibold tracking-tight text-ink">
      <span className="bg-gradient grid size-8 place-items-center rounded-xl text-white shadow-[0_6px_16px_-6px_var(--accent)] transition-transform group-hover:-rotate-6 group-hover:scale-105">
        <TrendingUp size={17} strokeWidth={2.6} aria-hidden />
      </span>
      <span className="text-lg">Upsolve</span>
    </Link>
  );
}

const NAV = [
  { to: "/plan", label: "My plan", icon: CalendarCheck },
  { to: "/compare", label: "Compare", icon: GitCompareArrows },
  { to: "/how-it-works", label: "How it works", icon: BookOpen },
];

export function Layout() {
  const me = useMe();
  const logout = useLogout();
  const location = useLocation();
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `inline-flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
      isActive ? "bg-accent-wash text-accent-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
    }`;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-page/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
          <Logo />
          <nav
            className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto sm:flex-1"
            aria-label="Main"
          >
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={navClass}>
                <Icon size={15} aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {me.data && (
              <>
                <Link
                  to={`/u/${me.data.handle}`}
                  className="flex items-center gap-2 rounded-xl px-2 py-1 text-sm font-medium text-ink hover:bg-surface-2"
                >
                  <span className="bg-gradient grid size-6 place-items-center rounded-full text-[11px] font-bold uppercase text-white">
                    {me.data.handle[0]}
                  </span>
                  <span className="hidden sm:inline">{me.data.handle}</span>
                </Link>
                <button
                  onClick={logout}
                  className="grid size-9 place-items-center rounded-xl text-ink-2 hover:bg-surface-2 hover:text-ink"
                  aria-label="Sign out"
                  title="Sign out"
                >
                  <LogOut size={16} aria-hidden />
                </button>
              </>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 pt-6">
        <Suspense fallback={<Spinner label="Loading…" />}>
          <div key={location.pathname} className="rise">
            <Outlet />
          </div>
        </Suspense>
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted">
          <span>
            Upsolve is an independent open-source project. It isn't affiliated with Codeforces and only
            reads public data from the Codeforces API.
          </span>
          <Link to="/how-it-works" className="hover:text-ink">
            How the model works
          </Link>
        </div>
      </footer>
    </div>
  );
}
