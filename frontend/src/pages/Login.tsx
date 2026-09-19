import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { describeError } from "../lib/errorMessages";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      // Deliberately the same generic message regardless of whether the
      // email exists, the password is wrong, or the account is disabled —
      // no user enumeration (Guardrail: Plan Part 2 FR-1 security notes).
      const { code } = describeError(err);
      setError(
        code === "HTTP_429"
          ? "Too many attempts. Please wait a moment and try again."
          : "Invalid email or password.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative isolate flex min-h-screen overflow-hidden bg-canvas">
      {/* Decorative background: gradient mesh + faint grid. Non-interactive. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-40 -top-40 h-[32rem] w-[32rem] animate-drift rounded-full bg-brand-600/30 blur-[120px]" />
        <div className="absolute -bottom-48 right-[-8rem] h-[30rem] w-[30rem] animate-drift rounded-full bg-sky-500/15 blur-[120px] [animation-delay:-9s]" />
        <div className="bg-grid absolute inset-0" />
      </div>

      <div className="mx-auto flex w-full max-w-6xl flex-col justify-center gap-12 px-6 py-12 lg:flex-row lg:items-center lg:gap-16">
        {/* Brand / product panel */}
        <section className="animate-fade-up lg:flex-1">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white shadow-glow">
              G
            </span>
            <span className="text-lg font-semibold tracking-tight text-ink">GeoLegalVault</span>
          </div>

          <h1 className="anim-delay-1 mt-8 animate-fade-up text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl">
            <span className="text-gradient">Document integrity you can verify.</span>
          </h1>
          <p className="anim-delay-2 mt-5 max-w-xl animate-fade-up text-base leading-relaxed text-muted sm:text-lg">
            Geospatially-aware document integrity & lifecycle platform. Every approved version is
            hashed and anchored, so any later change is detectable.
          </p>

          <ul className="anim-delay-3 mt-8 hidden animate-fade-up gap-3 sm:grid">
            {[
              {
                title: "Tamper-evident versions",
                body: "Only a SHA-256 hash is anchored on Ethereum Sepolia. Files never leave private storage.",
              },
              {
                title: "Policy-level geofencing",
                body: "Sensitive actions are checked server-side against authorised zones.",
              },
              {
                title: "Role-based and audited",
                body: "Access follows your role, and every action lands in the audit trail.",
              },
            ].map((f) => (
              <li
                key={f.title}
                className="card card-hover flex items-start gap-3 bg-surface/60 p-4 backdrop-blur"
              >
                <span
                  aria-hidden="true"
                  className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-400 shadow-[0_0_10px_2px_rgb(129_140_248_/_0.6)]"
                />
                <div>
                  <p className="text-sm font-semibold text-ink">{f.title}</p>
                  <p className="mt-0.5 text-sm text-muted">{f.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* Form panel */}
        <section className="anim-delay-2 w-full animate-fade-up lg:w-[26rem] lg:shrink-0">
          <div className="card border-white/10 bg-surface/80 p-8 backdrop-blur-xl shadow-[0_0_60px_-20px_rgb(99_102_241_/_0.5)]">
            <h2 className="text-lg font-semibold tracking-tight text-ink">Welcome back</h2>
            <p className="mt-1 text-sm text-muted">Use your organisation credentials to continue.</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="field-label">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input mt-1"
                />
              </div>
              <div>
                <label htmlFor="password" className="field-label">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input mt-1"
                />
              </div>

              {error && (
                <p
                  role="alert"
                  className="flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    className="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <path strokeLinecap="round" d="M12 8v5M12 16h.01" />
                  </svg>
                  <span>{error}</span>
                </p>
              )}

              <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
                {submitting && (
                  <span
                    aria-hidden="true"
                    className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white"
                  />
                )}
                {submitting ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </div>
          <p className="mt-4 text-center text-xs text-faint">
            Prototype. Geofencing is a policy control, not a location guarantee.
          </p>
        </section>
      </div>
    </div>
  );
}
