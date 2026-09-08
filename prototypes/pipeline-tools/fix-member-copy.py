from pathlib import Path
p=Path('../pipeline-hifi/src/routes/OnboardingRoutes.tsx')
s=p.read_text().replace('Simulate member invitation','Add local member')
p.write_text(s)
