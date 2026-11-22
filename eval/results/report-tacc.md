# FlatJai evaluation

## E1 and E2: systems and ablations on the suite (95% bootstrap intervals over cases)

| Metric | b0 | b1 | flatjai | flatjai-model_facts |
|---|---|---|---|---|
| Constraint satisfaction | – | 100% [100–100] | 100% [100–100] | 81% [62–96] |
| All limits confirmed | – | 25% [0–100] | 62% [50–73] | 40% [27–55] |
| Invented facts | – | 52% [43–59] | 0% [0–0] | 0% [0–0] |
| Invented listings | – | 0% [0–0] | 0% [0–0] | 0% [0–0] |
| Correct ask/no-ask | 85% [65–100] | 85% [65–100] | 100% [100–100] | 100% [100–100] |
| Outcome ok | 0% [0–0] | 10% [0–25] | 100% [100–100] | 100% [100–100] |
| Duplicate homes shown | – | 0% [0–0] | 0% [0–0] | 0% [0–0] |
| Cost figures off the cost tool | – | – | 0% [0–0] | 100% [100–100] |
| Homes shown per case | 0.0 | 0.2 | 3.6 | 3.9 |
| Seconds per case (median) | 0.4 | 5.2 | 19.1 | 22.4 |
| Model calls per case (median) | 1.0 | 2.0 | 6.5 | 11.0 |
| Tokens per case (median) | 122.0 | 4339.0 | 8870.5 | 9396.0 |
| Commute error vs router, min (median / max) | n/a | n/a | 0 / 0 | 12 / 39 |

Cases: b0 20, b1 20, flatjai 20, flatjai-model_facts 20.

## By category

| Category | System | Cases | Homes | Constraint sat. | Invented facts | Ask ok | Outcome ok |
|---|---|---|---|---|---|---|---|
| standard | b0 | 6 | 0 | – | – | 100% | 0% |
| standard | b1 | 6 | 0 | – | 55% | 100% | 0% |
| standard | flatjai | 6 | 23 | 100% | 0% | 100% | 100% |
| standard | flatjai-model_facts | 6 | 25 | 68% | 0% | 100% | 100% |
| missing_info | b0 | 3 | 0 | – | – | 0% | 0% |
| missing_info | b1 | 3 | 1 | 100% | 55% | 0% | 33% |
| missing_info | flatjai | 3 | 15 | 100% | 0% | 100% | 100% |
| missing_info | flatjai-model_facts | 3 | 15 | 100% | 0% | 100% | 100% |
| infeasible | b0 | 3 | 0 | – | – | 100% | 0% |
| infeasible | b1 | 3 | 0 | – | 57% | 100% | 0% |
| infeasible | flatjai | 3 | 0 | – | – | 100% | 100% |
| infeasible | flatjai-model_facts | 3 | 0 | – | – | 100% | 100% |
| mixed_language | b0 | 3 | 0 | – | – | 100% | 0% |
| mixed_language | b1 | 3 | 3 | 100% | 46% | 100% | 33% |
| mixed_language | flatjai | 3 | 12 | 100% | 0% | 100% | 100% |
| mixed_language | flatjai-model_facts | 3 | 13 | 85% | 0% | 100% | 100% |
| ambiguous_location | b0 | 2 | 0 | – | – | 100% | 0% |
| ambiguous_location | b1 | 2 | 0 | – | 50% | 100% | 0% |
| ambiguous_location | flatjai | 2 | 10 | 100% | 0% | 100% | 100% |
| ambiguous_location | flatjai-model_facts | 2 | 10 | 100% | 0% | 100% | 100% |
| adversarial | b0 | 1 | 0 | – | – | 100% | 0% |
| adversarial | b1 | 1 | 0 | – | 67% | 100% | 0% |
| adversarial | flatjai | 1 | 5 | 100% | 0% | 100% | 100% |
| adversarial | flatjai-model_facts | 1 | 5 | 100% | 0% | 100% | 100% |
| multi_turn | b0 | 2 | 0 | – | – | 100% | 0% |
| multi_turn | b1 | 2 | 0 | – | 43% | 100% | 0% |
| multi_turn | flatjai | 2 | 8 | 100% | 0% | 100% | 100% |
| multi_turn | flatjai-model_facts | 2 | 9 | 44% | 0% | 100% | 100% |

## Limits checked on shown homes (ok / violated / unknown)

| System | Limit | ok | violated | unknown |
|---|---|---|---|---|
| b1 | budget | 4 | 0 | 0 |
| b1 | room | 1 | 0 | 3 |
| b1 | commute | 0 | 0 | 3 |
| flatjai | budget | 73 | 0 | 0 |
| flatjai | room | 45 | 0 | 28 |
| flatjai | commute | 38 | 0 | 0 |
| flatjai | bedrooms | 7 | 0 | 6 |
| flatjai-model_facts | budget | 77 | 0 | 0 |
| flatjai-model_facts | room | 40 | 0 | 37 |
| flatjai-model_facts | commute | 27 | 15 | 0 |
| flatjai-model_facts | bedrooms | 7 | 0 | 6 |

## Every case

| System | Case | Rep | Homes | Violated | Facts ok | Asked | Outcome | Profile | s | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| b0 | std-hkust-own-room-9k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 1 |  |
| b0 | std-hkust-2bed-30k-total | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | std-hku-studio-15k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | std-cityu-room-7k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | std-cuhk-room-6k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | std-polyu-1bed-18k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | miss-cheap-room | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | miss-2bed-near-campus | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | miss-flat-budget-only | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | zh-hkust-room-8k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | zh-hku-flat-15k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | zh-cuhk-room-mixed | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | loc-hang-hau-room | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | loc-kennedy-town-studio | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | adv-brief-injection | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | multi-lower-budget | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b0 | multi-shorter-commute | 0 | 0 | 0 | 0/0 | no | FAIL |  | 0 |  |
| b1 | std-hkust-own-room-9k | 0 | 0 | 0 | 1/1 | no | FAIL |  | 5 |  |
| b1 | std-hkust-2bed-30k-total | 0 | 0 | 0 | 1/1 | no | FAIL |  | 5 |  |
| b1 | std-hku-studio-15k | 0 | 0 | 0 | 0/0 | no | FAIL |  | 5 |  |
| b1 | std-cityu-room-7k | 0 | 0 | 0 | 1/4 | no | FAIL |  | 5 |  |
| b1 | std-cuhk-room-6k | 0 | 0 | 0 | 1/4 | no | FAIL |  | 5 |  |
| b1 | std-polyu-1bed-18k | 0 | 0 | 0 | 1/1 | no | FAIL |  | 5 |  |
| b1 | miss-cheap-room | 0 | 0 | 0 | 2/6 | no | FAIL |  | 8 |  |
| b1 | miss-2bed-near-campus | 0 | 0 | 0 | 2/3 | no | FAIL |  | 5 |  |
| b1 | miss-flat-budget-only | 0 | 1 | 0 | 1/2 | no | ok |  | 5 |  |
| b1 | inf-hku-2bed-8k | 0 | 0 | 0 | 1/1 | no | FAIL |  | 4 |  |
| b1 | inf-hkust-studio-4k | 0 | 0 | 0 | 1/3 | no | FAIL |  | 5 |  |
| b1 | inf-cityu-3bed-10k | 0 | 0 | 0 | 1/3 | no | FAIL |  | 5 |  |
| b1 | zh-hkust-room-8k | 0 | 0 | 0 | 3/5 | no | FAIL |  | 7 |  |
| b1 | zh-hku-flat-15k | 0 | 3 | 0 | 3/5 | no | ok |  | 14 |  |
| b1 | zh-cuhk-room-mixed | 0 | 0 | 0 | 1/3 | no | FAIL |  | 5 |  |
| b1 | loc-hang-hau-room | 0 | 0 | 0 | 1/2 | no | FAIL |  | 5 |  |
| b1 | loc-kennedy-town-studio | 0 | 0 | 0 | 2/4 | no | FAIL |  | 6 |  |
| b1 | adv-brief-injection | 0 | 0 | 0 | 1/3 | no | FAIL |  | 7 |  |
| b1 | multi-lower-budget | 0 | 0 | 0 | 3/5 | no | FAIL |  | 7 |  |
| b1 | multi-shorter-commute | 0 | 0 | 0 | 1/2 | no | FAIL |  | 5 |  |
| flatjai | std-hkust-own-room-9k | 0 | 3 | 0 | 3/3 | no | ok | ok | 68 |  |
| flatjai | std-hkust-2bed-30k-total | 0 | 5 | 0 | 15/15 | no | ok | ok | 27 |  |
| flatjai | std-hku-studio-15k | 0 | 3 | 0 | 8/8 | no | ok | ok | 18 |  |
| flatjai | std-cityu-room-7k | 0 | 5 | 0 | 6/6 | no | ok | ok | 10 |  |
| flatjai | std-cuhk-room-6k | 0 | 4 | 0 | 4/4 | no | ok | ok | 30 |  |
| flatjai | std-polyu-1bed-18k | 0 | 3 | 0 | 8/8 | no | ok | ok | 16 |  |
| flatjai | miss-cheap-room | 0 | 5 | 0 | 6/6 | yes | ok | ok | 12 |  |
| flatjai | miss-2bed-near-campus | 0 | 5 | 0 | 11/11 | yes | ok | ok | 29 |  |
| flatjai | miss-flat-budget-only | 0 | 5 | 0 | 13/13 | yes | ok | ok | 25 |  |
| flatjai | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 22 |  |
| flatjai | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 21 |  |
| flatjai | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 24 |  |
| flatjai | zh-hkust-room-8k | 0 | 5 | 0 | 6/6 | no | ok | ok | 12 |  |
| flatjai | zh-hku-flat-15k | 0 | 3 | 0 | 8/8 | no | ok | ok | 9 |  |
| flatjai | zh-cuhk-room-mixed | 0 | 4 | 0 | 4/4 | no | ok | ok | 15 |  |
| flatjai | loc-hang-hau-room | 0 | 5 | 0 | 5/5 | no | ok | ok | 12 |  |
| flatjai | loc-kennedy-town-studio | 0 | 5 | 0 | 14/14 | no | ok | ok | 16 |  |
| flatjai | adv-brief-injection | 0 | 5 | 0 | 6/6 | no | ok | ok | 8 |  |
| flatjai | multi-lower-budget | 0 | 3 | 0 | 3/3 | no | ok | ok | 43 |  |
| flatjai | multi-shorter-commute | 0 | 5 | 0 | 14/14 | no | ok | ok | 20 |  |
| flatjai-model_facts | std-hkust-own-room-9k | 0 | 5 | 5 | 5/5 | no | ok | ok | 33 |  |
| flatjai-model_facts | std-hkust-2bed-30k-total | 0 | 5 | 0 | 15/15 | no | ok | ok | 29 |  |
| flatjai-model_facts | std-hku-studio-15k | 0 | 3 | 0 | 8/8 | no | ok | ok | 20 |  |
| flatjai-model_facts | std-cityu-room-7k | 0 | 5 | 2 | 5/5 | no | ok | ok | 12 |  |
| flatjai-model_facts | std-cuhk-room-6k | 0 | 4 | 1 | 4/4 | no | ok | ok | 34 |  |
| flatjai-model_facts | std-polyu-1bed-18k | 0 | 3 | 0 | 8/8 | no | ok | ok | 19 |  |
| flatjai-model_facts | miss-cheap-room | 0 | 5 | 0 | 6/6 | yes | ok | ok | 24 |  |
| flatjai-model_facts | miss-2bed-near-campus | 0 | 5 | 0 | 11/11 | yes | ok | ok | 30 |  |
| flatjai-model_facts | miss-flat-budget-only | 0 | 5 | 0 | 12/12 | yes | ok | ok | 27 |  |
| flatjai-model_facts | inf-hku-2bed-8k | 0 | 0 | 0 | 0/0 | no | ok |  | 22 |  |
| flatjai-model_facts | inf-hkust-studio-4k | 0 | 0 | 0 | 0/0 | no | ok |  | 22 |  |
| flatjai-model_facts | inf-cityu-3bed-10k | 0 | 0 | 0 | 0/0 | no | ok |  | 24 |  |
| flatjai-model_facts | zh-hkust-room-8k | 0 | 5 | 0 | 6/6 | no | ok | ok | 12 |  |
| flatjai-model_facts | zh-hku-flat-15k | 0 | 3 | 0 | 8/8 | no | ok | ok | 11 |  |
| flatjai-model_facts | zh-cuhk-room-mixed | 0 | 5 | 2 | 5/5 | no | ok | ok | 20 |  |
| flatjai-model_facts | loc-hang-hau-room | 0 | 5 | 0 | 6/6 | no | ok | ok | 12 |  |
| flatjai-model_facts | loc-kennedy-town-studio | 0 | 5 | 0 | 14/14 | no | ok | ok | 18 |  |
| flatjai-model_facts | adv-brief-injection | 0 | 5 | 0 | 5/5 | no | ok | ok | 12 |  |
| flatjai-model_facts | multi-lower-budget | 0 | 5 | 5 | 5/5 | no | ok | ok | 25 |  |
| flatjai-model_facts | multi-shorter-commute | 0 | 4 | 0 | 9/9 | no | ok | ok | 57 |  |
