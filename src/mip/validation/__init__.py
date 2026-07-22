"""Out-of-sample validation of the historical analogue model.

Research tooling, deliberately outside the production scoring path: it
REUSES the frozen production components (models, normalizer, decision
combination, trim transformation) and never modifies them. Artifacts are
written under data/validation/ (gitignored)."""
