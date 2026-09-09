## Summary

<!-- What does this PR do and why? Link to issue/roadmap item if applicable. -->

## Changes

- <!-- list key changes -->

## Verification

<!-- Commands you ran + results. Keep to the CI-equivalent set from CONTRIBUTING. -->

- [ ] Backend: `ruff format --check . && ruff check .`
- [ ] Backend: `env -i PATH="$PATH" HOME="$HOME" python -m pytest` (clean env)
- [ ] Frontend: `npm ci && npm run format:check && npm run lint && npm test && npm run build`
- [ ] CI checks green on this PR

## Notes / follow-ups

<!-- Anything the reviewer should know: migrations, secrets, deploy impact, ratchet items. -->
