# Internal vs External Conflicts

*Auto-generated comparison of internal learning against external specifications.*

**Last Updated:** Not yet updated

---

## Summary

| Status | Count |
|--------|-------|
| Confirmed (internal agrees with external) | 0 |
| Conflicts (internal differs from external) | 0 |
| Pending (insufficient sample size) | 0 |

---

## Confirmed Agreements

*No confirmed agreements yet. These will appear when internal learning validates external spec rules.*

---

## Conflicts

*No conflicts detected yet. Conflicts appear when internal performance data suggests different optimal values than external specs.*

### Conflict Format

When conflicts are detected, they will be recorded as:

```
### [Conflict ID] - [Topic]
**External Spec:** [Source document] says [rule]
**Internal Data:** Based on [N] runs, performance suggests [alternative]
**Sample Size:** [N] runs
**Statistical Confidence:** [%]
**Resolution:** [External preferred | Internal preferred | Manual review needed]
**Scope:** [Global | Niche: X | Style: Y | Visual Mode: Z]
```

---

## Pending Analysis

*Items awaiting sufficient sample size (threshold: 10 runs per niche/style combination).*

---

## Resolution Policy

1. External specs are **never modified** by the engine
2. Internal data takes precedence only when:
   - Sample size >= 10 runs for the specific niche/style
   - The difference is statistically significant (>15% performance delta)
3. All conflicts are logged here for manual review
4. User can override any conflict resolution in `rule_overrides.json`
