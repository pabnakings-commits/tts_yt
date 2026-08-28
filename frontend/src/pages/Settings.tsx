import { useEffect, useState } from "react";
import { api, SettingsModel, SystemStatus } from "../services/api";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsModel | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [outputDir, setOutputDir] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    Promise.all([api.getSettings(), api.getSystem()])
      .then(([s, sys]) => {
        setSettings(s);
        setOutputDir(s.output_dir);
        setSystem(sys);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const handleFormatChange = async (fmt: SettingsModel["output_format"]) => {
    if (!settings) return;
    const updated = await api.updateSettings({ output_format: fmt });
    setSettings(updated);
  };

  const handleSaveDir = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await api.updateSettings({ output_dir: outputDir });
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!settings || !system) {
    return (
      <div className="page">
        <div className="card">
          {error ? <div className="error-banner">{error}</div> : "Loading settings..."}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="card">
        <div className="section-title">Engine</div>
        <div className="settings-row">
          <span className="settings-label">TTS Engine</span>
          <span className="settings-value">Kokoro (kokoro-v1.0, ONNX)</span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Device</span>
          <span className="settings-value">
            CPU
            {system.gpu_detected
              ? ` (NVIDIA GPU detected: ${system.gpu_name} — not used, CPU-only inference)`
              : " (no NVIDIA GPU detected)"}
          </span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Model files</span>
          {system.model_ready ? (
            <span className="badge badge-ok">Ready</span>
          ) : (
            <span className="badge badge-warn">Will download on first generation</span>
          )}
        </div>
      </div>

      <div className="card">
        <div className="section-title">Output</div>
        <div className="field">
          <label className="field-label">Output Format</label>
          <div className="select-wrap">
            <select
              className="select"
              value={settings.output_format}
              onChange={(e) => handleFormatChange(e.target.value as SettingsModel["output_format"])}
            >
              <option value="wav">WAV</option>
              <option value="mp3">MP3</option>
              <option value="wav+mp3">WAV + MP3</option>
            </select>
            <span className="select-chevron">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </div>
        </div>

        <div className="field">
          <label className="field-label">Output Folder</label>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              className="input"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={handleSaveDir} disabled={saving} style={{ whiteSpace: "nowrap" }}>
              {saving ? "Saving..." : saved ? "Saved" : "Save"}
            </button>
          </div>
          <p className="help-text">New generations are written here as project_001, project_002, etc.</p>
        </div>
      </div>

      <div className="card">
        <div className="section-title">FFmpeg</div>
        <div className="settings-row">
          <span className="settings-label">Status</span>
          {system.ffmpeg_installed ? (
            <span className="badge badge-ok">Installed ✓ {system.ffmpeg_version}</span>
          ) : (
            <span className="badge badge-bad">Not Found</span>
          )}
        </div>
        {!system.ffmpeg_installed && (
          <p className="help-text">
            FFmpeg is required for MP3 export (WAV export still works without it).
            Install it from ffmpeg.org, or on Windows run{" "}
            <code>winget install ffmpeg</code> in a terminal, then restart the app.
          </p>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
    </div>
  );
}
