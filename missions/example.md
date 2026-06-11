# Mission format

A mission is just a plain-text goal. The loop feeds it to the agent as the
GOAL, and the agent works step by step until it emits `[MISSION_COMPLETED]`.

Write the goal so "done" is checkable — the clearer the finish line, the
cleaner the loop terminates.

---

## Example goal (delete this header and the lines above when writing your own)

Create a small Python project in the workspace that:

1. Has a file `fizzbuzz.py` with a `fizzbuzz(n)` function returning the
   FizzBuzz string for the numbers 1..n (one per line).
2. Has a file `test_fizzbuzz.py` with at least 3 assertions covering the
   "Fizz", "Buzz", and "FizzBuzz" cases.
3. Passes when you run `python -m pytest -q` (install pytest if needed).

Verify the tests actually pass via the run_bash tool before declaring the
mission complete.
