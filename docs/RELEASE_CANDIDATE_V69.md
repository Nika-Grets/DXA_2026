# V6.9 Release Candidate

## Packaging

- pinned `requirements.txt`
- Dockerfile
- docker-compose.yml
- `.env.example`
- `.dockerignore`
- root README

## Production path frozen

The V6.8.5 production path remains the default. Experimental landmarks and ROI models are not silently promoted.

## Verification checklist

- [x] canonical manifest uses real StudyInstanceUID
- [x] study-level grouping
- [x] two-image routing regression fixed
- [x] quality_prob in [0,1]
- [x] OOF provenance recorded
- [x] calibration provenance recorded
- [x] Docker configuration added
- [x] dependency versions pinned
- [x] production security settings documented
- [x] health endpoint documented
- [ ] full pytest in an environment with installed dependencies
- [ ] Docker build/run in a Docker-capable CI/host
- [ ] final closed test evaluation by organiser

## Acceptance rule

Do not report development OOF values as final independent test performance. Do not claim detection quality for `Для теста.zip`, because it is a format/debug fragment without expert labels.
