# Research and design worker

Own research/. Read PROJECT_BRIEF and existing simulation/ and lean/ README files.
Acquire actual sources using fetch_url, not just a bibliography. Use research/raw/
for full original HTML/PDF and research/notes/ for your original extracts/explanations.
Use pdftotext to examine relevant PDF sections, but do not publish full books in
notes. Respect access restrictions; author-hosted/preprints/open documentation suffice.

Starting primary sources:
- https://hades.mech.northwestern.edu/images/2/25/MR-v2.pdf
- https://www.roboticsbook.org/S52_diffdrive_actions.html
- https://manual.coppeliarobotics.com/en/remoteApiOverview.htm
- https://manual.coppeliarobotics.com/en/regularApi/simReadProximitySensor.htm
- https://manual.coppeliarobotics.com/en/regularApi/simCheckCollision.htm
- https://docs.octave.org/latest/
- https://github.com/cyberbotics/webots
- https://github.com/leanprover-community/mathlib4

Deliver research/notes/design_decisions.md with derivations for differential drive,
midpoint encoder odometry, sensor offset versus footprint clearance, final front
gate, lost-wall timing, conservative turn footprint and a practical controller
comparison. Cite exact supporting sections/equations where actually inspected.
Create research/notes/source_manifest.json with source URL, retrieved bytes/hash,
access basis, relevant section, decision and test. No indefinite literature search.
Explain Octave numerical parity and Webots/Python/Coppelia alternatives honestly.
Conclude with requirements/source/design/test map and your handoff. This is actual
research work; do not simply restate this prompt or invent citations.
