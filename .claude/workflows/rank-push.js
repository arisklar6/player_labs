export const meta = {
  name: 'rank-push',
  description: 'Fan out reviewers over scoring, winners, our failures and untapped signal; synthesise ranked hypotheses; adversarially verify them; return an implementation plan.',
  whenToUse: 'When our Crewrift Prime standing needs to improve and we want a broad, evidence-grounded sweep rather than one hand-picked hypothesis.',
  phases: [
    { title: 'Recon', detail: 'four independent reviewers: scoring, winners, our failures, untapped signal' },
    { title: 'Hypotheses', detail: 'synthesise into ranked, mechanistic, testable proposals' },
    { title: 'Verify', detail: 'two adversarial skeptics per hypothesis, prompted to refute' },
    { title: 'Plan', detail: 'implementation plan for the survivors' },
  ],
}

const REPO = '/Users/arisk/Code/player_labs'

const CONTEXT = `
You are reviewing a Crewrift (Among Us-like, 8 players, 2 imposters) policy competing in
the Softmax "Crewrift Prime" league. Repo: ${REPO}. Our policy is named \`watts\`
(a fork of crewborg) at \`crewrift_lab/crewrift/crewborg/\`.

STANDING: 16th of 20, Elo 1436. We were 4th before our policy became champion, so we are
actively losing ground. The goal is to climb.

SCORING: an imposter win pays reward 3.0, a crew win 1.0, a loss 0. Roles are random,
~25% imposter. Elo is updated per round (k=4, swiss_neighbor pairing, mean scoring).

ROLE-MATCHED PERFORMANCE from 119 live league seats:
  crew      19.6% win (n=92)  vs field 21.2% (n=622)
  imposter  74.1% win (n=27)  vs field 79.6% (n=211)
Because imposter wins pay 3x, the imposter gap is ~77% of our deficit.

WHAT WE ALREADY KNOW (do not re-derive; build on it or challenge it with evidence):
- We kill MORE than any opponent (1.89/ep vs field 1.40), re-kill faster (median gap 1299
  vs 1972 ticks), start at the field median (first kill ~3560) and are ejected LESS
  (15% vs 23%). Kills are NOT the constraint.
- Imposters reach parity by removing 4 crew; kills alone rarely get there, crew EJECTIONS
  do. We used to skip 100% of imposter votes. The two policies in this league that never
  vote as imposter are the two worst imposters.
- FIX ALREADY BUILT (watts:v4, uploaded, NOT submitted): imposters now vote out a crewmate,
  bandwagoning on chat accusations, never a teammate. Forced-imposter A/B vs v3, 90 eps
  each: skip 100%->0%, crew ejected/ep 0.95->1.63, win 55.0%->66.7% (p=0.15, not
  significant), we-get-ejected 46.2%->36.9%.
- Crew side: lowering the vote bar (VOTE_PROBABILITY 0.8 -> 0.65) was tested and REJECTED
  - accuracy fell 56%->20% (below the 29% random baseline) and innocent ejections went
  4->32 per 60 episodes. It also got us voted out 8x vs 0 (p=0.007).
- A chat-accusation evidence cue was added to the crew suspicion model and measured INERT
  (the field went quiet between calibration and test).
- The suspicion model is well-calibrated at >=0.80 (81% correct) and anti-informative in
  0.65-0.80 (~3%). Hand-picked evidence weights overstate by ~2.2x - measured, not applied.
- OPEN LEAD: the model may degrade specifically with 2 imposters. Our votes were 2.2x
  better than random in a 1-imposter drill but 0.7x (worse than random) in 2-imposter
  league play.

DATA ALREADY ON DISK (episode dirs; each has episode.json + replay.json):
  /tmp/league        120 LIVE league episodes (policy_results[] + avg_reward shape)
  /tmp/impab/v3, /tmp/impab/v4   forced-imposter A/B, 90 each
  /tmp/vb/v1,/tmp/vb/v2,/tmp/vb/v3  crewrift-prime-vote-basic drill, 90 each
  /tmp/ab3/v1, /tmp/ab3/v3       forced-crew A/B, 70 each
  /tmp/h2h           90 paired episodes, random roles
  /tmp/watts_crew, /tmp/watts_imp  original forced-role baseline

TOOLKIT: ${REPO}/crewrift_lab/tools/analysis/ (read its README.md FIRST - it documents the
two identification rules that everything depends on, and which record shape each script
expects). Run scripts with \`cd ${REPO} && uv run python crewrift_lab/tools/analysis/<x>.py <dirs>\`.
The replay expander is \`crewrift_lab/tools/bin/expand_replay <replay.json>\`; it prints a
tick-stamped event timeline. \`export PATH="$HOME/.nimble/bin:$PATH"\` if you rebuild it.

GAME REFERENCE: crewrift_lab/docs/crewrift-gameplay.md (rules, scoring, strategy).
POLICY INTERNALS: crewrift_lab/crewrift/crewborg/design.md and docs/designs/suspicion.md,
plus docs/suspicion-calibration.md (our measured findings).

HARD RULES:
- READ-ONLY on the world: never run \`coworld upload-policy\`, never \`coworld submit\`,
  never create experience requests, never push git. Analysis and local file reads only.
- Do not edit any file under ${REPO}. Report findings; a human decides what ships.
- Ground every claim in a number you computed or a file/line you read. "Plausibly" and
  "likely helps" are not evidence. If you could not verify something, say so.
`

const FINDINGS = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      maxItems: 6,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'evidence', 'lever'],
        properties: {
          claim: { type: 'string', description: 'One sentence, specific and falsifiable.' },
          evidence: { type: 'string', description: 'The numbers or file:line that establish it.' },
          lever: { type: 'string', description: 'What could be changed in the policy because of this, or "none - diagnostic only".' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

const HYPOTHESES = {
  type: 'object',
  additionalProperties: false,
  required: ['hypotheses'],
  properties: {
    hypotheses: {
      type: 'array',
      maxItems: 4,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'mechanism', 'change', 'predicted_effect', 'metric', 'expected_reward_gain'],
        properties: {
          title: { type: 'string' },
          mechanism: { type: 'string', description: 'WHY this loses points now, pinned to a rule/threshold/code path.' },
          change: { type: 'string', description: 'The single scoped change, naming file and constant/function.' },
          predicted_effect: { type: 'string', description: 'Pre-registered, falsifiable: which number moves, which way, how much.' },
          metric: { type: 'string', description: 'The one target axis to measure it on.' },
          expected_reward_gain: { type: 'number', description: 'Estimated reward/episode gain. Our current mean is 0.655; field is 0.764.' },
          risk: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  required: ['refuted', 'reasoning'],
  properties: {
    refuted: { type: 'boolean', description: 'true if the hypothesis does not survive scrutiny' },
    reasoning: { type: 'string' },
    strongest_objection: { type: 'string' },
  },
}

const LENSES = [
  {
    key: 'scoring',
    prompt: `Own the SCORING model. Where exactly do our points come from and leak away?
Read crewrift_lab/docs/crewrift-gameplay.md on win conditions and scoring, then measure
against /tmp/league. Decompose our reward/episode versus the field into role mix, per-role
win rate, and anything else that carries points. Quantify how much reward/episode each gap
is worth, so we can rank levers by value rather than by how interesting they look. Check
whether Elo/pairing (swiss_neighbor, k=4) changes what we should optimise. Be concrete:
if a lever is worth less than ~0.01 reward/episode, say so and rank it last.`,
  },
  {
    key: 'winners',
    prompt: `Own the WINNERS. What do the strongest policies do that we do not?
Use /tmp/league. Compare role-matched (crew vs crew, imposter vs imposter) - a mixed-role
comparison is the error that already misled this project once. Focus on the top few by
mean reward and by per-role win rate. Look at behaviour in replays: kill timing and
positioning, meeting conduct, chat, voting, body reporting, task behaviour, movement.
Name at least two concrete behaviours we lack, each with the numbers that distinguish
them. Then check whether the behaviour is actually causal or just correlated with winning.`,
  },
  {
    key: 'failures',
    prompt: `Own OUR FAILURES. How do we actually lose, in both roles?
Use /tmp/league (live rounds) plus /tmp/ab3 and /tmp/vb. Separate crew losses from imposter
losses. For each, find the dominant loss mode and the mechanism behind it, and quantify how
often it happens. Our crew side dies in 63-73% of games and FLEE_PROBABILITY is 0.9, even
stricter than the vote bar that was already disproven - test whether we ever actually flee,
and what it costs. Chase the "should have won" games. Separate operational failures
(crashes, timeouts, disconnects) from behavioural ones and report them apart.`,
  },
  {
    key: 'signal',
    prompt: `Own UNTAPPED SIGNAL. What information does the policy receive but never use?
Read the perception layer (crewrift_lab/crewrift/crewborg/perception/) and the belief type
(types.py: Belief), and compare what is DECODED against what is CONSUMED by
strategy/ and modes/. The chat_log field was decoded for a long time while nothing read it
- find the remaining cases of that shape. Also audit what the replay/timeline exposes that
we could exploit (rooms, vents, task locations, body reports, emergency buttons, movement).
Rank by how much signal is being thrown away and how cheaply it could be wired in.`,
  },
]

phase('Recon')
log('Fanning out four independent reviewers over scoring, winners, our failures, and unused signal')

const recon = await parallel(
  LENSES.map((l) => () =>
    agent(`${CONTEXT}\n\n---\n\nYOUR ASSIGNMENT (${l.key}):\n${l.prompt}\n\nReturn your findings via the structured schema. Ground every claim in a computed number or a file:line.`,
      { label: `recon:${l.key}`, phase: 'Recon', schema: FINDINGS })
  )
)

const allFindings = recon.filter(Boolean).flatMap((r, i) =>
  (r.findings || []).map((f) => ({ ...f, lens: LENSES[i] ? LENSES[i].key : 'unknown' }))
)
log(`${allFindings.length} findings from ${recon.filter(Boolean).length}/${LENSES.length} reviewers`)

phase('Hypotheses')
const synth = await agent(
  `${CONTEXT}\n\n---\n\nFour reviewers each surveyed a different angle. Their findings:\n\n` +
  JSON.stringify(allFindings, null, 1) +
  `\n\nSynthesise these into AT MOST 4 improvement hypotheses, ranked by expected reward/episode gain.

Rules:
- Each must name ONE scoped change (file + constant/function), so the next A/B is attributable.
- Each must pin a MECHANISM: why we lose points now, tied to a rule, threshold or code path.
  "It would probably help" is not a mechanism.
- Pre-register a falsifiable predicted effect and a single target metric.
- Prefer levers on the IMPOSTER side unless a crew lever is clearly worth more - imposter
  wins pay 3x and are ~77% of our current deficit.
- Do NOT re-propose anything already tested and rejected (vote bar 0.65; the crew-side
  chat-accusation cue). Building on watts:v4's imposter voting is fine and encouraged.
- Verify each change is actually implementable: read the code you are naming.
- Be honest about expected_reward_gain. Our mean is 0.655, the field's is 0.764, so the
  entire gap is 0.109. Anything claiming more than that is wrong.`,
  { label: 'synthesise', phase: 'Hypotheses', schema: HYPOTHESES, effort: 'high' }
)

const hyps = (synth && synth.hypotheses) || []
log(`${hyps.length} hypotheses proposed; sending each to 2 adversarial skeptics`)

phase('Verify')
const verdicts = await parallel(
  hyps.flatMap((h, i) =>
    ['mechanism', 'evidence'].map((lens) => () =>
      agent(`${CONTEXT}\n\n---\n\nYou are a SKEPTIC. Try to REFUTE this proposal. Default to refuted=true when uncertain.\n\n` +
        JSON.stringify(h, null, 1) +
        `\n\nYour lens: ${lens === 'mechanism'
          ? 'Is the stated mechanism real? Read the code it names and confirm the code path actually behaves as claimed, and that the change is implementable and would fire in real games. A mechanism that cannot fire is refuted.'
          : 'Is the evidence sound? Re-check the numbers against the data on disk. Watch for: mixed-role vs role-matched comparisons, small-n noise (a 10-vote sample can swing 30 points), roster drift between measurement and test, and correlation mistaken for causation.'}\n\nBe specific about what would have to be true for this to work, and whether it is.`,
        { label: `verify:${lens}:${i}`, phase: 'Verify', schema: VERDICT })
    )
  )
)

const survivors = hyps.filter((h, i) => {
  const pair = [verdicts[i * 2], verdicts[i * 2 + 1]].filter(Boolean)
  const refuted = pair.filter((v) => v.refuted).length
  return pair.length > 0 && refuted < 2   // killed only if BOTH skeptics refute
})
log(`${survivors.length}/${hyps.length} hypotheses survived adversarial review`)

phase('Plan')
const plan = await agent(
  `${CONTEXT}\n\n---\n\nThese hypotheses survived adversarial review:\n\n` +
  JSON.stringify(survivors, null, 1) +
  `\n\nAnd here is what every skeptic said, including about the ones that died:\n\n` +
  JSON.stringify(hyps.map((h, i) => ({ title: h.title, verdicts: [verdicts[i * 2], verdicts[i * 2 + 1]] })), null, 1) +
  `\n\nWrite the implementation plan, in priority order. For each surviving hypothesis give:
1. the exact edit (file, function/constant, what changes and to what value, and why that value)
2. the unit tests that would pin the behaviour
3. the A/B design that would measure it: forced role, episode count, target metric, and the
   pre-registered pass/fail threshold
4. what the skeptics flagged that we must watch for

Then state which ONE to do first and why. Note explicitly anything a skeptic raised that
the plan does not resolve. Plain prose, no schema.`,
  { label: 'plan', phase: 'Plan', effort: 'high' }
)

return { findings: allFindings, hypotheses: hyps, verdicts, survivors, plan }
