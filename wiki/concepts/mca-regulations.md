---
title: MCA 2026 Sporting Regulations (scoring & qualification)
type: concept
sources:
  - docs/reference/2026-MCA-Sporting-Regulations.pdf
  - src/raspberry_pab/race_results/mca_scoring.py
  - user (2026-09-27)
updated: 2026-09-27
---

# MCA 2026 Sporting Regulations — scoring & qualification

Source: [2026 Sporting Regulations](../../docs/reference/2026-MCA-Sporting-Regulations.pdf),
effective 2026-06-01. Page numbers are the printed page numbers. This page
covers what the code relies on; see the PDF for conduct, equipment and
course rules.

## Individual race points (Ch. 11, p. 18; Appendix A, pp. 32–33)

- Every finisher earns points from the **Appendix A** grid. There are three
  columns: Varsity (575 for 1st), JV3 (540) and JV2/Freshman/MS (500). The
  Varsity +75 and JV3 +40 bonuses are already in the grid.
- **Places 51 and below:** 1 point less for each place after 50th. This is
  implemented as `points_for_place` in `mca_scoring.py`.
- **Pulled riders** are placed and earn points. A **DNF** earns 0 points.
  IYR lists DNFs with a place; see the detection rule in
  [team standings](../features/team-standings.md).
- **D1/D2:** individual scoring is split by division only when the divisions
  race as separate categories. For example, Freshman Boys D1 and D2 are
  scored separately, while JV3 Boys D1 and D2 are scored together.

## Season average (p. 18–19)

- **Formula:** average of points over every regular-season race the rider
  **could have completed**, meaning races the team was scheduled for and that
  were held. For example, (R1 + R2 + R3 + R4) / 4.
- **Missed races:** if the team was scheduled and the rider didn't race, it
  counts as **0** and stays in the average. Bye weeks don't count.
- **Rainouts and cancellations:** the race is left out of both the points
  and the count (/3 instead of /4). For riders on teams that were there, the
  canceled day neither helps nor hurts, but each remaining race weighs more
  (1/3 instead of 1/4). Cancellations can hit just one day, e.g. the HS race at
  Theodore Wirth on 2026-09-27.
- **Category change:** only races in the new category count. MCA's standings
  show the earlier races as `NA (Upgrade)`.
- **Season score with State:** the regular-season average plus the State
  Championship score.
- **4-race limit:** each team (and so each racer) does **at most 4
  regular-season races** (user, 2026-09-27; consistent with the p. 19 example
  and the transfer cap on p. 20). A canceled race still uses one of the team's
  4 slots.

> ⚠ Conflict: p. 19 says a rainout shrinks the denominator. The
> transfers section on p. 21 says "in the event of rainouts … there is no
> change to scoring". The code follows p. 19. MCA's published standings
> (the "through Race N" PDFs) are the authority when in doubt.

## State Championship qualification (p. 21–22)

- **Who qualifies:** the **top 100 riders in each race category**, by
  cumulative standings after the **final regular-season race**. Categories
  split by division (e.g. JV2 Boys D1 and D2) qualify separately.
- **Eligibility:** riders must have **registered for at least 2
  regular-season races**.
- **No exceptions:** a qualified rider who opts out doesn't open a spot, and
  there are no petitions.
- **Senior Open:** non-qualifying seniors who have ≥2 races can race the
  Senior Open. It uses the JV2 distance and earns no points.
- **2026 venue:** the State Championship is at **Redhead, Chisholm MN
  (Oct 10–11, IYR 17339)** (user, 2026-09-27).

## Team scoring (p. 22)

- **HS D1:** top 8 riders, at most 6 of either gender.
- **HS D2 and all MS:** top 4 riders, at most 3 of either gender.
- **Season team score:** the average team score across regular-season
  races, plus the State score. Senior Open points don't count.
- **Team penalties** (e.g. 25/50/100 points, 200 points for staging cuts;
  pp. 10, 14, 15, 31) aren't published on ITS YOUR RACE.

## Call-ups (Ch. 9, pp. 15–16)

Call-ups use the current-season average finish position. The first race uses
the previous season's average (×1.3 after moving up a category). 6th graders
and new riders get random call-ups. State uses the standard call-up rule.

Related: [team standings](../features/team-standings.md),
[state qualification](../features/state-qualification.md).
