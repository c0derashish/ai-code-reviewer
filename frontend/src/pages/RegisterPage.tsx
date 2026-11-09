import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { LoaderCircle, UserPlus } from "lucide-react";
import AuthField from "../components/auth/AuthField";
import AuthLayout from "../components/auth/AuthLayout";
import Button from "../components/common/Button";
import Notice from "../components/common/Notice";
import { useAuth } from "../context/AuthContext";
import { AUTH_IS_DEMO } from "../services/authService";
import { checkEmail, checkName, checkPassword } from "../utils/validators";

type Errors = { name?: string; email?: string; password?: string; confirm?: string };

export default function RegisterPage() {
  const { user, register } = useAuth();
  const location = useLocation();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (user) return <Navigate to={from} replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    const next: Errors = {
      name: checkName(name) ?? undefined,
      email: checkEmail(email) ?? undefined,
      password: checkPassword(password) ?? undefined,
      confirm: password !== confirm ? "Passwords do not match." : undefined,
    };
    setErrors(next);
    setFormError(null);
    if (next.name || next.email || next.password || next.confirm) return;

    setLoading(true);
    const result = await register(name, email, password);
    if (!result.ok) {
      setFormError(result.message);
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Keep your analysis history and see how your code improves."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="text-saffron hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <Notice kind="info">
          {AUTH_IS_DEMO
            ? "Demo mode: no real account is created. You are signed in on this device only. The password is never stored or sent."
            : "Accounts need the backend, which is not connected yet."}
        </Notice>

        <AuthField
          id="register-name"
          label="Name"
          value={name}
          onChange={setName}
          error={errors.name}
          autoComplete="name"
          autoFocus
        />
        <AuthField
          id="register-email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={errors.email}
          autoComplete="email"
          placeholder="name@example.com"
        />
        <AuthField
          id="register-password"
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="new-password"
          placeholder="At least 8 characters"
        />
        <AuthField
          id="register-confirm"
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          error={errors.confirm}
          autoComplete="new-password"
        />

        {formError && <Notice kind="error">{formError}</Notice>}

        <Button
          type="submit"
          disabled={loading}
          className="w-full"
          icon={
            loading ? <LoaderCircle size={16} className="animate-spin" /> : <UserPlus size={16} />
          }
        >
          {loading ? "Creating account" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}