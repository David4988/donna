import { useEffect, useReducer, useRef } from "react";
import { Composer } from "./components/Composer";
import { Conversation } from "./components/Conversation";
import { ErrorBanner } from "./components/ErrorBanner";
import { Sphere } from "./components/Sphere";
import { StatusBar } from "./components/StatusBar";
import { ToolActivity } from "./components/ToolActivity";
import { CoreClient } from "./core-client/client";
import { initialState, reducer } from "./state/reducer";

export function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const client = useRef<CoreClient | null>(null);

  useEffect(() => {
    const c = new CoreClient({
      onMessage: (msg) => dispatch({ kind: "server", msg }),
      onStatus: (status, detail) => dispatch({ kind: "connection", status, detail }),
    });
    client.current = c;
    c.start();
    return () => c.stop();
  }, []);

  const connected = state.connection === "connected";
  return (
    <div className="app">
      <StatusBar state={state} />
      {state.connectionDetail && <p className="conn-detail">{state.connectionDetail}</p>}
      <ErrorBanner message={state.lastError} onDismiss={() => dispatch({ kind: "dismissError" })} />
      <main>
        <div className="left">
          <Sphere state={state.assistantState} />
          <ToolActivity tools={state.tools} />
        </div>
        <div className="right">
          <Conversation messages={state.messages} />
          <Composer
            enabled={connected}
            busy={state.activeTurn !== null}
            onSend={(text) => client.current?.sendText(text)}
            onCancel={() => client.current?.cancel()}
          />
        </div>
      </main>
    </div>
  );
}
