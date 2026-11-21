# FlatJai evaluation

## E1 and E2: systems and ablations on the suite (95% bootstrap intervals over cases)

| Metric | b0 | b1 | flatjai | flatjai-model_facts | flatjai-no_dedup | flatjai-no_reflect |
|---|---|---|---|---|---|---|
| Constraint satisfaction | 100% [100–100] | 71% [38–100] | 100% [100–100] | 76% [53–94] | 100% [100–100] | 100% [100–100] |
| All limits confirmed | 100% [100–100] | 36% [0–71] | 52% [40–64] | 44% [18–69] | 56% [37–73] | 58% [30–82] |
| Invented facts | 85% [76–92] | 44% [31–60] | 0% [0–0] | 0% [0–0] | 0% [0–0] | 0% [0–0] |
| Invented listings | 100% [100–100] | 0% [0–0] | 0% [0–0] | 0% [0–0] | 0% [0–0] | 0% [0–0] |
| Correct ask/no-ask | 85% [75–93] | 85% [75–93] | 100% [100–100] | 100% [100–100] | 100% [100–100] | 100% [100–100] |
| Outcome ok | 12% [5–20] | 15% [7–25] | 100% [100–100] | 85% [70–100] | 100% [100–100] | 90% [75–100] |
| Duplicate homes shown | 63% [45–77] | 0% [0–0] | 0% [0–0] | 0% [0–0] | 3% [0–7] | 0% [0–0] |
| Cost figures off the cost tool | – | – | – | 100% [100–100] | 0% [0–0] | 0% [0–0] |
| Homes shown per case | 0.6 | 0.7 | 3.5 | 2.7 | 3.6 | 2.6 |
| Seconds per case (median) | 2.8 | 8.1 | 26.3 | 38.2 | 26.4 | 17.4 |
| Model calls per case (median) | 1.0 | 2.0 | 6.0 | 11.0 | 4.5 | 3.0 |
| Tokens per case (median) | 163.0 | 4063.5 | 2628.5 | 3938.0 | 2586.5 | 1985.5 |
| Commute error vs router, min (median / max) | n/a | n/a | n/a | 17 / 29 | 0 / 0 | 0 / 0 |

Cases: b0 60, b1 60, flatjai 60, flatjai-model_facts 20, flatjai-no_dedup 20, flatjai-no_reflect 20.

## By category

| Category | System | Cases | Homes | Constraint sat. | Invented facts | Ask ok | Outcome ok |
|---|---|---|---|---|---|---|---|
| standard | b0 | 18 | 15 | 100% | 100% | 100% | 17% |
| standard | b1 | 18 | 15 | 100% | 73% | 100% | 17% |
| standard | flatjai | 18 | 69 | 100% | 0% | 100% | 100% |
| standard | flatjai-model_facts | 6 | 11 | 45% | 0% | 100% | 67% |
| standard | flatjai-no_dedup | 6 | 24 | 100% | 0% | 100% | 100% |
| standard | flatjai-no_reflect | 6 | 14 | 100% | 0% | 100% | 83% |
| missing_info | b0 | 9 | 15 | 100% | 100% | 0% | 33% |
| missing_info | b1 | 9 | 0 | – | – | 0% | 0% |
| missing_info | flatjai | 9 | 39 | 100% | 0% | 100% | 100% |
| missing_info | flatjai-model_facts | 3 | 13 | 100% | 0% | 100% | 100% |
| missing_info | flatjai-no_dedup | 3 | 13 | 100% | 0% | 100% | 100% |
| missing_info | flatjai-no_reflect | 3 | 12 | 100% | 0% | 100% | 100% |
| infeasible | b0 | 9 | 0 | – | 50% | 100% | 0% |
| infeasible | b1 | 9 | 0 | – | 67% | 100% | 0% |
| infeasible | flatjai | 9 | 0 | – | – | 100% | 100% |
| infeasible | flatjai-model_facts | 3 | 0 | – | – | 100% | 100% |
| infeasible | flatjai-no_dedup | 3 | 0 | – | – | 100% | 100% |
| infeasible | flatjai-no_reflect | 3 | 0 | – | – | 100% | 100% |
| mixed_language | b0 | 9 | 0 | – | 67% | 100% | 0% |
| mixed_language | b1 | 9 | 0 | – | 50% | 100% | 0% |
| mixed_language | flatjai | 9 | 36 | 100% | 0% | 100% | 100% |
| mixed_language | flatjai-model_facts | 3 | 11 | 82% | 0% | 100% | 100% |
| mixed_language | flatjai-no_dedup | 3 | 12 | 100% | 0% | 100% | 100% |
| mixed_language | flatjai-no_reflect | 3 | 7 | 100% | 0% | 100% | 100% |
| ambiguous_location | b0 | 6 | 0 | – | – | 100% | 0% |
| ambiguous_location | b1 | 6 | 12 | 0% | 23% | 100% | 50% |
| ambiguous_location | flatjai | 6 | 24 | 100% | 0% | 100% | 100% |
| ambiguous_location | flatjai-model_facts | 2 | 9 | 100% | 0% | 100% | 100% |
| ambiguous_location | flatjai-no_dedup | 2 | 9 | 100% | 0% | 100% | 100% |
| ambiguous_location | flatjai-no_reflect | 2 | 9 | 100% | 0% | 100% | 100% |
| adversarial | b0 | 3 | 5 | 100% | 88% | 100% | 33% |
| adversarial | b1 | 3 | 15 | 100% | 0% | 100% | 100% |
| adversarial | flatjai | 3 | 15 | 100% | 0% | 100% | 100% |
| adversarial | flatjai-model_facts | 1 | 5 | 100% | 0% | 100% | 100% |
| adversarial | flatjai-no_dedup | 1 | 5 | 100% | 0% | 100% | 100% |
| adversarial | flatjai-no_reflect | 1 | 5 | 100% | 0% | 100% | 100% |
| multi_turn | b0 | 6 | 0 | – | 100% | 100% | 0% |
| multi_turn | b1 | 6 | 0 | – | 67% | 100% | 0% |
| multi_turn | flatjai | 6 | 24 | 100% | 0% | 100% | 100% |
| multi_turn | flatjai-model_facts | 2 | 5 | 0% | 0% | 100% | 50% |
| multi_turn | flatjai-no_dedup | 2 | 9 | 100% | 0% | 100% | 100% |
| multi_turn | flatjai-no_reflect | 2 | 5 | 100% | 0% | 100% | 50% |

## Limits checked on shown homes (ok / violated / unknown)

| System | Limit | ok | violated | unknown |
|---|---|---|---|---|
| b0 | budget | 35 | 0 | 0 |
| b0 | room | 35 | 0 | 0 |
| b0 | bedrooms | 30 | 0 | 0 |
| b0 | commute | 15 | 0 | 0 |
| b1 | budget | 39 | 3 | 0 |
| b1 | room | 15 | 12 | 15 |
| b1 | bedrooms | 15 | 0 | 0 |
| b1 | commute | 15 | 0 | 0 |
| flatjai | budget | 207 | 0 | 0 |
| flatjai | room | 113 | 0 | 94 |
| flatjai | commute | 108 | 0 | 6 |
| flatjai | bedrooms | 3 | 0 | 36 |
| flatjai-model_facts | budget | 54 | 0 | 0 |
| flatjai-model_facts | room | 36 | 0 | 18 |
| flatjai-model_facts | commute | 9 | 13 | 0 |
| flatjai-model_facts | bedrooms | 0 | 0 | 5 |
| flatjai-no_dedup | budget | 72 | 0 | 0 |
| flatjai-no_dedup | room | 41 | 0 | 31 |
| flatjai-no_dedup | commute | 39 | 0 | 1 |
| flatjai-no_dedup | bedrooms | 2 | 0 | 11 |
| flatjai-no_reflect | budget | 52 | 0 | 0 |
| flatjai-no_reflect | room | 30 | 0 | 22 |
| flatjai-no_reflect | bedrooms | 1 | 0 | 10 |
| flatjai-no_reflect | commute | 21 | 0 | 0 |

## Every case

| System | Case | Rep | Homes | Violated | Facts ok | Asked | Outcome | Profile | s | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| b0 | std-hkust-own-room-9k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | std-hkust-2bed-30k-total | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hku-studio-15k | 0 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-cityu-room-7k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-cuhk-room-6k | 0 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-polyu-1bed-18k | 0 | 5 | 0 | 0/5 | no | ok |  | 28 |  |
| b0 | miss-cheap-room | 0 | 0 | 0 | 0/0 | no | FAIL |  | 3 |  |
| b0 | miss-2bed-near-campus | 0 | 5 | 0 | 0/5 | no | ok |  | 32 |  |
| b0 | miss-flat-budget-only | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-hku-2bed-8k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-cityu-3bed-10k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | zh-hkust-room-8k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b0 | zh-hku-flat-15k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 4 |  |
| b0 | zh-cuhk-room-mixed | 0 | 0 | 0 | 0/1 | no | FAIL |  | 2 |  |
| b0 | loc-hang-hau-room | 0 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | loc-kennedy-town-studio | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | adv-brief-injection | 0 | 0 | 0 | 0/1 | no | FAIL |  | 2 |  |
| b0 | multi-lower-budget | 0 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | multi-shorter-commute | 0 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hkust-own-room-9k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hkust-2bed-30k-total | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hku-studio-15k | 1 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-cityu-room-7k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-cuhk-room-6k | 1 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-polyu-1bed-18k | 1 | 5 | 0 | 0/5 | no | ok |  | 28 |  |
| b0 | miss-cheap-room | 1 | 0 | 0 | 0/0 | no | FAIL |  | 3 |  |
| b0 | miss-2bed-near-campus | 1 | 5 | 0 | 0/5 | no | ok |  | 32 |  |
| b0 | miss-flat-budget-only | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-hku-2bed-8k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | inf-hkust-studio-4k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-cityu-3bed-10k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | zh-hkust-room-8k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | zh-hku-flat-15k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 4 |  |
| b0 | zh-cuhk-room-mixed | 1 | 0 | 0 | 0/1 | no | FAIL |  | 2 |  |
| b0 | loc-hang-hau-room | 1 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | loc-kennedy-town-studio | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | adv-brief-injection | 1 | 5 | 0 | 1/6 | no | ok |  | 18 |  |
| b0 | multi-lower-budget | 1 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | multi-shorter-commute | 1 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hkust-own-room-9k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hkust-2bed-30k-total | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-hku-studio-15k | 2 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-cityu-room-7k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | std-cuhk-room-6k | 2 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | std-polyu-1bed-18k | 2 | 5 | 0 | 0/5 | no | ok |  | 28 |  |
| b0 | miss-cheap-room | 2 | 0 | 0 | 0/0 | no | FAIL |  | 3 |  |
| b0 | miss-2bed-near-campus | 2 | 5 | 0 | 0/5 | no | ok |  | 32 |  |
| b0 | miss-flat-budget-only | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-hku-2bed-8k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | inf-hkust-studio-4k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | inf-cityu-3bed-10k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 3 |  |
| b0 | zh-hkust-room-8k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | zh-hku-flat-15k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 4 |  |
| b0 | zh-cuhk-room-mixed | 2 | 0 | 0 | 0/1 | no | FAIL |  | 2 |  |
| b0 | loc-hang-hau-room | 2 | 0 | 0 | 0/0 | no | FAIL |  | 4 |  |
| b0 | loc-kennedy-town-studio | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b0 | adv-brief-injection | 2 | 0 | 0 | 0/1 | no | FAIL |  | 2 |  |
| b0 | multi-lower-budget | 2 | 0 | 0 | 0/1 | no | FAIL |  | 3 |  |
| b0 | multi-shorter-commute | 2 | 0 | 0 | 0/0 | no | FAIL |  | 2 |  |
| b1 | std-hkust-own-room-9k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | std-hkust-2bed-30k-total | 0 | 0 | 0 | 0/0 | no | FAIL |  | 7 |  |
| b1 | std-hku-studio-15k | 0 | 0 | 0 | 0/1 | no | FAIL |  | 10 |  |
| b1 | std-cityu-room-7k | 0 | 0 | 0 | 1/1 | no | FAIL |  | 11 |  |
| b1 | std-cuhk-room-6k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 16 |  |
| b1 | std-polyu-1bed-18k | 0 | 5 | 0 | 0/5 | no | ok |  | 36 |  |
| b1 | miss-cheap-room | 0 | 0 | 0 | 0/0 | no | FAIL |  | 8 |  |
| b1 | miss-2bed-near-campus | 0 | 0 | 0 | 0/0 | no | FAIL |  | 7 |  |
| b1 | miss-flat-budget-only | 0 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b1 | inf-hku-2bed-8k | 0 | 0 | 0 | 1/3 | no | FAIL |  | 8 |  |
| b1 | inf-hkust-studio-4k | 0 | 0 | 0 | 0/1 | no | FAIL |  | 8 |  |
| b1 | inf-cityu-3bed-10k | 0 | 0 | 0 | 1/2 | no | FAIL |  | 9 |  |
| b1 | zh-hkust-room-8k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b1 | zh-hku-flat-15k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 10 |  |
| b1 | zh-cuhk-room-mixed | 0 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | loc-hang-hau-room | 0 | 0 | 0 | 1/3 | no | FAIL |  | 11 |  |
| b1 | loc-kennedy-town-studio | 0 | 4 | 4 | 9/10 | no | ok |  | 41 |  |
| b1 | adv-brief-injection | 0 | 5 | 0 | 6/6 | no | ok |  | 33 |  |
| b1 | multi-lower-budget | 0 | 0 | 0 | 1/2 | no | FAIL |  | 7 |  |
| b1 | multi-shorter-commute | 0 | 0 | 0 | 0/1 | no | FAIL |  | 9 |  |
| b1 | std-hkust-own-room-9k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 9 |  |
| b1 | std-hkust-2bed-30k-total | 1 | 0 | 0 | 0/0 | no | FAIL |  | 8 |  |
| b1 | std-hku-studio-15k | 1 | 0 | 0 | 0/1 | no | FAIL |  | 9 |  |
| b1 | std-cityu-room-7k | 1 | 0 | 0 | 1/1 | no | FAIL |  | 6 |  |
| b1 | std-cuhk-room-6k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 7 |  |
| b1 | std-polyu-1bed-18k | 1 | 5 | 0 | 0/5 | no | ok |  | 36 |  |
| b1 | miss-cheap-room | 1 | 0 | 0 | 0/0 | no | FAIL |  | 8 |  |
| b1 | miss-2bed-near-campus | 1 | 0 | 0 | 0/0 | no | FAIL |  | 7 |  |
| b1 | miss-flat-budget-only | 1 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b1 | inf-hku-2bed-8k | 1 | 0 | 0 | 1/3 | no | FAIL |  | 8 |  |
| b1 | inf-hkust-studio-4k | 1 | 0 | 0 | 0/1 | no | FAIL |  | 8 |  |
| b1 | inf-cityu-3bed-10k | 1 | 0 | 0 | 1/2 | no | FAIL |  | 7 |  |
| b1 | zh-hkust-room-8k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 6 |  |
| b1 | zh-hku-flat-15k | 1 | 0 | 0 | 0/0 | no | FAIL |  | 10 |  |
| b1 | zh-cuhk-room-mixed | 1 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | loc-hang-hau-room | 1 | 0 | 0 | 1/3 | no | FAIL |  | 9 |  |
| b1 | loc-kennedy-town-studio | 1 | 4 | 4 | 9/10 | no | ok |  | 41 |  |
| b1 | adv-brief-injection | 1 | 5 | 0 | 6/6 | no | ok |  | 33 |  |
| b1 | multi-lower-budget | 1 | 0 | 0 | 1/2 | no | FAIL |  | 6 |  |
| b1 | multi-shorter-commute | 1 | 0 | 0 | 0/1 | no | FAIL |  | 8 |  |
| b1 | std-hkust-own-room-9k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | std-hkust-2bed-30k-total | 2 | 0 | 0 | 0/0 | no | FAIL |  | 6 |  |
| b1 | std-hku-studio-15k | 2 | 0 | 0 | 0/1 | no | FAIL |  | 8 |  |
| b1 | std-cityu-room-7k | 2 | 0 | 0 | 1/1 | no | FAIL |  | 6 |  |
| b1 | std-cuhk-room-6k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | std-polyu-1bed-18k | 2 | 5 | 0 | 0/5 | no | ok |  | 38 |  |
| b1 | miss-cheap-room | 2 | 0 | 0 | 0/0 | no | FAIL |  | 8 |  |
| b1 | miss-2bed-near-campus | 2 | 0 | 0 | 0/0 | no | FAIL |  | 7 |  |
| b1 | miss-flat-budget-only | 2 | 0 | 0 | 0/0 | no | FAIL |  | 6 |  |
| b1 | inf-hku-2bed-8k | 2 | 0 | 0 | 1/3 | no | FAIL |  | 9 |  |
| b1 | inf-hkust-studio-4k | 2 | 0 | 0 | 0/1 | no | FAIL |  | 9 |  |
| b1 | inf-cityu-3bed-10k | 2 | 0 | 0 | 1/2 | no | FAIL |  | 7 |  |
| b1 | zh-hkust-room-8k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b1 | zh-hku-flat-15k | 2 | 0 | 0 | 0/0 | no | FAIL |  | 10 |  |
| b1 | zh-cuhk-room-mixed | 2 | 0 | 0 | 1/2 | no | FAIL |  | 8 |  |
| b1 | loc-hang-hau-room | 2 | 0 | 0 | 1/3 | no | FAIL |  | 10 |  |
| b1 | loc-kennedy-town-studio | 2 | 4 | 4 | 9/10 | no | ok |  | 41 |  |
| b1 | adv-brief-injection | 2 | 5 | 0 | 6/6 | no | ok |  | 34 |  |
| b1 | multi-lower-budget | 2 | 0 | 0 | 1/2 | no | FAIL |  | 7 |  |
| b1 | multi-shorter-commute | 2 | 0 | 0 | 0/1 | no | FAIL |  | 10 |  |
| flatjai | std-hkust-own-room-9k | 0 | 4 | 0 | 4/4 | no | ok | ok | 37 |  |
| flatjai | std-hkust-2bed-30k-total | 0 | 3 | 0 | 6/6 | no | ok | ok | 25 |  |
| flatjai | std-hku-studio-15k | 0 | 4 | 0 | 4/4 | no | ok | ok | 36 |  |
| flatjai | std-cityu-room-7k | 0 | 4 | 0 | 4/4 | no | ok | ok | 17 |  |
| flatjai | std-cuhk-room-6k | 0 | 3 | 0 | 3/3 | no | ok | ok | 41 |  |
| flatjai | std-polyu-1bed-18k | 0 | 5 | 0 | 9/9 | no | ok | ok | 20 |  |
| flatjai | miss-cheap-room | 0 | 5 | 0 | 5/5 | yes | ok | ok | 20 |  |
| flatjai | miss-2bed-near-campus | 0 | 5 | 0 | 6/6 | yes | ok | ok | 20 |  |
| flatjai | miss-flat-budget-only | 0 | 3 | 0 | 5/5 | yes | ok | ok | 31 |  |
| flatjai | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 27 |  |
| flatjai | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | zh-hkust-room-8k | 0 | 5 | 0 | 5/5 | no | ok | ok | 23 |  |
| flatjai | zh-hku-flat-15k | 0 | 3 | 0 | 3/3 | no | ok | ok | 31 |  |
| flatjai | zh-cuhk-room-mixed | 0 | 4 | 0 | 5/5 | no | ok | ok | 29 |  |
| flatjai | loc-hang-hau-room | 0 | 5 | 0 | 5/5 | no | ok | ok | 21 |  |
| flatjai | loc-kennedy-town-studio | 0 | 3 | 0 | 6/6 | no | ok | ok | 17 |  |
| flatjai | adv-brief-injection | 0 | 5 | 0 | 5/5 | no | ok | ok | 22 |  |
| flatjai | multi-lower-budget | 0 | 3 | 0 | 3/3 | no | ok | ok | 71 |  |
| flatjai | multi-shorter-commute | 0 | 5 | 0 | 7/7 | no | ok | ok | 49 |  |
| flatjai | std-hkust-own-room-9k | 1 | 4 | 0 | 4/4 | no | ok | ok | 41 |  |
| flatjai | std-hkust-2bed-30k-total | 1 | 3 | 0 | 6/6 | no | ok | ok | 25 |  |
| flatjai | std-hku-studio-15k | 1 | 4 | 0 | 4/4 | no | ok | ok | 36 |  |
| flatjai | std-cityu-room-7k | 1 | 4 | 0 | 4/4 | no | ok | ok | 18 |  |
| flatjai | std-cuhk-room-6k | 1 | 3 | 0 | 3/3 | no | ok | ok | 39 |  |
| flatjai | std-polyu-1bed-18k | 1 | 5 | 0 | 9/9 | no | ok | ok | 23 |  |
| flatjai | miss-cheap-room | 1 | 5 | 0 | 5/5 | yes | ok | ok | 20 |  |
| flatjai | miss-2bed-near-campus | 1 | 5 | 0 | 7/7 | yes | ok | ok | 20 |  |
| flatjai | miss-flat-budget-only | 1 | 3 | 0 | 5/5 | yes | ok | ok | 30 |  |
| flatjai | inf-hku-2bed-8k | 1 | 0 | 0 | 0/0 | no | ok |  | 26 |  |
| flatjai | inf-hkust-studio-4k | 1 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | inf-cityu-3bed-10k | 1 | 0 | 0 | 0/0 | no | ok |  | 27 |  |
| flatjai | zh-hkust-room-8k | 1 | 5 | 0 | 5/5 | no | ok | ok | 25 |  |
| flatjai | zh-hku-flat-15k | 1 | 3 | 0 | 3/3 | no | ok | ok | 26 |  |
| flatjai | zh-cuhk-room-mixed | 1 | 4 | 0 | 5/5 | no | ok | ok | 26 |  |
| flatjai | loc-hang-hau-room | 1 | 5 | 0 | 5/5 | no | ok | ok | 18 |  |
| flatjai | loc-kennedy-town-studio | 1 | 3 | 0 | 6/6 | no | ok | ok | 18 |  |
| flatjai | adv-brief-injection | 1 | 5 | 0 | 5/5 | no | ok | ok | 17 |  |
| flatjai | multi-lower-budget | 1 | 3 | 0 | 3/3 | no | ok | ok | 69 |  |
| flatjai | multi-shorter-commute | 1 | 5 | 0 | 7/7 | no | ok | ok | 45 |  |
| flatjai | std-hkust-own-room-9k | 2 | 4 | 0 | 4/4 | no | ok | ok | 40 |  |
| flatjai | std-hkust-2bed-30k-total | 2 | 3 | 0 | 6/6 | no | ok | ok | 25 |  |
| flatjai | std-hku-studio-15k | 2 | 4 | 0 | 4/4 | no | ok | ok | 36 |  |
| flatjai | std-cityu-room-7k | 2 | 4 | 0 | 4/4 | no | ok | ok | 18 |  |
| flatjai | std-cuhk-room-6k | 2 | 3 | 0 | 3/3 | no | ok | ok | 39 |  |
| flatjai | std-polyu-1bed-18k | 2 | 5 | 0 | 9/9 | no | ok | ok | 21 |  |
| flatjai | miss-cheap-room | 2 | 5 | 0 | 5/5 | yes | ok | ok | 24 |  |
| flatjai | miss-2bed-near-campus | 2 | 5 | 0 | 6/6 | yes | ok | ok | 23 |  |
| flatjai | miss-flat-budget-only | 2 | 3 | 0 | 5/5 | yes | ok | ok | 30 |  |
| flatjai | inf-hku-2bed-8k | 2 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | inf-hkust-studio-4k | 2 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | inf-cityu-3bed-10k | 2 | 0 | 0 | 0/0 | no | ok |  | 29 |  |
| flatjai | zh-hkust-room-8k | 2 | 5 | 0 | 6/6 | no | ok | ok | 20 |  |
| flatjai | zh-hku-flat-15k | 2 | 3 | 0 | 3/3 | no | ok | ok | 28 |  |
| flatjai | zh-cuhk-room-mixed | 2 | 4 | 0 | 5/5 | no | ok | ok | 26 |  |
| flatjai | loc-hang-hau-room | 2 | 5 | 0 | 5/5 | no | ok | ok | 18 |  |
| flatjai | loc-kennedy-town-studio | 2 | 3 | 0 | 5/5 | no | ok | ok | 18 |  |
| flatjai | adv-brief-injection | 2 | 5 | 0 | 5/5 | no | ok | ok | 18 |  |
| flatjai | multi-lower-budget | 2 | 3 | 0 | 3/3 | no | ok | ok | 69 |  |
| flatjai | multi-shorter-commute | 2 | 5 | 0 | 7/7 | no | ok | ok | 51 |  |
| flatjai-no_reflect | std-hkust-own-room-9k | 0 | 0 | 0 | 0/0 | no | FAIL | ok | 14 |  |
| flatjai-no_reflect | std-hkust-2bed-30k-total | 0 | 1 | 0 | 1/1 | no | ok | ok | 14 |  |
| flatjai-no_reflect | std-hku-studio-15k | 0 | 2 | 0 | 3/3 | no | ok | ok | 16 |  |
| flatjai-no_reflect | std-cityu-room-7k | 0 | 5 | 0 | 5/5 | no | ok | ok | 20 |  |
| flatjai-no_reflect | std-cuhk-room-6k | 0 | 1 | 0 | 1/1 | no | ok | ok | 13 |  |
| flatjai-no_reflect | std-polyu-1bed-18k | 0 | 5 | 0 | 9/9 | no | ok | ok | 26 |  |
| flatjai-no_reflect | miss-cheap-room | 0 | 5 | 0 | 5/5 | yes | ok | ok | 21 |  |
| flatjai-no_reflect | miss-2bed-near-campus | 0 | 5 | 0 | 7/7 | yes | ok | ok | 22 |  |
| flatjai-no_reflect | miss-flat-budget-only | 0 | 2 | 0 | 4/4 | yes | ok | ok | 17 |  |
| flatjai-no_reflect | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 8 |  |
| flatjai-no_reflect | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 8 |  |
| flatjai-no_reflect | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 8 |  |
| flatjai-no_reflect | zh-hkust-room-8k | 0 | 5 | 0 | 5/5 | no | ok | ok | 20 |  |
| flatjai-no_reflect | zh-hku-flat-15k | 0 | 1 | 0 | 1/1 | no | ok | ok | 13 |  |
| flatjai-no_reflect | zh-cuhk-room-mixed | 0 | 1 | 0 | 1/1 | no | ok | ok | 11 |  |
| flatjai-no_reflect | loc-hang-hau-room | 0 | 5 | 0 | 6/6 | no | ok | ok | 18 |  |
| flatjai-no_reflect | loc-kennedy-town-studio | 0 | 4 | 0 | 9/9 | no | ok | ok | 20 |  |
| flatjai-no_reflect | adv-brief-injection | 0 | 5 | 0 | 5/5 | no | ok | ok | 19 |  |
| flatjai-no_reflect | multi-lower-budget | 0 | 0 | 0 | 0/0 | no | FAIL | ok | 17 |  |
| flatjai-no_reflect | multi-shorter-commute | 0 | 5 | 0 | 7/7 | no | ok | ok | 44 |  |
| flatjai-no_dedup | std-hkust-own-room-9k | 0 | 5 | 0 | 5/5 | no | ok | ok | 58 |  |
| flatjai-no_dedup | std-hkust-2bed-30k-total | 0 | 3 | 0 | 6/6 | no | ok | ok | 25 |  |
| flatjai-no_dedup | std-hku-studio-15k | 0 | 3 | 0 | 3/3 | no | ok | ok | 30 |  |
| flatjai-no_dedup | std-cityu-room-7k | 0 | 5 | 0 | 6/6 | no | ok | ok | 18 |  |
| flatjai-no_dedup | std-cuhk-room-6k | 0 | 3 | 0 | 4/4 | no | ok | ok | 21 |  |
| flatjai-no_dedup | std-polyu-1bed-18k | 0 | 5 | 0 | 11/11 | no | ok | ok | 18 |  |
| flatjai-no_dedup | miss-cheap-room | 0 | 5 | 0 | 5/5 | yes | ok | ok | 23 |  |
| flatjai-no_dedup | miss-2bed-near-campus | 0 | 5 | 0 | 5/5 | yes | ok | ok | 62 |  |
| flatjai-no_dedup | miss-flat-budget-only | 0 | 3 | 0 | 5/5 | yes | ok | ok | 34 |  |
| flatjai-no_dedup | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 31 |  |
| flatjai-no_dedup | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 30 |  |
| flatjai-no_dedup | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 28 |  |
| flatjai-no_dedup | zh-hkust-room-8k | 0 | 5 | 0 | 6/6 | no | ok | ok | 19 |  |
| flatjai-no_dedup | zh-hku-flat-15k | 0 | 3 | 0 | 3/3 | no | ok | ok | 32 |  |
| flatjai-no_dedup | zh-cuhk-room-mixed | 0 | 4 | 0 | 5/5 | no | ok | ok | 20 |  |
| flatjai-no_dedup | loc-hang-hau-room | 0 | 5 | 0 | 5/5 | no | ok | ok | 22 |  |
| flatjai-no_dedup | loc-kennedy-town-studio | 0 | 4 | 0 | 9/9 | no | ok | ok | 19 |  |
| flatjai-no_dedup | adv-brief-injection | 0 | 5 | 0 | 5/5 | no | ok | ok | 20 |  |
| flatjai-no_dedup | multi-lower-budget | 0 | 4 | 0 | 4/4 | no | ok | ok | 89 |  |
| flatjai-no_dedup | multi-shorter-commute | 0 | 5 | 0 | 7/7 | no | ok | ok | 43 |  |
| flatjai-model_facts | std-hkust-own-room-9k | 0 | 3 | 2 | 3/3 | no | ok | ok | 76 |  |
| flatjai-model_facts | std-hkust-2bed-30k-total | 0 | 0 | 0 | 0/0 | no | FAIL | ok | 90 |  |
| flatjai-model_facts | std-hku-studio-15k | 0 | 3 | 0 | 3/3 | no | ok | ok | 50 |  |
| flatjai-model_facts | std-cityu-room-7k | 0 | 3 | 2 | 3/3 | no | ok | ok | 39 |  |
| flatjai-model_facts | std-cuhk-room-6k | 0 | 2 | 2 | 3/3 | no | ok | ok | 82 |  |
| flatjai-model_facts | std-polyu-1bed-18k | 0 | 0 | 0 | 0/0 | no | FAIL | ok | 50 |  |
| flatjai-model_facts | miss-cheap-room | 0 | 5 | 0 | 6/6 | yes | ok | ok | 30 |  |
| flatjai-model_facts | miss-2bed-near-campus | 0 | 5 | 0 | 5/5 | yes | ok | ok | 37 |  |
| flatjai-model_facts | miss-flat-budget-only | 0 | 3 | 0 | 5/5 | yes | ok | ok | 36 |  |
| flatjai-model_facts | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 26 |  |
| flatjai-model_facts | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 33 |  |
| flatjai-model_facts | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 32 |  |
| flatjai-model_facts | zh-hkust-room-8k | 0 | 5 | 0 | 5/5 | no | ok | ok | 30 |  |
| flatjai-model_facts | zh-hku-flat-15k | 0 | 3 | 0 | 3/3 | no | ok | ok | 48 |  |
| flatjai-model_facts | zh-cuhk-room-mixed | 0 | 3 | 2 | 3/3 | no | ok | ok | 82 |  |
| flatjai-model_facts | loc-hang-hau-room | 0 | 5 | 0 | 5/5 | no | ok | ok | 28 |  |
| flatjai-model_facts | loc-kennedy-town-studio | 0 | 4 | 0 | 9/9 | no | ok | ok | 26 |  |
| flatjai-model_facts | adv-brief-injection | 0 | 5 | 0 | 6/6 | no | ok | ok | 27 |  |
| flatjai-model_facts | multi-lower-budget | 0 | 5 | 5 | 5/5 | no | ok | ok | 59 |  |
| flatjai-model_facts | multi-shorter-commute | 0 | 0 | 0 | 0/0 | no | FAIL | ok | 85 |  |
