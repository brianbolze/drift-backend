# Claude Skills for Engineering: What Senior Engineers Are Actually Using

*Research compiled March 2026*

---

## The Big Idea

Claude Skills let you encode the knowledge gap between a junior and senior engineer — the patterns that prevent problems before they happen — into reusable, auto-activating modules. Instead of re-explaining conventions across projects, you install a skill once and Claude applies it by default. The best skills aren't clever prompts; they're **distilled engineering judgment**.

---

## High-Impact Skills Worth Looking At

### 1. Planning with Files — `OthmanAdi/planning-with-files`
**Stars:** 13,410 (most starred skill in the ecosystem)

The core insight: Claude's volatile context window is a liability during multi-step refactors and long sessions. This skill writes plans to disk as markdown files, keeping Claude anchored across hours-long sessions. It addresses the single biggest failure mode most engineers hit — context drift mid-task.

**Why it matters:** Forces structured planning before execution. Particularly valuable for large refactors or feature work that spans multiple files.

---

### 2. Web Quality Skills — `addyosmani/web-quality-skills`
**Stars:** 496

Addy Osmani's collection of six skills covering the full spectrum of web quality: performance budgets (page weight < 1.5MB, JS < 300KB compressed), Core Web Vitals optimization, accessibility, and SEO. Includes framework-specific patterns for React and Vue.

**Why it matters:** Encodes the kind of performance knowledge that usually lives in one person's head. Claude stops generating bloated bundles and starts flagging performance anti-patterns proactively.

---

### 3. Pulumi Agent Skills — `pulumi/agent-skills`
**Key skills in the collection:**
- **pulumi-best-practices**: Catches the mistakes that burn you in production — stops Claude from creating resources inside `apply()` callbacks, enforces parent relationships, encrypts secrets from day one, ensures `pulumi preview` runs before deployment.
- **pulumi-esc**: Environment management, OIDC setup, secret store integration.
- **kubernetes-specialist**: Automatically adds security contexts, resource limits, and pod disruption budgets to deployments.

**Why it matters:** When you request "a static website on AWS," multiple skills fire simultaneously — TypeScript generates code, monitoring adds CloudWatch alarms, security flags missing encryption. Output shifts from "works" to "production-ready."

---

### 4. HashiCorp Agent Skills — `hashicorp/agent-skills`
**Stars:** 303

Official Terraform skills covering code generation, testing, and module creation following HashiCorp conventions. Includes plan-mode unit tests, module refactoring patterns, and security validation for conditional resource creation.

**Why it matters:** If your team uses Terraform, this stops Claude from generating syntactically valid but idiomatically wrong HCL.

---

### 5. Full SDLC Pipeline — `levnikolaevich/claude-code-skills`
**Stars:** 82

The most ambitious collection: encodes the entire software delivery lifecycle from epic planning through story creation, task breakdown, implementation, code review, testing, quality gates, and documentation audits. Enforces **role separation** — implementers don't commit, reviewers don't implement, test executors don't write production code.

**Why it matters:** Mirrors how high-functioning teams actually work. Prevents Claude from cutting corners by skipping review steps.

---

### 6. Snyk Fix — `snyk/studio-recipes`
Automated vulnerability detection and remediation. Attempts up to three iterations to resolve vulnerabilities, validates against test suites, and checks for regressions.

**Why it matters:** Closes the loop from "vulnerability found" to "vulnerability fixed and verified" without context-switching to a separate security tool.

---

### 7. GitHub PR Review — `aidankinzett/claude-git-pr-skill`
Professional pull request reviews using `gh` CLI with batched inline comments. Also worth noting: **Anthropic's own `/code-review` plugin** runs 5 parallel Sonnet agents checking CLAUDE.md compliance, bug detection, historical context, PR history, and code comments.

**Why it matters:** You're already using `/pr-review` — Anthropic's official version is notable because it parallelizes review across multiple focused agents rather than doing one monolithic pass.

---

### 8. Claude Agentic Framework — `dralgorhythm/claude-agentic-framework`
Core engineering practices: TDD, systematic debugging, refactoring, and dependency management. Enforces a structured approach rather than letting Claude jump straight to code.

---

## Patterns & Workflows Beyond Individual Skills

### The "AI Docs" Pattern
One senior engineer (Juan Pablo Djeredjian) creates exhaustive service guides by having Claude explore codebases, Jira tickets, PRs, and Slack threads. Output goes to an `AI_DOCS/` folder with architecture diagrams, API endpoints, database schemas, dependencies, and common gotchas. Key idea: **compound knowledge rather than letting it evaporate.**

### Cross-Model Review
For complex tasks: prompt Claude, Codex, and Gemini separately, then have different models review each other's work. Catches edge cases, security concerns, and alternative approaches none would find alone.

### CLI-First Tooling Strategy
Give Claude access to CLIs over MCPs when possible — GitHub CLI for PRs/CI, AWS CLI for Lambda logs and DynamoDB, `mongosh` for database queries, Datadog CLI for production logs. Then layer in Slack and Atlassian MCPs to make tribal knowledge queryable.

### Meeting Knowledge Extraction
Record expert knowledge-transfer sessions, extract frames with ffmpeg, then have Claude create step-by-step guides with embedded screenshots matched to discussion moments. Turns one-time expert wisdom into permanent documentation.

### Stacked Skills for Infrastructure
Request "deploy a static site on AWS" and multiple skills activate simultaneously — TypeScript generates code, monitoring adds CloudWatch, security flags missing encryption. The compound effect of stacking 3–4 skills is larger than any single skill.

---

## The Staff Engineer Perspective (HN Discussion)

A notable Hacker News thread on "A Staff Engineer's Journey with Claude Code" surfaced several recurring themes:

- **Planning overhead is real.** Success requires substantial upfront specification work. The resulting quality often exceeds expectations, but you're trading coding time for planning time.
- **Output needs editing down.** Engineers report LLM-generated code typically requires editing to "at least half its original size."
- **Break tasks small.** "Don't ask for large/complex changes. Ask for a plan, implement in small steps, test each step before the next."
- **Context window limits matter at scale.** In codebases spanning millions of lines, one engineer noted: "my brain has a shitload more of that in context than any of the models."

---

## Community Repositories to Browse

| Repository | What's In It |
|---|---|
| [awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | Curated list of skills and resources |
| [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | Skills, hooks, slash-commands, agent orchestrators |
| [Claude Command Suite](https://github.com/qdhenry/Claude-Command-Suite) | 216+ slash commands, 12 skills, 54 agents |
| [claude-skills-starter](https://github.com/angakh/claude-skills-starter) | 12 "essential" fork-and-customize skills |
| [Anthropic official plugins](https://github.com/anthropics/claude-code/tree/main/plugins) | `/code-review`, `/feature-dev`, `/hookify` |
| [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) | 66 skills for full-stack development |

---

## Security Note

Snyk's ToxicSkills research (Feb 2026) scanned 3,984 public skills and found 13.4% had critical vulnerabilities — including credential exfiltration and backdoor downloads. **Always read the source of any skill before installing.** Run `uvx mcp-scan@latest --skills` to detect malicious payloads.

---

## Potential Big Unlocks for You

Based on this research, the highest-leverage additions beyond `/pr-review` are likely:

1. **Planning with Files** — if you ever lose context mid-session on complex tasks, this is the #1 community-validated fix.
2. **Pulumi or HashiCorp agent skills** — if you do any IaC work, these encode production-grade patterns automatically.
3. **Full SDLC pipeline skills** — the role-separation enforcement is genuinely interesting for solo developers who need to force themselves through review gates.
4. **The AI Docs pattern** — not a skill per se, but creating persistent service documentation that compounds across sessions is a workflow multiplier.
5. **Anthropic's `/code-review` with parallel agents** — an upgrade path from single-pass PR review to multi-agent review with specialized focus areas.
