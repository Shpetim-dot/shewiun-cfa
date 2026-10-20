# Shewiun CFA — Product and Go-to-Market Plan

Status: strategy hypothesis for validation, not a claim of market fit or a launch approval.

## 1. Positioning

**Category:** decision workspace and knowledge-backed agent team.

**One-line promise:** Turn an ambiguous work task into a structured recommendation, a traceable decision, and a next action—using named agents and a shared knowledge graph.

**Short website copy**
- Headline: **Make better decisions with a team of focused agents.**
- Subhead: Shewiun CFA brings strategy, risk, implementation and synthesis into one workspace. Every run can reuse the knowledge your team has chosen to save.
- Primary CTA: **Run your first task**
- Secondary CTA: **Explore the Brain**
- Proof point to demonstrate—not merely claim: show one real task from prompt → multiple perspectives → linked Brain notes → saved decision.

## 2. Initial ideal customer profile

Start with one narrow audience, not “everyone who uses AI”.

**Recommended first segment:** small product, operations and consulting teams (3–30 people) that repeatedly make decisions from scattered documents and need a clear record of why a decision was made.

**Jobs to be done**
- Compare options and document trade-offs.
- Turn a vague initiative into an executable plan.
- Keep project assumptions, decisions and sources reusable.
- Review an AI-assisted workflow before a team relies on it.

**Buyer:** founder, product lead, operations lead or consulting partner.
**Daily user:** project lead, analyst, product manager or consultant.
**Do not target first:** enterprises requiring SSO, strict contractual data controls, custom integrations or formal compliance certification until those capabilities are delivered and tested.

## 3. Differentiation

The market is crowded with general-purpose assistants. Do not position CFA as “another chatbot” or claim that a multi-agent setup is automatically more intelligent.

| Alternative | Their natural strength | Shewiun CFA should win on |
|---|---|---|
| General AI chat | Flexible one-off answers | Repeatable task workflow, named roles, decision history |
| Notes / knowledge apps | Human-authored knowledge and links | Agent runs that retrieve and cite the team's saved context |
| Workflow automation | Connecting systems and triggering actions | Deliberate reasoning and review before an action is automated |
| Agent frameworks | Developer control and extensibility | A usable workspace for non-specialists to configure roles and review results |

**Defensible product loop:** task → focused agent roles → explicit assumptions and evidence → human decision → saved Brain note → more relevant context for the next task. The advantage is the workflow and accumulated, curated knowledge—not a proprietary foundation model.

## 4. Product principles

1. **A useful first run without a model key.** The Local Planner is a deterministic planning helper. Label it honestly; it is not a generative model.
2. **Named, purpose-built agents.** Users can add, name, and define roles. Default roles should have clear jobs, not decorative personas.
3. **Knowledge with provenance.** Brain notes have a title, type, source, confidence and explicit links. Never silently turn a model guess into a fact.
4. **Human-owned memory.** Agents can retrieve saved notes; users validate and save outcomes. The product does not secretly self-modify or learn from private conversations without consent.
5. **Clear modes.** Distinguish local/rules-based results from model-backed results and show when context is temporary.
6. **Outcome-first UI.** One main task input, visible agent selector, clear next action, readable result, and a one-click way to save a useful result.

## 5. Recommended release scope

### Free starter
- Local Planner with no external model/API bill.
- A small Brain with manual notes and explicit links.
- A small number of named custom agents.
- Export / copy of task results.
- Clear limits on local-only deterministic planning.

### Individual paid plan (pricing hypothesis; validate in interviews)
- Model-backed runs using user-provided key or an included, metered allowance.
- Larger Brain, reusable agent templates, more task history and exports.
- Suggested test price: €12–19/month.

### Team plan (pricing hypothesis; validate before publishing)
- Shared Brain, shared agent templates, project spaces, decision history and team onboarding.
- Suggested test price: €25–39 per seat/month, with a minimum seat count only if customers accept it.

### Business / enterprise
Do not sell as ready until identity, tenant separation, durable jobs, contractual data handling, support and operational requirements are complete. Start with discovery calls and a waitlist rather than promises.

**Important cost rule:** never promise unlimited model usage for a fixed low price before measuring real token use, retries, context size and abuse. Prefer BYOK or a transparent included allowance with clear caps.

## 6. Design direction

- Palette: warm neutral canvas, dark slate text, cobalt blue reserved for the animated agent and primary action, restrained semantic colors for risk/status.
- Icons: consistent open-source stroke icons such as Lucide, not letters in circles, emoji, or random Unicode glyphs.
- Agent identity: one small animated blue mascot used as a status indicator (idle / thinking / working), not a full-screen character. Respect reduced-motion preferences.
- Layout: stable left navigation; compact agent rail immediately above the task composer; clear plus button for creating agents; Brain graph and entry-list views; responsive mobile layout.
- Brain: show real note nodes and explicit edges; allow search and clicking a node to open the note. Avoid drawing fake relationships when notes are unlinked.
- States: every view needs loading, empty, error and populated states. Never leave a tab blank without an explanation and action.
- Copy: avoid “fully autonomous”, “self-improving”, “secure by design”, “enterprise-ready” or “certified” unless the exact capability has been implemented, measured and verified.

## 7. Website and sales funnel

1. Landing page names the target user and the task they can complete.
2. Show a 60–90 second product walkthrough: create an agent, run a task, inspect Brain links, save a decision.
3. Offer a sample workspace with non-sensitive example content.
4. Ask for an email only after showing useful value; state exactly what is stored and why.
5. Invite qualified teams to a 20-minute workflow interview or a scoped pilot.
6. Publish limitations and supported integrations beside pricing, not only in legal pages.

**Landing page sections**
- Hero and primary CTA.
- Three-step workflow: Assign → Review → Remember.
- Real screenshot/video of the actual product.
- One example decision with assumptions, risks and linked notes.
- “What CFA is / is not” (workspace and orchestration layer, not a foundation model).
- Pricing and limits.
- FAQ: model costs, data retention, knowledge reuse, free tier, human oversight.
- Contact and support route.

## 8. First 30 days of non-technical validation

**Week 1 — Discovery**
- Interview 10–15 product/operations/consulting leads.
- Ask about their last difficult decision, existing workflow, cost of lost context, and what they already pay for.
- Do not pitch first; collect exact language and current workarounds.

**Week 2 — Concierge pilot**
- Recruit 3–5 teams.
- Run real, low-sensitivity tasks with them.
- Measure time-to-first-useful-result, how often they edit the output, how often they save Brain notes, and whether the next task benefits from those notes.

**Week 3 — Positioning tests**
- Test two messages: “decision workspace” versus “knowledge-backed agent team”.
- Test one use case at a time: product prioritization, project planning, or consulting decision records.
- Measure qualified signups and completed first tasks, not page views alone.

**Week 4 — Paid intent**
- Ask pilot users to choose between a concrete free plan and one paid plan.
- Request a paid pilot or refundable deposit only if the value proposition is clear.
- Continue only if users repeat the workflow without being prompted and at least a few express credible willingness to pay.

## 9. Metrics to instrument

- Activation: first completed task within 24 hours.
- Time to first useful result.
- Repeat use: active users returning in week 2.
- Brain adoption: percentage of tasks that reference or save notes.
- Decision quality proxy: user-rated usefulness and number of substantive edits.
- Retention: week-4 active teams.
- Conversion: activated free users who start a paid trial/pilot.
- Cost to serve: model spend per active user and per completed task.
- Support burden and failed-task rate.

Do not optimize for raw agent count, number of tokens, or number of generated messages. Those can rise while customer value falls.

## 10. Non-security requirements before commercial launch

- Choose the first customer segment and publish one concrete use case.
- Decide the company/legal entity and who owns product support.
- Publish accurate pricing, usage limits, cancellation/refund terms, and invoice/VAT handling for the target markets.
- Prepare privacy notice, terms of service, data-processing terms where relevant, subprocessors list, retention/deletion policy and contact details with qualified legal review.
- Clarify rights to user inputs and outputs, model-provider terms, and whether provider free-tier content may be used to improve provider products.
- Add a real support channel, incident/status communication plan, onboarding guide and feedback collection.
- Prepare customer-facing documentation: agent roles, Brain links, model setup, export, limitations and known issues.
- Use real product screenshots and a repeatable demo dataset; never use fabricated testimonials or unverified performance claims.
- Confirm brand/trademark/domain availability before spending on launch assets.
- Define a support and product feedback cadence for pilot customers.

## 11. Honest current promise

Shewiun CFA currently aims to provide a structured decision workspace, a rules-based local planning agent, configurable agent roles, and a linked knowledge view. Model-backed generation requires a configured provider key. Persistent cross-session memory requires durable database configuration. These dependencies must be disclosed until they are provisioned and verified.
