# Dopamine Content Engine Specification

## 1. Purpose

This document defines the structural rules for integrating the Dopamine Ladder framework into the Content Engine pipeline.

The system must enforce dopamine-stage-aware generation across all content modes.

This is required validation logic — not optional guidance.

---

## 2. Dopamine Ladder Framework (Engineering Definition)

Each generated content run MUST include the following structured components.

### Level 1 — Stimulation
**Goal:** Interrupt scroll within first 1–2 seconds.

**Required Output:**
- High-contrast visual plan
- Motion element defined
- Brightness separation noted
- Feed-disruption tactic specified

**Failure Conditions:**
- Static first frame
- Generic talking head without motion
- No contrast defined

---

### Level 2 — Captivation
**Goal:** Trigger an internal curiosity question.

**Required Output:**
- Explicit curiosity question OR
- Implied mystery setup

**Validation Rule:**
Script must contain at least one open loop before 5 seconds.

**Failure Conditions:**
- Informational statement with no tension
- Immediate explanation without suspense

---

### Level 3 — Anticipation
**Goal:** Increase dopamine by delaying resolution.

**Required Output:**
- At least one anticipation beat
- Context expansion OR misdirection OR escalation

**Validation Rule:**
The answer must not be delivered immediately after the question.
A minimum anticipation gap is required.

---

### Level 4 — Validation
**Goal:** Close the loop and deliver payoff.

**Required Output:**
- Clear answer OR resolution
- Preferably non-obvious value

**Failure Conditions:**
- No resolution
- Cliffhanger without intentional design

---

### Level 5 — Affection (Brand Layer)
**Goal:** Increase creator trust and likability.

**Required Output (at least one):**
- Personality signal
- Authority marker
- Trust-building micro-moment
- Demonstrated value delivery

---

### Level 6 — Revelation (Long-Term Association)
**Goal:** Position creator as consistent value source.

**Required Output (at least one):**
- Future value signal
- Category authority positioning
- Repeatable promise
- Series implication

---

## 3. Content Modes

The engine must support three modes.

### Mode A — AI Generated

**Outputs Required:**
- Script
- NanoBanana prompt
- Visual motion plan
- Dopamine ladder breakdown
- Hook optimization notes

---

### Mode B — Real Shoot Plan

Instead of AI prompts, generate:

**Outputs Required:**
- Shot list
- Lens suggestion
- Lighting direction
- Camera movement
- Visual contrast notes
- Performance direction
- Anticipation beats mapped to physical action

---

### Mode C — Hybrid

**Outputs Required:**
- Real shoot segments
- AI insert opportunities
- Enhancement points
- Dopamine escalation strategy

---

## 4. Hook Optimizer Module

If image input is provided, the system must analyze:

- Color contrast score
- Motion potential score
- Brightness separation
- Feed disruption probability

**Output:**
- Improvement recommendations
- Revised hook strategy

---

## 5. Pipeline Integration Rules

Dopamine validation must occur during:
- Script generation
- Script regeneration
- Shot planning

If dopamine requirements are not met:
- System must revise output
- Or flag generation as invalid

---

## 6. Enforcement Requirements

The system must:
- Prevent premature validation
- Prevent missing curiosity loops
- Ensure at least one anticipation escalation
- Ensure brand-layer presence in final output

---

## 7. Config Example

```yaml
content_run:
  mode: hybrid
  category: educational
  dopamine_focus: strong_anticipation
  enforce_validation: true
```

---

END OF SPECIFICATION
