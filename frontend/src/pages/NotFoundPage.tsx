import { ButtonLink } from "../components/ui";

export function NotFoundPage() {
  return (
    <div className="py-24 text-center">
      <h1 className="text-2xl font-semibold text-ink">Page not found</h1>
      <p className="mt-2 text-ink-2">That page doesn't exist.</p>
      <div className="mt-6">
        <ButtonLink to="/">Go home</ButtonLink>
      </div>
    </div>
  );
}
