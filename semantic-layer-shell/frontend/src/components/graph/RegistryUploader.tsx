import { useState } from "react";
import { fetchJson, uploadRegistryFiles } from "../../services/api";

export function RegistryUploader() {
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [publishResult, setPublishResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    try {
      await uploadRegistryFiles(files);
      const result = await fetchJson<Record<string, unknown>>("/api/v1/registry/validate", { method: "POST" });
      setValidation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const onPublish = async () => {
    setError(null);
    try {
      const result = await fetchJson<Record<string, unknown>>("/api/v1/registry/publish", { method: "POST" });
      setPublishResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publish failed");
    }
  };

  return (
    <div className="panel">
      <h2>Registry Uploader</h2>
      <input type="file" multiple accept=".yaml,.yml" onChange={(e) => onUpload(e.target.files)} />
      {validation && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Validation</h3>
          <pre>{JSON.stringify(validation, null, 2)}</pre>
          {validation.passed === true && (
            <button className="primary" onClick={onPublish}>
              Publish to Graph
            </button>
          )}
        </div>
      )}
      {publishResult && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Published</h3>
          <pre>{JSON.stringify(publishResult, null, 2)}</pre>
        </div>
      )}
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
    </div>
  );
}
