import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { api, type VerifyStart } from "../api";
import { Button, Spinner } from "./ui";

/** Prove ownership of a handle by submitting a compilation error to a problem we pick. */
export function VerifyDialog({ handle, onClose }: { handle: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [session, setSession] = useState<VerifyStart | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    dialog.current?.showModal();
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const start = useMutation({
    mutationFn: () => api.verifyStart(handle),
    onSuccess: (s) => {
      setSession(s);
      setMessage(null);
    },
    onError: (e: Error) => setMessage(e.message),
  });
  const check = useMutation({
    mutationFn: () => api.verifyCheck(session!.verification_id),
    onSuccess: async (r) => {
      if (r.verified) {
        await qc.invalidateQueries({ queryKey: ["me"] });
        onClose();
        navigate("/plan");
      } else setMessage(r.message);
    },
    onError: (e: Error) => setMessage(e.message),
  });

  const left = session ? Math.max(0, Math.round((new Date(session.expires_at).getTime() - now) / 1000)) : 0;
  const expired = session && left === 0;

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      className="card pop m-auto w-[min(32rem,calc(100vw-2rem))] p-0 text-ink backdrop:bg-black/50 backdrop:backdrop-blur-sm"
      aria-labelledby="verify-title"
    >
      <div className="p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="bg-gradient grid size-10 place-items-center rounded-xl text-white">
            <BadgeCheck size={20} aria-hidden />
          </span>
          <h2 id="verify-title" className="text-lg font-semibold">
            Verify {handle}
          </h2>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-ink-2">
          Codeforces doesn't offer sign-in for other apps, so we use the method common in CF tools:
          you submit a <b>compilation error</b> to a problem we pick. Only the account's owner can do
          that, and a compilation error never counts against you.
        </p>

        {!session && (
          <Button className="mt-5" onClick={() => start.mutate()} disabled={start.isPending}>
            {start.isPending ? <Spinner /> : "Start verification"}
          </Button>
        )}

        {session && (
          <ol className="mt-5 space-y-3 text-sm [&>li]:flex [&>li]:gap-3">
            <li className="rise">
              <Step n={1} />
              <span>
                Open{" "}
              <a href={session.submit_url ?? session.problem.url ?? undefined} target="_blank" rel="noreferrer" className="font-medium text-accent-ink underline">
                problem {session.problem.id} ({session.problem.name})
              </a>{" "}
              on Codeforces while logged in as <b>{session.handle}</b>.
              </span>
            </li>
            <li className="rise" style={{ "--d": "80ms" } as React.CSSProperties}>
              <Step n={2} />
              <span>
                Submit anything that won't compile, for example the single line{" "}
                <code className="rounded bg-surface-2 px-1">upsolve</code> in C++.
              </span>
            </li>
            <li className="rise" style={{ "--d": "160ms" } as React.CSSProperties}>
              <Step n={3} />
              <span>
                Wait for the "Compilation error" verdict, then press <b>Check</b>.
              </span>
            </li>
          </ol>
        )}

        {message && (
          <p role="alert" className="mt-4 text-sm text-bad">
            {message}
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <span className="tabular text-xs text-muted">
            {session && !expired && `Expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`}
            {expired && "This attempt expired."}
          </span>
          <div className="flex gap-2">
            <Button kind="ghost" onClick={() => dialog.current?.close()}>
              Cancel
            </Button>
            {session && !expired && (
              <Button onClick={() => check.mutate()} disabled={check.isPending}>
                {check.isPending ? <Spinner /> : "Check"}
              </Button>
            )}
            {expired && <Button onClick={() => start.mutate()}>Start again</Button>}
          </div>
        </div>
      </div>
    </dialog>
  );
}

function Step({ n }: { n: number }) {
  return (
    <span className="bg-gradient tabular grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold text-white">
      {n}
    </span>
  );
}
