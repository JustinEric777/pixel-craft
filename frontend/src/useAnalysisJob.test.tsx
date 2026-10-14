import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelAnalysisJob,
  enqueueAnalysisJob,
  getAnalysisJob,
  getAnalysisJobResult,
  getLatestAnalysisJob,
  getProject,
  type AnalysisJob,
} from "./api";
import { useAnalysisJob } from "./useAnalysisJob";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  enqueueAnalysisJob: vi.fn(),
  getAnalysisJob: vi.fn(),
  getAnalysisJobResult: vi.fn(),
  getLatestAnalysisJob: vi.fn(),
  cancelAnalysisJob: vi.fn(),
  getProject: vi.fn(),
}));

function job(status: AnalysisJob["status"], id = "job-1"): AnalysisJob {
  return {
    id,
    project_id: "project-1",
    status,
    requested_models: ["one", "two"],
    completed_models: status === "queued" ? {} : { one: { status: "ready" } },
  };
}

async function runPoll(milliseconds = 10) {
  await act(async () => {
    vi.advanceTimersByTime(milliseconds);
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useAnalysisJob", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(enqueueAnalysisJob).mockReset();
    vi.mocked(getAnalysisJob).mockReset();
    vi.mocked(getAnalysisJobResult).mockReset();
    vi.mocked(getLatestAnalysisJob).mockReset();
    vi.mocked(getLatestAnalysisJob).mockResolvedValue(null);
    vi.mocked(cancelAnalysisJob).mockReset();
    vi.mocked(getProject).mockReset();
  });

  afterEach(() => vi.useRealTimers());

  it("polls to success, reads the complete result, and reloads the project", async () => {
    vi.mocked(enqueueAnalysisJob).mockResolvedValue(job("queued"));
    vi.mocked(getAnalysisJob).mockResolvedValue(job("succeeded"));
    vi.mocked(getAnalysisJobResult).mockResolvedValue({
      job_id: "job-1",
      project_id: "project-1",
      status: "succeeded",
      complete: true,
      models: { one: {}, two: {} },
    });
    vi.mocked(getProject).mockResolvedValue({ source: { path: "source.jpg" }, layers: [], edits: [] });
    const { result } = renderHook(() => useAnalysisJob("project-1", 10));

    await act(() => result.current.start());
    await runPoll();

    expect(result.current.view.status).toBe("succeeded");
    expect(result.current.view.project?.source.path).toBe("source.jpg");
    expect(getAnalysisJobResult).toHaveBeenCalledWith("job-1");
    expect(getProject).toHaveBeenCalledWith("project-1");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels an active job and stops polling", async () => {
    vi.mocked(enqueueAnalysisJob).mockResolvedValue(job("running"));
    vi.mocked(cancelAnalysisJob).mockResolvedValue(job("cancelled"));
    vi.mocked(getAnalysisJobResult).mockResolvedValue({
      job_id: "job-1",
      project_id: "project-1",
      status: "cancelled",
      complete: true,
      models: { one: {} },
    });
    const { result } = renderHook(() => useAnalysisJob("project-1", 10));

    await act(() => result.current.start());
    await act(() => result.current.cancel());
    await runPoll(50);

    expect(result.current.view.status).toBe("cancelled");
    expect(getAnalysisJob).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("clears polling on unmount without cancelling the server job", async () => {
    vi.mocked(enqueueAnalysisJob).mockResolvedValue(job("queued"));
    const { result, unmount } = renderHook(() => useAnalysisJob("project-1", 10));
    await act(() => result.current.start());

    unmount();
    await runPoll(50);

    expect(getAnalysisJob).not.toHaveBeenCalled();
    expect(cancelAnalysisJob).not.toHaveBeenCalled();
  });

  it("resumes the latest running job after remount", async () => {
    vi.mocked(getLatestAnalysisJob).mockResolvedValue(job("running"));
    vi.mocked(getAnalysisJob).mockResolvedValue(job("succeeded"));
    vi.mocked(getAnalysisJobResult).mockResolvedValue({
      job_id: "job-1",
      project_id: "project-1",
      status: "succeeded",
      complete: true,
      models: { one: {}, two: {} },
    });
    vi.mocked(getProject).mockResolvedValue({ source: { path: "source.jpg" }, layers: [], edits: [] });

    const { result } = renderHook(() => useAnalysisJob("project-1", 10));
    await act(async () => { await Promise.resolve(); });
    expect(result.current.view.status).toBe("running");

    await runPoll();
    expect(result.current.view.status).toBe("succeeded");
    expect(getAnalysisJob).toHaveBeenCalledWith("job-1");
  });

  it("ignores an enqueue response from the previously selected project", async () => {
    let resolveFirst: (value: AnalysisJob) => void = () => undefined;
    const first = new Promise<AnalysisJob>((resolve) => { resolveFirst = resolve; });
    vi.mocked(enqueueAnalysisJob).mockImplementation((projectId) => {
      if (projectId === "project-1") return first;
      return Promise.resolve({ ...job("queued", "job-2"), project_id: "project-2" });
    });
    const { result, rerender } = renderHook(
      ({ projectId }) => useAnalysisJob(projectId, 10),
      { initialProps: { projectId: "project-1" } },
    );

    let staleStart!: Promise<void>;
    act(() => { staleStart = result.current.start(); });
    rerender({ projectId: "project-2" });
    await act(() => result.current.start());
    resolveFirst(job("queued", "job-1"));
    await act(() => staleStart);

    expect(result.current.view.jobId).toBe("job-2");
  });
});
