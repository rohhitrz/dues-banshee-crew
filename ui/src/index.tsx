import { useAppApi, useChatLauncher } from "@kirocrew/app-sdk";
import { useEffect, useRef, useState } from "react";
import { loadSummary } from "./api";
import { askMessage } from "./ask";
import Graveyard, { type ViewState } from "./Graveyard";
import type { Tombstone } from "./types";

export default function GraveyardPage() {
  const api = useAppApi();
  const { openChat } = useChatLauncher();
  const [demo, setDemo] = useState(false);
  const [state, setState] = useState<ViewState>({ kind: "loading" });

  // Keep the latest client without making it an effect dependency.
  const apiRef = useRef(api);
  apiRef.current = api;

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    loadSummary(apiRef.current, demo).then((result) => {
      if (!cancelled) setState(result);
    });
    return () => {
      cancelled = true;
    };
  }, [demo]);

  // Opens an unsent chat draft only; no Backend request, no ladder trigger.
  const onAsk = (t: Tombstone) => {
    if (t.taxBomb === null) return;
    openChat({ message: askMessage({ ...t, taxBomb: t.taxBomb }), autoSend: false });
  };

  return <Graveyard state={state} demo={demo} onDemoChange={setDemo} onAsk={onAsk} />;
}
