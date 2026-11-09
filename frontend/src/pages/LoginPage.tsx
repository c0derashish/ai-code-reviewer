import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { LoaderCircle, LogIn } from "lucide-react";
import AuthField from "../components/auth/AuthField";
import AuthLayout from "../components/auth/AuthLayout";
import Button from "../components/common/Button";
import Notice from "../components/common/Notice";
import { useAuth } from "../context/AuthContext";
import { AUTH_IS_DEMO } from "../services/authService";
import { checkEmail } from "../utils/validators";

type Errors = { email?: string; password?: string };

export default function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // already signed in (or just signed in): go to the page the user wanted
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (user) return <Navigate to={from} replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    const next: Errors = {
      email: checkEmail(email) ?? undefined,
      password: password === "" ? "Enter your password." : undefined,
    };
    setErrors(next);
    setFormError(null);
    if (next.email || next.password) return;

    setLoading(true);
    const result = await login(email, password);
    if (!result.ok) {
      setFormError(result.message);
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to see your analysis history and analytics."
      footer={
        <>
          New to VEDIX?{" "}
          <Link to="/register" className="text-saffron hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <Notice kind="info">
          {AUTH_IS_DEMO
            ? "Demo mode: no real accounts yet. Any valid email signs you in on this device only. The password is never stored or sent."
            : "Accounts need the backend, which is not connected yet."}
        </Notice>

        <AuthField
          id="login-email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={errors.email}
          autoComplete="email"
          placeholder="name@example.com"
          autoFocus
        />
        <AuthField
          id="login-password"
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="current-password"
        />

        {formError && <Notice kind="error">{formError}</Notice>}

        <Button
          type="submit"
          disabled={loading}
          className="w-full"
          icon={
            loading ? <LoaderCircle size={16} className="animate-spin" /> : <LogIn size={16} />
          }
        >
          {loading ? "Signing in" : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  );
}