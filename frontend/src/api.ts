import type { PipelineResult, TraceStep } from "./types";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api" + path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Request failed (${response.status}). Check that the backend is running.`,
    );
  }
  return response.json() as Promise<T>;
}

export const jsonPost = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
  signal,
});

export async function streamPipeline(
  patientId: string,
  onStep: (step: TraceStep) => void,
  signal: AbortSignal,
): Promise<PipelineResult> {
  const response = await fetch(
    "/api/pipeline/stream",
    jsonPost({ patient_id: patientId }, signal),
  );
  if (!response.ok || !response.body)
    throw new Error(
      "Could not start the pipeline. Check the backend connection.",
    );
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let result: PipelineResult | undefined;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = pending.indexOf("\n\n")) >= 0) {
        const event = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const type = event
          .split("\n")
          .find((line) => line.startsWith("event: "))
          ?.slice(7);
        const data = event
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (!data) continue;
        const payload = JSON.parse(data);
        if (type === "step") onStep(payload);
        if (type === "result") result = payload;
        if (type === "error") throw new Error(payload.message);
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
  if (!result)
    throw new Error(
      "The pipeline ended before returning results. Please retry.",
    );
  return result;
}
