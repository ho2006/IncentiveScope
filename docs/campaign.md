# GMX V2 / Arbitrum STIP: campaign context

The real historical case isolates first-round trading-rebate distribution type **1003**. Its archived earning interval is after **2023-11-15 midnight UTC** through **2024-03-27 midnight UTC**, exclusive end. The integer-second half-open configuration starts at `00:00:01` because the contemporaneous indexer tests a strict greater-than launch timestamp. [Boundary code, final epoch and report reconciliation](boundary-evidence.md) establish this decision; March 29 is the overall program's administrative end.

| Exposure | Primary source | Relevance |
| --- | --- | --- |
| Original STIP trading rebates | [GMX addendum](https://forum.arbitrum.foundation/t/gmx-stip-addendum/23484), [final report](https://forum.arbitrum.foundation/t/leveraging-the-stip-grants-program-to-grow-the-gmx-and-arbitrum-defi-ecosystem/23100), archived generation code | Earning epochs and reward mechanism, distinct from payment |
| Earlier Odyssey tasks, September 2023 | [Arbitrum announcement](https://blog.arbitrum.io/arbitrum-odyssey-reignited/), [organizer quest](https://app.galxe.com/quest/arbitrum/GCsqgUtsTX) | Earlier observed addresses may have prior incentive exposure; September activity surge is contextual, not an untreated baseline |
| GMX competition, March 13–27, 2024 | [GMX announcement](https://gmxio.substack.com/p/the-gmx-eip4844-trading-competition) | Overlaps the final earning weeks |
| Binance Wallet tasks, March 27–April 9, 2024 | [Binance announcement](https://www.binance.com/en/support/announcement/detail/55199366818140f4afd4bc56000d92f2) | Overlaps the first two post weeks, represented with April 10 exclusive UTC date boundary |
| STIP Bridge, from June 26, 2024 | [GMX update](https://forum.arbitrum.foundation/t/gmx-stip-b-bi-weekly-update/25219) | Starts outside this study's May 29 exclusive extraction end |

## Evidence and limits

The [907,107-row indexed extract](../data/evidence/history-manifest.json) spans September 20, 2023 through May 29, 2024. [Daily quality and independent recount](data-quality.md) distinguish local extraction coverage from upstream population completeness. [Five chain receipts](event-validation.md) validate selected account, event, size and fee fields. They do not certify every historical row or deployed decoder.

The source selects successful `OrderExecuted` perpetual types 2–7. Protocol accounts are used instead of keeper senders. Creation is separately looked up by order key. Net position-fee fields are converted under the historical contract's token-adjusted collateral-price convention; external rebates and other fee classes are excluded. This fee is not protocol revenue.

Historical ADL can use market-decrease type 4, and the indexed surface omits the secondary ADL marker. Opening-only retention is unaffected, but the report withholds voluntary30 and labels the broader opening-or-decrease comparison. First-observed history uses positive increases or indexed decreases and may include forced decreases. Addresses are not people, and observed addresses are not necessarily rebate recipients.

[Official allocations](reward-data.md) total 19 epochs. Recipient substitution can merge original accounts, so trader-level reward costs remain unavailable. Neither reward payment dates nor high frequency, small orders or a threshold-matching transaction establish acquisition, Sybil status or campaign participation for a particular person.

The report is a descriptive historical comparison. Other incentives and market conditions can affect its post windows; a documented earning cutoff does not supply a causal counterfactual.
