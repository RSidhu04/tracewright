# Statistical interpretation

Let d_i be the candidate-minus-baseline difference in pass fraction for case i, averaged over that case's repeated trials. Each d_i is in [-1,1]. For n cases the overall delta is their mean. A two-sided Hoeffding interval with error probability alpha has radius `sqrt(2 * log(2 / alpha) / n)`, clipped to the possible parameter range [-1,1]. Default alpha is 0.05.

The probability guarantee requires independent case-level observations sampled representatively from the target population. Curated suites, duplicate cases, related repositories, shared provider incidents, or agent state can violate these assumptions. For a fixed handpicked suite, emphasize the descriptive result. The interval does not certify population reliability merely because it was computed.

Repeated trials improve each case's measured pass fraction but do not add independent cases. Matching seeds enable pairing; they do not guarantee common random numbers in a remote provider. The interval is conservative and can remain wide even with many cases. A zero observed delta does not prove noninferiority.

A regression is statistically supported only when the upper endpoint is below `-tolerance`. Noninferiority is supported only when the lower endpoint is at least `-tolerance`. Otherwise the result is inconclusive. The statistical gate fails for both regression and inconclusive outcomes.

Per-case drops drive the observed gate without p-values or per-case significance claims. No multiple-comparison correction is implemented. Predeclare the candidate, suite, tolerance, and alpha; use a held-out set and an explicit correction policy for repeated model/prompt selection. Requiring all assertions per trial is a specified binary metric, not a universal measure of answer quality.

Durations, SWE-bench error categories, provider costs, and token counts are not covered by this interval. No LLM judge or calibration claim enters the score.
