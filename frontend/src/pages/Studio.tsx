import { useEffect, useMemo, useRef, useState } from "react";
import { api, JobProgress, pollJob, Voice } from "../services/api";
import AudioPlayer from "../components/AudioPlayer";

const STATE_LABELS: Record<string, string> = {
  queued: "Queued...",
  preparing_model: "Preparing model...",
  generating: "Generating voice...",
  combining_segments: "Combining segments...",
  processing_audio: "Processing audio...",
  finalizing: "Finalizing...",
  done: "Done",
  error: "Error",
};

export default function Studio() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [text, setText] = useState("");
  const [speed, setSpeed] = useState(1.0);
  const [job, setJob] = useState<JobProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    api
      .getVoices()
      .then((v) => {
        setVoices(v.voices);
        if (v.voices.length) setVoiceId(v.voices[0].id);
      })
      .catch((e) => setLoadError(e.message));
  }, []);

  const groupedVoices = useMemo(() => {
    const male = voices.filter((v) => v.gender === "male");
    const female = voices.filter((v) => v.gender === "female");
    return { male, female };
  }, [voices]);

  const charCount = text.length;

  const handleGenerate = async () => {
    if (!text.trim() || !voiceId || busy) return;
    setBusy(true);
    setJob(null);
    cancelledRef.current = false;
    try {
      const { job_id } = await api.generate({ text, voice_id: voiceId, speed });
      await pollJob(job_id, (j) => {
        if (!cancelledRef.current) setJob(j);
      });
    } catch (e: any) {
      setJob({
        job_id: "error",
        state: "error",
        progress: 0,
        message: "Generation failed",
        error: e.message ?? "Unknown error",
      });
    } finally {
      setBusy(false);
    }
  };

  const isRunning =
    busy && job && job.state !== "done" && job.state !== "error";

  return (
    <div className="page">
      <div className="card">
        <div className="field">
          <label className="field-label" htmlFor="voice">
            Voice
          </label>
          <div className="select-wrap">
            <select
              id="voice"
              className="select"
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
            >
              {groupedVoices.male.length > 0 && (
                <optgroup label="Male">
                  {groupedVoices.male.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {groupedVoices.female.length > 0 && (
                <optgroup label="Female">
                  {groupedVoices.female.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            <span className="select-chevron">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path
                  d="m6 9 6 6 6-6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
          </div>
          {loadError && <p className="help-text">Could not load voices: {loadError}</p>}
        </div>

        <div className="field">
          <label className="field-label" htmlFor="script">
            Text
          </label>
          <textarea
            id="script"
            className="textarea"
            placeholder="Paste your script here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="char-count">Characters: {charCount.toLocaleString()}</div>
        </div>

        <div className="field">
          <label className="field-label">Speed</label>
          <div className="speed-row">
            <input
              type="range"
              min={0.75}
              max={1.25}
              step={0.05}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            />
            <span className="speed-value">{speed.toFixed(2)}x</span>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={busy || !text.trim() || !voiceId}
        >
          {busy ? "Generating..." : "Generate Voice"}
        </button>

        {job && (
          <div className="status-panel">
            {job.state !== "error" && (
              <>
                <div className="status-row">
                  {isRunning && <span className="status-dot" />}
                  <span>{STATE_LABELS[job.state] ?? job.message}</span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${job.progress}%` }} />
                </div>
              </>
            )}
            {job.state === "error" && (
              <div className="error-banner">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
                  <path d="M12 8v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="12" cy="16" r="1" fill="currentColor" />
                </svg>
                <span>{job.error ?? "Something went wrong. Please try again."}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {job?.state === "done" && job.audio_id && (
        <div className="card">
          <div className="section-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7L8 5Z" />
            </svg>
            Generated Audio
          </div>
          <AudioPlayer
            src={api.audioUrl(job.audio_id, "wav")}
            wavUrl={api.audioUrl(job.audio_id, "wav")}
            mp3Url={api.audioUrl(job.audio_id, "mp3")}
            hasMp3={Boolean(job.result?.has_mp3)}
          />
          {job.result && (
            <p className="help-text" style={{ marginTop: 14 }}>
              Duration: {Math.round((job.result.duration_seconds as number) * 10) / 10}s &middot;
              {" "}Saved to output/{job.audio_id}/
            </p>
          )}
        </div>
      )}
    </div>
  );
}
