import { useEffect, useState } from "react";
import { api, ProjectDetail, ProjectSummary } from "../services/api";
import AudioPlayer from "../components/AudioPlayer";

export default function Projects() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [newName, setNewName] = useState("");
  const [selected, setSelected] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = () => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message));
  };

  useEffect(refresh, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.createProject({ name: newName.trim() });
      setNewName("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleOpen = async (id: string) => {
    try {
      const detail = await api.getProject(id);
      setSelected(detail);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this project? This cannot be undone.")) return;
    try {
      await api.deleteProject(id);
      if (selected?.id === id) setSelected(null);
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <div className="section-title">Projects</div>
        <div className="field" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              className="input"
              placeholder="New project name (e.g. Fishing News)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
            <button
              className="btn btn-secondary"
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              style={{ whiteSpace: "nowrap" }}
            >
              + New Project
            </button>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        {projects.length === 0 ? (
          <div className="empty-state">
            No projects yet. Create one above, or generate audio from the
            Studio tab and save it as a project.
          </div>
        ) : (
          <div className="project-list">
            {projects.map((p) => (
              <div className="project-item" key={p.id}>
                <div>
                  <div className="project-item-name">{p.name}</div>
                  <div className="project-item-meta">
                    {p.has_audio ? "Audio generated" : "No audio yet"} &middot; updated{" "}
                    {new Date(p.updated_at).toLocaleString()}
                  </div>
                </div>
                <div className="project-item-actions">
                  <button className="btn btn-secondary" onClick={() => handleOpen(p.id)}>
                    Open
                  </button>
                  <button className="btn btn-danger" onClick={() => handleDelete(p.id)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selected && (
        <div className="card">
          <div className="section-title">{selected.name}</div>
          {selected.script && (
            <div className="field">
              <label className="field-label">Script</label>
              <textarea className="textarea" readOnly value={selected.script} style={{ minHeight: 140 }} />
            </div>
          )}
          {selected.has_audio ? (
            <AudioPlayer
              src={api.audioUrl(selected.id, "wav")}
              wavUrl={api.audioUrl(selected.id, "wav")}
              mp3Url={api.audioUrl(selected.id, "mp3")}
              hasMp3={selected.has_mp3}
            />
          ) : (
            <p className="help-text">No audio generated for this project yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
