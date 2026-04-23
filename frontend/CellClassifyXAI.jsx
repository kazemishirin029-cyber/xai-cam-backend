/**
 * CellClassifyXAI.jsx
 * Full page layout matching the mockup.
 *
 * YOUR sections:  LeftSidebar (video picker) · PredictionHeader · FrameImportanceSection · RightPanel
 * ARJUN's slots:  <SequenceViewer /> · <TopSalientFrames />  (drop his components where marked)
 *
 * Backend (no changes needed):
 *   GET /videos                         → list of { id }
 *   GET /videos/:id                     → { id, label, frames, has_importance_plot, video }
 *   GET /videos/:id/analyze             → { predicted_label, frames_analyzed, gemini_analysis }
 *   /static/:id/frame_importance_plot.png
 *   /static/:id/temp_frame_N.jpg
 */

import { useState, useEffect, useRef } from "react";

const BASE = "http://localhost:8000";

/* ─── helpers ─────────────────────────────────────────── */
const api  = (path) => fetch(`${BASE}${path}`).then((r) => r.json());
const src  = (id, file) => `${BASE}/static/${id}/${file}`;

const SUGGESTED = [
  "Why was this classified as {label}?",
  "Which frames contributed most to the decision?",
  "Explain the importance plot peak.",
  "Compare the salient frames.",
];

/* ─── root ────────────────────────────────────────────── */
export default function CellClassifyXAI() {
  const [videos,     setVideos]     = useState([]);
  const [activeId,   setActiveId]   = useState(null);
  const [videoData,  setVideoData]  = useState(null);
  const [analysis,   setAnalysis]   = useState(null);
  const [analyzing,  setAnalyzing]  = useState(false);
  const [chatInput,  setChatInput]  = useState("");

  /* load video list */
  useEffect(() => {
    api("/videos").then(setVideos).catch(() => {});
  }, []);

  /* load video data when selection changes */
  useEffect(() => {
    if (!activeId) return;
    setVideoData(null); setAnalysis(null);
    api(`/videos/${activeId}`).then(setVideoData).catch(() => {});
  }, [activeId]);

  const handleAnalyze = () => {
    if (!activeId || analyzing) return;
    setAnalyzing(true); setAnalysis(null);
    api(`/videos/${activeId}/analyze`)
      .then((d) => { setAnalysis(d); setAnalyzing(false); })
      .catch(() => setAnalyzing(false));
  };

  const handleSuggestedQuery = (q) => {
    const label = videoData?.label ?? "this class";
    setChatInput(q.replace("{label}", label));
  };

  return (
    <div className="flex h-screen w-full bg-[#080d18] text-[#e2e8f0] overflow-hidden" style={{fontFamily:"'Inter','Segoe UI',sans-serif"}}>
      <LeftSidebar videos={videos} activeId={activeId} setActiveId={setActiveId} />
      <MiddlePanel videoData={videoData} activeId={activeId} />
      <RightPanel
        videoData={videoData}
        analysis={analysis}
        analyzing={analyzing}
        onAnalyze={handleAnalyze}
        chatInput={chatInput}
        setChatInput={setChatInput}
        onSuggestedQuery={handleSuggestedQuery}
      />
    </div>
  );
}

/* ─── LEFT SIDEBAR ────────────────────────────────────── */
function LeftSidebar({ videos, activeId, setActiveId }) {
  return (
    <aside className="w-[248px] flex-shrink-0 flex flex-col bg-[#0b1120] border-r border-[#1a2540]">
      {/* logo */}
      <div className="px-4 py-4 border-b border-[#1a2540]">
        <div className="flex items-center justify-between">
          <span className="text-[15px] font-semibold text-white">CellClassify XAI</span>
          <button className="text-[#475569] hover:text-[#94a3b8] text-sm">⊡</button>
        </div>
      </div>

      {/* search */}
      <div className="px-3 py-3">
        <div className="flex items-center gap-2 px-3 py-2 bg-[#0f1929] border border-[#1a2540] rounded-lg">
          <span className="text-[#475569] text-sm">🔍</span>
          <input
            placeholder="Search patient / study / session..."
            className="bg-transparent text-[13px] text-[#94a3b8] placeholder-[#334155] outline-none w-full"
          />
        </div>
      </div>

      {/* nav */}
      <div className="px-3 mb-2">
        <div className="flex items-center gap-2 px-3 py-2 bg-[#1a2e4a] rounded-lg">
          <span className="text-[13px] font-medium text-white">Chat Workspace</span>
        </div>
        <button className="flex items-center gap-2 px-3 py-2 w-full text-left hover:bg-[#0f1929] rounded-lg mt-0.5">
          <span className="text-[#94a3b8] text-sm">↺</span>
          <span className="text-[13px] text-[#94a3b8]">New Chat</span>
        </button>
        <button className="flex items-center gap-2 px-3 py-2 w-full text-left hover:bg-[#0f1929] rounded-lg">
          <span className="text-[13px] text-[#94a3b8]">Session History</span>
        </button>
      </div>

      {/* recent studies */}
      <div className="px-4 mt-1 mb-2">
        <p className="text-[10px] font-semibold text-[#475569] tracking-widest uppercase">Recent Studies</p>
      </div>

      <div className="flex-1 overflow-y-auto px-3 flex flex-col gap-1">
        {videos.length === 0 ? (
          /* demo entries if no backend */
          [
            { id: "042", sub: "Processed sequence • XAI outputs ready" },
            { id: "031", sub: "Prior comparison run" },
            { id: "018", sub: "Archived session" },
          ].map((v) => (
            <StudyCard
              key={v.id}
              title={`Microscopy Video — Sample_${v.id}`}
              sub={v.sub}
              active={false}
              onClick={() => {}}
            />
          ))
        ) : (
          videos.map((v) => (
            <StudyCard
              key={v.id}
              title={`Microscopy Video — Sample_${v.id.padStart(3,"0")}`}
              sub="Processed sequence • XAI outputs ready"
              active={activeId === v.id}
              onClick={() => setActiveId(v.id)}
            />
          ))
        )}
      </div>

      {/* model snapshot */}
      <div className="px-4 py-4 border-t border-[#1a2540]">
        <p className="text-[11px] font-semibold text-[#e2e8f0] mb-1.5">Model snapshot</p>
        <p className="text-[11px] text-[#475569] leading-5">
          Backbone: ResNet → Temporal Encoder<br />
          Explainability: Grad-CAM + Temporal heatmap<br />
          LLM: Gemini-style post-hoc rationale<br />
          Classes: Apoptotic • Necrotic • Non-apoptotic
        </p>
      </div>
    </aside>
  );
}

function StudyCard({ title, sub, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
        active ? "bg-[#1a2e4a]" : "hover:bg-[#0f1929]"
      }`}
    >
      <p className="text-[13px] font-medium text-[#e2e8f0]">{title}</p>
      <p className="text-[11px] text-[#475569] mt-0.5">{sub}</p>
    </button>
  );
}

/* ─── MIDDLE PANEL ────────────────────────────────────── */
function MiddlePanel({ videoData, activeId }) {
  return (
    <main className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5 min-w-0">
      {/* page title */}
      <div>
        <h1 className="text-[26px] font-bold text-white">Evidence Workspace</h1>
        <p className="text-[13px] text-[#475569] mt-1">
          Design centered on actual model outputs: label, AVI sequence, salient frames, and temporal importance plot
        </p>
      </div>

      {/* ── YOUR SECTION: prediction label ── */}
      <div className="bg-[#0b1422] border border-[#1a2540] rounded-xl px-6 py-5">
        <p className="text-[10px] font-semibold text-[#475569] tracking-widest uppercase mb-1">Model Output</p>
        <div className="flex items-center justify-between">
          <h2 className="text-[24px] font-bold text-white">
            Prediction:{" "}
            <span>{videoData?.label ?? <span className="text-[#334155]">—</span>}</span>
          </h2>
          {videoData && (
            <button className="flex items-center gap-1.5 px-4 py-1.5 border border-[#3b5a8a] rounded-full text-[12px] text-[#93c5fd] hover:bg-[#1a2e4a] transition-colors">
              predicted_label.txt
            </button>
          )}
        </div>
      </div>

      {/* ── ARJUN'S SECTION: Sequence Viewer ── */}
      <div className="bg-[#0b1422] border border-[#1a2540] rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1a2540]">
          <p className="text-[15px] font-semibold text-white">Sequence Viewer</p>
          <p className="text-[12px] text-[#475569]">Source: AVI output</p>
        </div>
        {/* ↓↓↓ DROP ARJUN'S <SequenceViewer videoId={activeId} /> HERE ↓↓↓ */}
        <div className="flex items-center justify-center bg-[#070d18] h-[280px]">
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 rounded-full border border-[#1a2540] flex items-center justify-center">
              <span className="text-[#334155] text-2xl ml-1">▶</span>
            </div>
            <p className="text-[12px] text-[#1e3352]">Arjun's SequenceViewer component</p>
          </div>
        </div>
        <div className="px-6 py-3 border-t border-[#1a2540] flex items-center justify-between">
          <div className="flex-1 bg-[#1a2540] rounded-full h-1 mr-4">
            <div className="bg-[#3b82f6] h-1 rounded-full w-[37%]" />
          </div>
          <span className="text-[11px] text-[#475569] font-mono whitespace-nowrap">
            {videoData ? `Frame 1 / ${videoData.frames?.length ?? "—"}` : "Frame — / —"}
          </span>
        </div>
      </div>

      {/* ── ARJUN'S SECTION: Top Salient Frames ── */}
      <div>
        <h3 className="text-[15px] font-semibold text-white mb-1">Top Salient Frames</h3>
        <p className="text-[12px] text-[#475569] mb-3">
          Temporally strongest evidence frames surfaced by the explanation pipeline.
        </p>
        {/* ↓↓↓ DROP ARJUN'S <TopSalientFrames videoId={activeId} /> HERE ↓↓↓ */}
        <div className="grid grid-cols-3 gap-3">
          {(videoData?.frames?.slice(0,3) ?? [null,null,null]).map((f, i) => (
            <div key={i} className="bg-[#0b1422] border border-[#1a2540] rounded-xl overflow-hidden">
              <div className="aspect-square bg-[#07101c] flex items-center justify-center">
                {f ? (
                  <img
                    src={src(videoData.id, f.filename)}
                    alt={f.filename}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-[#1e3352] text-xs">frame {i+1}</span>
                )}
              </div>
              <p className="text-[11px] text-[#475569] text-center py-2 px-1 truncate">
                {f ? f.filename : `temp_frame_${i+1}.jpg`}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── YOUR SECTION: Frame Importance / Grad-CAM ── */}
      {(videoData?.has_importance_plot || !videoData) && (
        <div className="bg-[#0b1422] border border-[#1a2540] rounded-xl overflow-hidden">
          <div className="flex items-start gap-5 p-6">
            <div className="flex-1 min-w-0">
              <h3 className="text-[15px] font-semibold text-white mb-1">Frame Importance Over Time</h3>
              <p className="text-[12px] text-[#475569] mb-3">Source: frame_importance_plot.png</p>
              {videoData ? (
                <>
                  <p className="text-[13px] text-[#94a3b8] leading-6 mb-2">
                    Peak activation emerges late in the sequence, supporting the {videoData.label} decision.
                  </p>
                  <p className="text-[13px] text-[#3b82f6]">
                    Temporal evidence is preserved instead of abstracted into speculative diagnostics.
                  </p>
                </>
              ) : (
                <p className="text-[13px] text-[#334155]">Select a study to view frame importance.</p>
              )}
            </div>
            <div className="w-[220px] flex-shrink-0 bg-[#070d18] border border-[#1a2540] rounded-lg overflow-hidden">
              {videoData?.has_importance_plot ? (
                <img
                  src={src(videoData.id, "frame_importance_plot.png")}
                  alt="Frame importance plot"
                  className="w-full h-[120px] object-contain"
                />
              ) : (
                <div className="w-full h-[120px] flex items-center justify-center">
                  <span className="text-[11px] text-[#1e3352] font-mono">frame_importance_plot.png</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

/* ─── RIGHT PANEL ─────────────────────────────────────── */
function RightPanel({ videoData, analysis, analyzing, onAnalyze, chatInput, setChatInput, onSuggestedQuery }) {
  const inputRef = useRef(null);

  const analysisText = analysis?.gemini_analysis;
  const label = videoData?.label ?? "RAP";

  return (
    <aside className="w-[360px] flex-shrink-0 flex flex-col bg-[#0b1120] border-l border-[#1a2540] overflow-hidden">
      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-5">
        {/* header */}
        <div>
          <h2 className="text-[20px] font-bold text-white">Explain Prediction</h2>
          <p className="text-[12px] text-[#475569] mt-1">LLM evidence layer grounded in pipeline outputs.</p>
        </div>

        {/* prediction badge + analysis */}
        <div className="bg-[#0f1929] border border-[#1a2540] rounded-xl p-4 flex flex-col gap-3">
          <div>
            <span className="px-3 py-1 border border-[#3b5a8a] rounded-full text-[12px] font-semibold text-[#93c5fd] bg-[#0d1e38]">
              Prediction: {label}
            </span>
          </div>

          {analyzing ? (
            <div className="flex items-center gap-2 text-[13px] text-[#475569]">
              <span className="w-3.5 h-3.5 border-2 border-[#475569]/30 border-t-[#3b82f6] rounded-full animate-spin" />
              Analyzing with Gemini…
            </div>
          ) : analysisText ? (
            <p className="text-[13px] text-[#94a3b8] leading-6">{analysisText}</p>
          ) : (
            <>
              <p className="text-[13px] text-[#94a3b8] leading-6">
                The model identified a pattern consistent with {label} based on temporal dynamics observed in the microscopy sequence.
              </p>
              <p className="text-[13px] text-[#94a3b8] leading-6">
                Key evidence includes the late peak in frame importance and the morphological structure visible in the salient frames.
              </p>
            </>
          )}

          {/* explain button — only show if not yet analyzed */}
          {videoData && !analysisText && !analyzing && (
            <button
              onClick={onAnalyze}
              className="mt-1 w-full py-2 bg-[#1d4ed8] hover:bg-[#2563eb] rounded-lg text-[13px] font-medium text-white transition-colors"
            >
              Run Explanation
            </button>
          )}
        </div>

        {/* suggested queries */}
        <div>
          <p className="text-[10px] font-semibold text-[#475569] tracking-widest uppercase mb-3">Suggested Queries</p>
          <div className="flex flex-col gap-2">
            {SUGGESTED.map((q) => (
              <button
                key={q}
                onClick={() => onSuggestedQuery(q)}
                className="text-left px-4 py-3 bg-[#0f1929] border border-[#1a2540] rounded-xl text-[13px] text-[#94a3b8] hover:border-[#3b5a8a] hover:text-[#e2e8f0] transition-colors"
              >
                {q.replace("{label}", label)}
              </button>
            ))}
          </div>
        </div>

        {/* grounding rules */}
        <div>
          <p className="text-[14px] font-semibold text-white mb-2">Grounding Rules</p>
          <ul className="flex flex-col gap-1.5">
            {[
              "Explain from displayed files only",
              "No segmentation, PACS, or unrelated imaging layers",
              "Tie language to label, frames, video, and plot",
            ].map((r) => (
              <li key={r} className="flex items-start gap-2 text-[13px] text-[#94a3b8]">
                <span className="text-[#475569] mt-0.5">•</span>{r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* chat input */}
      <div className="px-4 py-3 border-t border-[#1a2540]">
        <div className="flex items-center gap-2 bg-[#0f1929] border border-[#1a2540] rounded-xl px-4 py-2.5">
          <span className="text-[#334155] text-sm flex-shrink-0">◎</span>
          <input
            ref={inputRef}
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Ask about the prediction or request evidence..."
            className="flex-1 bg-transparent text-[13px] text-[#94a3b8] placeholder-[#334155] outline-none"
          />
          <button className="w-7 h-7 bg-[#2563eb] hover:bg-[#3b82f6] rounded-lg flex items-center justify-center flex-shrink-0 transition-colors">
            <span className="text-white text-[11px]">▶</span>
          </button>
        </div>
      </div>


    </aside>
  );
}
