% Optional GNU Octave / MATLAB parity checks. No proprietary toolbox needed.
% These are executable numerical checks, not Lean proofs or CoppeliaSim runs.
r = 0.0975; b = 0.381; limit = 6;
wrap_angle = @(a) mod(a + pi, 2*pi) - pi;
assert(wrap_angle(pi) == -pi);
assert(wrap_angle(-pi) == -pi);
v = 2; omega = 3;
wl = (v - b*omega/2) / r;
wr = (v + b*omega/2) / r;
scale = max([1, abs(wl)/limit, abs(wr)/limit]);
limited = [wl, wr] / scale;
assert(max(abs(limited)) <= limit + 1e-12);
assert(abs(limited(1)*wr-limited(2)*wl) < 1e-10);
% Row-vector CCW transform uses transposed rotation matrix.
theta = pi/2;
rotation = [cos(theta), -sin(theta); sin(theta), cos(theta)];
rotated = [1, 0] * rotation';
assert(norm(rotated-[0,1]) < 1e-12);
assert(norm([1,0]*rotation-[0,1]) > 1);
disp('Octave/MATLAB algebra and endpoint checks passed.');
