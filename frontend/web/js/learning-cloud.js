/* Quiet, optional uploads to a Cloudflare Worker. No account or cloud UI. */
window.LearningCloud = (() => {
  const enabled = () => Boolean(window.COCKPIT_LEARNING_CLOUD?.endpoint);
  let uploadToken = null;
  function token() {
    if (uploadToken) return uploadToken;
    try { uploadToken = localStorage.getItem("flyteam-upload-token-v1"); } catch { /* in-memory fallback */ }
    if (!/^[a-f0-9]{64}$/.test(uploadToken || "")) {
      uploadToken = Array.from(crypto.getRandomValues(new Uint8Array(32)), n => n.toString(16).padStart(2, "0")).join("");
      try { localStorage.setItem("flyteam-upload-token-v1", uploadToken); } catch { /* local recordings remain exportable */ }
    }
    return uploadToken;
  }
  async function upload(envelope) {
    if (!enabled()) return;
    const response = await fetch(window.COCKPIT_LEARNING_CLOUD.endpoint, {
      method: "POST", headers: {"Content-Type": "application/json", "X-Upload-Token": token()},
      body: JSON.stringify(envelope), signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) throw new Error(`Upload fehlgeschlagen (${response.status})`);
  }
  return {enabled, upload};
})();
