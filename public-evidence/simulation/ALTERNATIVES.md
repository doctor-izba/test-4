# Free simulation options, checked 3 November 2026

| Option | Cost/license basis | Useful cloud role | Material limitation |
|---|---|---|---|
| Included Python surrogate | Python stdlib, original implementation | Fast deterministic boundary tests, supplementary experiments, CSV/SVG evidence on a standard runner | Kinematic approximation; no calibrated Pioneer/contact dynamics; not assignment's mandated tools |
| GNU Octave | GPL free software; official site says largely MATLAB-compatible | Execute portable `.m` policy/algebra tests, plots and numerical replay | MATLAB classes/toolboxes and an existing remote-API client need compatibility testing; not accepted as MATLAB by assumption |
| Webots | Open-source simulator, repository Apache-2.0 license | Future physics/Pioneer port with headless/batch execution and rendering setup | Rebuild robot/world/sensors and validate physics; a completed Webots port has not been implemented here |
| CoppeliaSim Edu | Free for eligible educational users under Edu terms | Actual required simulator, optionally Linux headless on a runner; remote APIs include Python and Octave | Eligibility/registration and package setup must be respected; not a blanket unrestricted commercial license; simulation GUI/video/headless differences matter |

Primary sources:

- GNU Octave: https://octave.org/ (free software, GPL, broad MATLAB syntax compatibility).
- Webots official overview: https://cyberbotics.com/ (desktop simulator, Python/MATLAB controllers, physics and export options).
- Webots license: https://github.com/cyberbotics/webots/blob/master/LICENSE (Apache License 2.0; individual assets can carry separate notices).
- CoppeliaSim official product/licensing text: https://www.coppeliarobotics.com/ and feature overview https://manual.coppeliarobotics.com/en/coppeliaSimFeatures.htm . Educational eligibility is specific; do not interpret “free” as permission for every entity/use.
- CoppeliaSim headless flags: https://manual.coppeliarobotics.com/en/commandLine.htm . `-H` and `-h` are distinct modes; official docs still note display-server requirements and vision-rendering restrictions in true headless mode.
- CoppeliaSim ZeroMQ API: https://manual.coppeliarobotics.com/en/zmqRemoteApiOverview.htm (stepping and Python client; compatible language clients require actual adapter validation).

The most immediate free setup is Python tests plus Lean on Linux GitHub Actions,
with the already-installed MATLAB/CoppeliaSim used locally for mandated evidence.
Octave and Webots are valuable optional checks/ports, not a reason to relabel
unexecuted replacement code as finished assignment evidence.
