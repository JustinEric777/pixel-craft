import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelAnalysisJob,
  enqueueAnalysisJob,
  getAnalysisJob,
  getAnalysisJobResult,
  getLatestAnalysisJob,
  getProject,
  type AnalysisJob,
  type AnalysisJobResult,
  type AnalysisJobStatus,
  type Project,
} from "./api";

type AnalysisViewStatus = "idle" | "enqueueing" | "cancelling" | AnalysisJobStatus;

export type AnalysisJobView = {
  jobId?: string;
  status: AnalysisViewStatus;
  completedCount: number;
  totalCount: number;
  message?: string;
  error?: string;
  project?: Project;
  result?: AnalysisJobResult;
};

const TERMINAL = new Set<AnalysisJobStatus>(["succeeded", "completed", "failed", "cancelled"]);

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function progress(job: AnalysisJob) {
  return {
    completedCount: Object.keys(job.completed_models || {}).length,
    totalCount: job.requested_models.length,
  };
}

function runningMessage(job: AnalysisJob): string {
  const current = progress(job);
  if (job.status === "queued") return `AI 分析已排队 · 0/${current.totalCount}`;
  return `AI 分析中 · ${current.completedCount}/${current.totalCount}`;
}

function terminalMessage(result: AnalysisJobResult): string {
  const count = Object.keys(result.models || {}).length;
  if (result.status === "cancelled") return `AI 分析已取消 · 已完成 ${count} 个模型`;
  if (result.status === "failed") return "AI 分析失败";
  if (result.status === "completed") return `AI 分析完成，部分模型失败 · ${count} 个模型已落盘`;
  return `AI 分析完成 · ${count} 个模型已落盘`;
}

function requestKey(projectId: string): string {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  return `analysis:${projectId}:${random}`;
}

export function analysisJobIsActive(status: AnalysisViewStatus): boolean {
  return status === "enqueueing" || status === "queued" || status === "running" || status === "cancelling";
}

export function useAnalysisJob(projectId?: string, pollMilliseconds = 1500) {
  const [view, setView] = useState<AnalysisJobView>({
    status: "idle",
    completedCount: 0,
    totalCount: 0,
  });
  const generation = useRef(0);
  const timer = useRef<number | undefined>(undefined);

  const stopTimer = useCallback(() => {
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    timer.current = undefined;
  }, []);

  const finish = useCallback(async (job: AnalysisJob, token: number, activeProjectId: string) => {
    stopTimer();
    const result = await getAnalysisJobResult(job.id);
    const refreshedProject = result.status === "succeeded" || result.status === "completed"
      ? await getProject(activeProjectId)
      : undefined;
    if (generation.current !== token) return;
    setView({
      jobId: job.id,
      status: result.status,
      ...progress(job),
      message: terminalMessage(result),
      error: result.error || undefined,
      project: refreshedProject,
      result,
    });
  }, [stopTimer]);

  const poll = useCallback(async function pollCurrent(jobId: string, token: number, activeProjectId: string): Promise<void> {
    try {
      const job = await getAnalysisJob(jobId);
      if (generation.current !== token) return;
      if (TERMINAL.has(job.status)) {
        await finish(job, token, activeProjectId);
        return;
      }
      setView((current) => ({
        ...current,
        jobId: job.id,
        status: job.status,
        ...progress(job),
        message: runningMessage(job),
        error: undefined,
      }));
      timer.current = window.setTimeout(
        () => void pollCurrent(job.id, token, activeProjectId),
        pollMilliseconds,
      );
    } catch (error) {
      if (generation.current !== token) return;
      stopTimer();
      setView((current) => ({
        ...current,
        status: "failed",
        message: "AI 分析状态查询失败",
        error: errorMessage(error),
      }));
    }
  }, [finish, pollMilliseconds, stopTimer]);

  const start = useCallback(async () => {
    if (!projectId) return;
    const token = generation.current + 1;
    generation.current = token;
    stopTimer();
    setView({
      status: "enqueueing",
      completedCount: 0,
      totalCount: 0,
      message: "正在创建 AI 分析任务…",
    });
    try {
      const job = await enqueueAnalysisJob(projectId, {
        idempotencyKey: requestKey(projectId),
      });
      if (generation.current !== token) return;
      setView({
        jobId: job.id,
        status: job.status,
        ...progress(job),
        message: TERMINAL.has(job.status) ? undefined : runningMessage(job),
      });
      if (TERMINAL.has(job.status)) {
        await finish(job, token, projectId);
      } else {
        timer.current = window.setTimeout(
          () => void poll(job.id, token, projectId),
          pollMilliseconds,
        );
      }
    } catch (error) {
      if (generation.current !== token) return;
      setView({
        status: "failed",
        completedCount: 0,
        totalCount: 0,
        message: "AI 分析任务创建失败",
        error: errorMessage(error),
      });
    }
  }, [finish, poll, pollMilliseconds, projectId, stopTimer]);

  const cancel = useCallback(async () => {
    if (!view.jobId || !analysisJobIsActive(view.status)) return;
    const token = generation.current;
    stopTimer();
    setView((current) => ({ ...current, status: "cancelling", message: "正在取消 AI 分析…" }));
    try {
      const job = await cancelAnalysisJob(view.jobId);
      if (generation.current !== token) return;
      await finish(job, token, job.project_id);
    } catch (error) {
      if (generation.current !== token) return;
      setView((current) => ({
        ...current,
        status: "failed",
        message: "AI 分析取消失败",
        error: errorMessage(error),
      }));
    }
  }, [finish, stopTimer, view.jobId, view.status]);

  useEffect(() => {
    const token = generation.current + 1;
    generation.current = token;
    stopTimer();
    setView({ status: "idle", completedCount: 0, totalCount: 0 });
    if (!projectId) return;
    void getLatestAnalysisJob(projectId)
      .then(async (job) => {
        if (generation.current !== token || job === null) return;
        setView({
          jobId: job.id,
          status: job.status,
          ...progress(job),
          message: TERMINAL.has(job.status) ? undefined : runningMessage(job),
        });
        if (TERMINAL.has(job.status)) {
          await finish(job, token, projectId);
        } else {
          timer.current = window.setTimeout(
            () => void poll(job.id, token, projectId),
            pollMilliseconds,
          );
        }
      })
      .catch((error) => {
        if (generation.current !== token) return;
        setView({
          status: "failed",
          completedCount: 0,
          totalCount: 0,
          message: "AI 分析恢复失败",
          error: errorMessage(error),
        });
      });
  }, [finish, poll, pollMilliseconds, projectId, stopTimer]);

  useEffect(() => () => {
    generation.current += 1;
    stopTimer();
  }, [stopTimer]);

  return { view, start, cancel, active: analysisJobIsActive(view.status) };
}
