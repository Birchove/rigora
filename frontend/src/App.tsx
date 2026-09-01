const stages = ["Idea Review", "Plan", "Check", "Working", "Complete"];

export default function App() {
  return (
    <div className="app-frame">
      <header className="app-header">
        <a className="brand" href="/" aria-label="傲娇导师首页">
          <span className="brand-mark" aria-hidden="true">
            研
          </span>
          <span>
            <strong>傲娇导师</strong>
            <small>Research Mentor</small>
          </span>
        </a>
        <p className="build-note">v1 · workspace foundation</p>
      </header>

      <main className="welcome-shell">
        <div className="research-rail" aria-hidden="true">
          <span>01</span>
          <span className="research-rail-line" />
          <span>05</span>
        </div>

        <section className="welcome-copy" aria-labelledby="workspace-title">
          <p className="eyebrow">Computer science research workflow</p>
          <h1 id="workspace-title">科研判断与推进工作台</h1>
          <p className="welcome-summary">
            从 Idea 审查到结果整理，把每一次判断、选择和证据留在同一条研究脉络里。
          </p>

          <ol className="stage-preview" aria-label="五个研究阶段">
            {stages.map((stage, index) => (
              <li key={stage}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                {stage}
              </li>
            ))}
          </ol>

          <p className="scope-note">
            当前已建立前端基础与 API contract；项目工作台将在下一阶段接入。
          </p>
        </section>
      </main>
    </div>
  );
}
